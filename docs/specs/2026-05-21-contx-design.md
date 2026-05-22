# contx — Design Document

**Date:** 2026-05-21
**Author:** Mrinmoy Saikia (with Claude as design partner)
**Status:** Design — awaiting user approval before implementation planning

---

## 1. Problem

When AI coding agents (Claude, Cursor, etc.) edit code, the *rationale* for every change lives only in the ephemeral conversation. The moment the session ends, the "why" is gone. `git blame` answers *who* and *when*, never *why*. Code-review graphs (e.g., `code-review-graph`) answer *what is connected to what*, never *what was the human decision*.

A new developer cloning a repo inherits the code but not the intent behind it. They can ask the AI "what does this function do?" — but the AI can only re-derive behavior from the code itself. It cannot tell them *why* the retry logic is linear instead of exponential, *why* the SSO module was split from auth, or *which incident* drove a given defensive `try/except`.

**contx fills this gap: an append-only log of *intent* per file/symbol, version-controlled alongside code, written by AI agents as they edit and read by AI agents when explaining code to humans.**

---

## 2. Product Form Factor

**MVP shape: MCP server + CLI + local web UI + Claude Code skill.**

- **MCP server (`contx-mcp`)** — exposes context read/write tools to any MCP-capable AI agent (Claude Code first; Cursor, Windsurf, Codex compatible by design).
- **CLI (`contx`)** — human-facing commands: `init`, `show`, `log`, `audit`, `serve`, `export`.
- **Local web UI** — read-only viewer launched by `contx serve`. Renders the full intent map of the repo.
- **Claude Code skill** — loaded on session start; enforces "every code edit must be paired with a context update."

No SaaS, no cloud sync, no auth. All state is files in `.contx/` inside the repo, committed to git.

---

## 3. Primary Consumer

**AI agents first, humans second.**

Humans don't browse context entries directly most of the time — they ask the AI ("why does this function exist?", "explain this module's purpose"), and the AI synthesizes an answer from the stored entries plus the code. The local web UI exists for the cases when a human does want to browse directly (onboarding, audits, PR review).

This decision drives:
- Storage format is machine-readable (JSONL), not Markdown.
- Retrieval is via MCP tools that agents call programmatically.
- The web UI is a thin read-only viewer, not a CMS.

---

## 4. Storage Model

### 4.1 Layout

`.contx/` directory at repo root, **mirror tree** of source files. Committed to git like any other code.

```
repo/
├── src/
│   └── auth/
│       └── login.py
├── .contx/
│   ├── config.json
│   └── src/
│       └── auth/
│           └── login.py.jsonl
```

One sidecar JSONL file per source file. Append-only. PR-reviewable side-by-side with the code change that produced it.

### 4.2 Entry schema

Each line in a sidecar is one JSON object:

```json
{
  "id": "01HXYZ...ULID",
  "kind": "symbol",
  "symbol": "User.authenticate",
  "event": "created",
  "rationale": "Email-only login because Legal said phone OTP doesn't meet GDPR for EU users (ticket COMPLIANCE-412).",
  "tags": ["compliance", "gdpr"],
  "author": "mrinmoy.saikia@xeno.in",
  "timestamp": "2026-05-21T14:23:11Z",
  "agent": "claude-code",
  "related": ["src/auth/sso/handlers.py::route_eu_user"]
}
```

Fields:

| Field | Required | Notes |
|---|---|---|
| `id` | yes | ULID — sortable, globally unique, no collisions on parallel branches |
| `kind` | yes | `"file"` or `"symbol"` |
| `symbol` | if `kind=symbol` | Dotted path within file (`Class.method`, `function`, `Class.NestedClass.method`) |
| `event` | yes | `created`, `modified`, `renamed_in`, `renamed_out`, `moved_in`, `moved_out`, `deleted` |
| `rationale` | yes | Free-text the *why*. Never describes *what* the code does. |
| `tags` | optional | Open vocabulary; suggested taxonomy in §10 |
| `author` | yes | From git config at write time |
| `timestamp` | yes | ISO8601 UTC |
| `agent` | yes | `claude-code`, `cursor`, `human-cli`, `audit` |
| `related` | optional | Backlinks to other symbols (for refactors that touch multiple files) |

**Note: `commit_sha` is NOT stored in the entry.** It's *derived on read* by running `git blame` on the JSONL line that holds the entry. This avoids the post-commit-amend trap and keeps entries pure data. The CLI and web UI hydrate `commit_sha` lazily when displaying log views.

### 4.3 Two temporal modes

1. **Current intent (folded view)** — the "what is this for, right now" view, computed by folding all entries for a file/symbol. Cached but always re-derivable.
2. **Change log (raw)** — the full append-only history of why this file/symbol changed.

We **never store "what the function does"** — that is derivable by reading the code. We store only what cannot be re-derived: intent, decisions, constraints, business reasoning, incident links.

---

## 5. Granularity

Hierarchical: **file-level + symbol-level**, both at once.

Per-repo configurable in `.contx/config.json` at `contx init`:

```json
{
  "granularity": "both",
  "languages": ["py", "ts", "tsx", "js", "go", "java", "kt", "rs"],
  "ignore": ["**/node_modules/**", "**/__tests__/**", "**/*.test.*"],
  "require_rationale_on_create": true,
  "extract_rationale_on_modify": true
}
```

- `granularity`: `"file"` | `"symbol"` | `"both"` (default)
- `languages`: which file extensions to track. Default = common code extensions.
- `ignore`: gitignore-style patterns.
- `require_rationale_on_create`: hard-blocks symbol creation without a rationale.
- `extract_rationale_on_modify`: enables conversation-mining at commit time.

---

## 6. Identity & Refactor Propagation

**Symbol identity** = `relative_file_path::symbol_path` (e.g., `src/auth/login.py::User.authenticate`).

**No AST parsing on contx's side.** The AI agent — which is already doing the editing — provides the symbol path as a string when it calls a contx MCP tool. contx is a glorified key-value store with git-friendly layout.

### Refactor flow

When an AI agent renames or moves a symbol, it must, **in the same conversational turn**:

1. Call `contx_rename(old_file, old_symbol?, new_file, new_symbol?)`
2. Apply the code `Edit`

The `contx_rename` call:
- Appends a `renamed_out` (or `moved_out`) entry to the old sidecar
- Appends a `renamed_in` (or `moved_in`) entry to the new sidecar with `related` backlink to the old location
- The full prior history stays in the old sidecar; readers follow `related` links to trace ancestry

### Fallback for non-AI edits

`contx audit`:
- Scans the working tree for symbols in code that have no entry in `.contx/`
- Scans `.contx/` for entries pointing at symbols that no longer exist
- For each orphan, prompts interactively: "Did `login_user` become `authenticate_user`? (y/n/skip)"
- Writes inferred entries with `agent: "audit"` so they're traceable

---

## 7. Capture Workflow

Two trigger styles, both active, picked by event type:

### 7.1 Symbol/file creation → inline prompt

When the AI is about to create a new symbol or file, the skill instructs it to:

1. Call `contx_append(kind, event="created", rationale=...)` **before** the `Edit` tool.
2. If the rationale isn't clearly stated in the current conversation, **ask the user before editing**. Never invent a rationale.

This enforces the "decision moment" capture for things-being-born.

### 7.2 Symbol modification → commit-time extraction

The user codes/converses freely. At `git commit` time, a pre-commit hook runs an extraction routine:

1. Reads `git diff --cached` to identify changed symbols.
2. Reads the current Claude Code session transcript (from the session log path Claude Code already maintains).
3. For each changed symbol, drafts a contx entry by extracting the most relevant rationale-bearing snippets from the conversation.
4. Opens an editor (like `git commit -e`) showing all drafts side-by-side; the user edits/approves/discards each.
5. Approved drafts are appended to the relevant sidecars and added to the same commit.

This keeps the inner loop frictionless and batches review at commit boundaries.

### 7.3 The `git commit` becomes atomic

A single commit contains:
- The code change
- The corresponding `.contx/` sidecar updates

PR reviewers see both side-by-side. If a contributor commits code without contx entries, the pre-commit hook blocks the commit (configurable).

---

## 8. MCP Tool Surface (what AI agents call)

| Tool | Purpose | Inputs |
|---|---|---|
| `contx_init` | One-time repo initialization | `config?` |
| `contx_append` | Add an entry | `file, symbol?, kind, event, rationale, tags?, related?` |
| `contx_rename` | Rename/move bookkeeping | `old_file, old_symbol?, new_file, new_symbol?, rationale?` |
| `contx_delete` | Append a deletion entry (history preserved) | `file, symbol?, rationale` |
| `contx_query` | Read current intent + log for a symbol/file | `file, symbol?` |
| `contx_search` | FTS across all entries | `query, limit?` |
| `contx_audit` | Find orphans/missing context | — |

Read tools (`contx_query`, `contx_search`) are the hot path — AI agents call them before editing to load existing intent.

---

## 9. Claude Code Skill

Lives at `~/.claude/skills/contx/SKILL.md`. Auto-loads via SessionStart hook when `.contx/` is detected in the project root, OR on-demand via `/contx`.

Enforces:

- **R1.** Before editing any tracked file, call `contx_query` to load existing intent for the affected symbols.
- **R2.** Never call `Edit` or `Write` on a tracked symbol without a paired `contx_*` call in the same turn.
- **R3.** When creating a new symbol/file, ask the user for rationale if not already clearly stated.
- **R4.** When renaming/moving, emit `contx_rename` *before* applying the rename in code.
- **R5.** When deleting code, emit `contx_delete` with rationale.
- **R6.** When explaining code to the user, prefer stored intent over re-deriving from code.

---

## 10. CLI Commands (human-facing)

| Command | Purpose |
|---|---|
| `contx init` | Set up tracking. Creates `.contx/config.json`, installs `pre-commit` and `post-commit` hooks. |
| `contx show <symbol\|file>` | Print the folded current intent. |
| `contx log <symbol\|file>` | Print the full append-only history. |
| `contx audit` | Detect orphans, prompt user to fix. |
| `contx serve [--port 4242]` | Launch local web UI. |
| `contx export --format markdown` | Dump a human-readable intent guide (useful for onboarding docs). |
| `contx tags` | List tags in use across the repo. |

### Suggested tag taxonomy (open vocabulary, not enforced)

`compliance`, `gdpr`, `security`, `performance`, `incident`, `refactor`, `business-decision`, `tech-debt`, `experiment`, `deprecation`.

---

## 11. Local Web UI

Read-only. Served by `contx serve`. Single localhost port. No auth.

Routes:
- `/` — file tree of the repo, click-through.
- `/file/<path>` — file-level intent + symbol list.
- `/symbol/<path>::<symbol>` — symbol intent + full timeline log; each entry shows commit SHA (linked to `git show`), author, timestamp, rationale, tags, related links.
- `/search?q=...` — full-text search across all entries.
- `/timeline` — recent activity feed (all commits with their contx entries).

Stack (MVP): plain server-rendered HTML + htmx for search interactivity. No React, no build step. We can upgrade later if needed.

---

## 12. Git Integration

- `.contx/` is **fully committed to git**. No `.gitignore` exclusions.
- `contx init` installs:
  - **Pre-commit hook** — scans staged code changes, cross-references with staged `.contx/` changes, runs the extraction agent if there's drift, prompts the user, and re-stages any approved contx entries so they're part of the same commit.
  - (No post-commit hook is needed because `commit_sha` is derived via `git blame` rather than stored — see §4.2.)
- **Branches**: sidecars are normal files; git handles branching naturally. Each branch can have its own intent log.
- **Merges**: append-only JSONL design means most merges are clean (both branches add new lines). Conflicts on the same line are rare. When they happen, `contx merge-resolve` does smart merge by ULID order.

---

## 13. Tech Stack

- **Language**: Python 3.11+ for both MCP server and CLI (single repo, single venv, single binary via PyInstaller or shiv).
- **MCP**: official `mcp` Python SDK.
- **CLI framework**: `click` or `typer`.
- **Storage**: plain JSONL files. No database. Indexing for search via SQLite FTS5 generated on demand.
- **Web UI**: FastAPI (already a dependency for MCP), Jinja2 templates, htmx for interactivity, Pico.css for default styling.
- **Hook scripts**: bash, calling out to `contx` CLI.

---

## 14. Testing Strategy

- **Unit**: JSONL read/write, entry schema validation, ULID generation, fold logic.
- **Integration**: MCP tool surface tested against a mock client.
- **End-to-end**: A fake AI agent edits code in a temp repo, calls MCP tools, commits, then we verify sidecars and git state.
- **Refactor scenarios**: rename, move-across-files, split-function-into-two — verify history is preserved and traceable.
- Target **80%+ coverage** per project rules.

---

## 15. Success Criteria (MVP)

1. `contx init` creates `.contx/` with sane defaults in any git repo.
2. When the user works with Claude Code and creates a new function, contx prompts for "why" (or skips if it's clear in conversation) and records it.
3. When the user commits, contx auto-extracts modification rationales from the Claude session transcript, presents drafts, and includes approved entries in the same commit.
4. `contx show src/foo.py::bar` prints the current intent and full log of that symbol.
5. `contx serve` opens a localhost page showing the repo's full intent map.
6. AI-driven rename/move preserves the context chain across files.
7. `contx audit` finds and helps fix orphans from non-AI edits.
8. A new dev clones the repo, runs `contx serve` (or asks Claude "why is this here?"), and gets the intent immediately.

---

## 16. Out of Scope (deferred to post-MVP)

- Cross-repo links.
- Team/multi-user features beyond what git already provides.
- Cloud sync / SaaS dashboard / billing.
- AST-based language analysis (we don't need it — AI agents provide symbol paths).
- Auth / write access in the web UI.
- Auto-summarization across many entries (Claude can do this on demand via MCP).
- Visual diff overlays in the web UI.
- VSCode / JetBrains extensions (later — the web UI covers the same need for MVP).

---

## 17. Open Questions

(Resolve these before or during implementation planning.)

1. **Claude session transcript location** — confirm the exact path/format Claude Code writes session logs to, since the extraction agent depends on it.
2. **Multi-language symbol path conventions** — `Class.method` works for Python and JS; what about Go (`Receiver.Method`), Rust (`impl Type::method`), Kotlin (`Class.method` with extension funcs)? Pick a canonical form per language at `init`.
3. **Conflict resolution UX** — when two devs both add entries on different branches, the merge is clean by default. But what about contradictory rationales for the same symbol? `contx merge-resolve` UI is sketched but not designed in detail.
4. **Performance ceiling** — at what repo size does folding/searching become slow enough to need a real DB? (Hypothesis: 100k entries before we feel anything.)
5. **Skill activation reliability** — Claude Code skill rules vs. natural model behavior. May need iteration on the SKILL.md prompt for R2–R5 enforcement to actually hold.

---

## 18. Glossary

- **Sidecar** — the `.jsonl` file in `.contx/` mirroring a source file.
- **Entry** — one JSON object on one line of a sidecar.
- **Fold** — the operation of collapsing a sidecar's append-only log into a "current intent" view.
- **Orphan** — a symbol in code with no contx entry, or a contx entry pointing at a symbol that no longer exists.
- **Rationale** — the free-text *why* in an entry. Never *what*.
