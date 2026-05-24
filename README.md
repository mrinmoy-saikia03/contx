# contx

Git for context. Append-only logs of *why* each file and function exists, written by AI coding agents as they edit and read by AI agents when explaining code to humans.

See `docs/specs/2026-05-21-contx-design.md` for the full design.

## Install

One-command install (uses `pipx` if present, else a local venv):

```bash
./install.sh           # just the CLI + MCP binaries
./install.sh --all     # also installs the Claude Code skill + registers contx-mcp
```

Or for development inside this repo:

```bash
pip install -e .[dev]
```

## Quickstart

```bash
contx init
contx append --ref src/foo.py::bar --event created --rationale "why this exists"
contx show src/foo.py::bar
contx log src/foo.py
```

## CLI commands

| Command | Purpose |
|---|---|
| `contx init` | Initialize contx for the current git repo (creates `.contx/config.json`). |
| `contx append --ref X --event Y --rationale Z` | Add a context entry. `--event` is one of `created`, `modified`, `renamed_in`, `renamed_out`, `moved_in`, `moved_out`, `deleted`. Repeatable `--tag` and `--related`. |
| `contx show <ref>` | Print the folded current intent for a file or symbol. |
| `contx log <ref>` | Print the full append-only history. |
| `contx draft [--from-transcript]` | Interactive editor for drifted files; appends entries and re-stages `.contx/`. |
| `contx install-hook` / `contx uninstall-hook` | Install or remove the pre-commit hook (`contx init` installs it by default; use `init --no-hook` to skip). |
| `contx install-skill` / `contx uninstall-skill` | Install or remove the Claude Code skill at `~/.claude/skills/contx/`. |
| `contx bootstrap [--ast] [--git] [--since REF] [--dry-run] [--force]` | Seed entries from git history + AST on an already-initialized repo. |
| `contx serve [--port 4242] [--host 127.0.0.1]` | Launch the read-only local web UI. |
| `contx version` | Print version. |

`<ref>` is either `path/to/file.py` (file-level) or `path/to/file.py::Class.method` (symbol-level).

## Using with Claude Code (MCP)

contx ships an MCP server (`contx-mcp`) so AI coding agents can read and write context entries directly during a session.

### Add to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp"
    }
  }
}
```

By default the server uses `os.getcwd()` to find the repo root (walks up looking for `.git`). To point at a specific repo, set `CONTX_REPO_ROOT`:

```json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp",
      "env": { "CONTX_REPO_ROOT": "/path/to/repo" }
    }
  }
}
```

### MCP tools exposed

| Tool | Purpose |
|---|---|
| `contx_query` | Read folded intent + raw log for a file or symbol. |
| `contx_append` | Add a context entry (created / modified / deleted / etc.). |
| `contx_search` | Substring search across all entries (rationale + tags). |
| `contx_rename` | Refactor bookkeeping for renames and moves. |
| `contx_delete` | Append a deletion entry (history preserved). |
| `contx_audit` | Find orphan sidecars and untracked source files. |

The intended workflow: AI agents call `contx_query` before editing to learn existing context, then call `contx_append` (or `contx_rename` / `contx_delete`) in the same turn as their `Edit` / `Write` tool calls. The CLI is for humans.

## Claude Code skill

contx ships a Claude Code skill that enforces the workflow rules: query existing context before editing, append context in the same turn as code edits, handle renames/deletes through the MCP tools.

### Install

```bash
contx install-skill
```

This copies `skills/contx/SKILL.md` to `~/.claude/skills/contx/`. Re-running the command updates to the latest version (overwrites). Override the destination with `CONTX_CLAUDE_HOME=/some/path contx install-skill` if you keep Claude config elsewhere.

### What the skill enforces

When working in a repo with `.contx/`, Claude will:
- Call `contx_query` before editing a tracked file (to learn existing intent).
- Call `contx_append` in the same turn as any `Edit`/`Write` on a tracked file.
- Call `contx_rename` *before* applying a code rename.
- Call `contx_delete` with a rationale when removing code.
- Ask the user for the *why* if it isn't already clear in the conversation (never invent a rationale).

The skill activates on the user's `/contx` invocation, or you can wire a SessionStart hook to load it automatically when `.contx/` is detected (not done by `install-skill` — that's intentional, to keep user-level Claude Code settings explicit).

### Uninstall

```bash
contx uninstall-skill
```

Removes `~/.claude/skills/contx/` (the contx skill directory only — other skills untouched).

## Pre-commit hook

`contx init` installs a `pre-commit` hook in `.git/hooks/pre-commit` (use `--no-hook` to opt out). The hook blocks any commit where a tracked source file changed but its `.contx/` sidecar didn't.

Example:

```
$ git commit -m "fix the bug"
error: contx drift — the following files changed without a matching .contx/ entry:
  - src/auth/login.py

Fix: add a contx entry for each file, then re-stage and re-commit.
Example:
  contx append --ref src/auth/login.py --event modified --rationale 'why this changed'
  git add .contx/
  git commit

To bypass once: git commit --no-verify
To disable enforcement: set 'require_context_on_commit': false in .contx/config.json
```

### Fixing drift with `contx draft`

When the hook blocks, run `contx draft`. It opens your `$EDITOR` (or `$VISUAL`, or `CONTX_EDITOR`) on a template with one section per drifted file. Fill in the `rationale:` line, save, exit — entries are appended to `.contx/` and re-staged. Then re-run `git commit`.

```
$ contx draft
# (editor opens)
# contx draft — fill in a rationale for each file, then save & exit.
#
# ## src/auth/login.py
# event: modified
# rationale: switched to email-only because GDPR
# tags: compliance, gdpr
#
# (save & exit)
appended 1 entries and staged .contx/. Run `git commit` again.
```

For a head start: `contx draft --from-transcript` heuristically mines the most recent Claude Code session transcript at `~/.claude/projects/<sanitized-cwd>/` and pre-fills each rationale with the most relevant sentence. Edit as needed before saving.

### Bypass

- **One commit:** `git commit --no-verify`
- **Whole repo:** set `"require_context_on_commit": false` in `.contx/config.json` to convert the block into a soft warning.

### Manage the hook

- `contx install-hook` — install (or top up) the hook on a repo that wasn't `init`'d with it.
- `contx uninstall-hook` — remove the contx block (preserves other content in the hook).

## Web UI

```bash
contx serve              # localhost:4242
contx serve --port 8080  # any port
```

Opens a read-only web viewer. Routes:

- `/` — file tree (every source file with contx entries).
- `/file/<path>` — file-level intent, list of symbols, full log.
- `/symbol/<path>::<symbol>` — symbol's current intent + complete log.
- `/search?q=` — full-text search across all rationales and tags.
- `/timeline` — recent entries across the whole repo, sorted newest first.

No auth, no edits, no JS bundle — server-rendered HTML with a sprinkle of htmx. The intent map travels with git: anyone who clones the repo can `contx serve` and see why every function is the way it is.

## `.contxignore`

`contx init` creates a `.contxignore` at the repo root (gitignore-style syntax) with sensible defaults: `**/node_modules/**`, `**/__tests__/**`, `**/.venv/**`, `**/venv/**`, `**/dist/**`, `**/build/**`, `**/.contx/**`. Add to it whatever your team wants contx to skip.

Patterns from `.contxignore` are **additive** to the `ignore` field in `.contx/config.json`. The effective ignore set is the union of both. config.json holds the per-init defaults; `.contxignore` is where you put ongoing per-repo exclusions next to `.gitignore`.

Supported syntax (subset of gitignore):
- `*` — match any single path segment
- `**` — match any number of segments
- `dir/file.py` — exact path
- `# comment` — ignored
- Negation (`!`) is not yet supported.

Affects: drift detection (pre-commit hook), `contx_audit`, and any future tooling that walks the source tree.

## Bootstrapping a brownfield repo

On an existing repo, `contx init` automatically runs a bootstrap pass after initialization (pass `--no-bootstrap` to skip). The bootstrap walks the source tree with `ast` and emits one baseline entry per file/symbol, using docstrings where available.

```bash
contx init                  # init + AST bootstrap (default)
contx init --no-bootstrap   # init only, no entries written
contx init --bootstrap-ast  # AST only (skip git history)
contx init --bootstrap-git  # git history only (skip AST)
```

On an already-initialized repo, use the standalone `contx bootstrap` command:

```bash
contx bootstrap             # AST + git history (default)
contx bootstrap --ast       # AST only
contx bootstrap --git       # git history only
contx bootstrap --since v1.0.0   # only commits after a ref
contx bootstrap --dry-run   # print counts without writing
contx bootstrap --force     # re-run even if already bootstrapped
```

### What gets written

- **AST pass:** one `file`-kind entry per Python file (rationale = module docstring), plus one `symbol`-kind entry per top-level function/class/method (rationale = docstring). Tagged `bootstrap`.
- **Git history pass:** one `file`-kind entry per non-noisy commit × file touched. First occurrence is `created`, subsequent are `modified`. Tagged `bootstrap` + `git-history`. Noisy commits (WIP, typo, lint, merge, bump, chore(deps), tiny diffs) are skipped automatically.

All bootstrap entries carry `agent="audit"` so they're distinguishable from human-written or agent-written context.

### Idempotence

Running bootstrap twice without `--force` raises an error: `repo already bootstrapped`. With `--force`, a supersede marker entry is appended to each already-bootstrapped sidecar before the new entries are written.

## Storage layout

contx stores entries in JSONL sidecars under `.contx/`, mirroring the source tree:

```
your-repo/
├── src/auth/login.py
└── .contx/
    ├── config.json
    └── src/auth/login.py.jsonl
```

Each line of the sidecar is one entry: `{id, kind, symbol, event, rationale, tags, author, timestamp, agent, related}`. Append-only. All files are committed to git so context travels with the code.

## Deployment-manifest awareness

contx tracks deployment manifests (Kubernetes, GitHub Actions, docker-compose) as first-class citizens alongside source files.

### `tracked_paths`

`config.json` has a `tracked_paths` field — a list of `{glob, kind, summarizer}` records:

```json
{
  "tracked_paths": [
    {"glob": "**/*.py", "kind": "source", "summarizer": null},
    {"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"},
    {"glob": ".github/workflows/*.yml", "kind": "deploy", "summarizer": "github_actions"},
    {"glob": "docker-compose*.yml", "kind": "deploy", "summarizer": "docker_compose"}
  ]
}
```

The pre-commit hook and `contx audit` use these globs to detect drift on any tracked path, not just source files.

### Summarizers

Three built-in summarizers produce human-readable rationale entries from manifest YAML:

| Name | Handles |
|------|---------|
| `kubernetes` | Deployment, Service, Ingress resources |
| `github_actions` | Workflow triggers, job count, referenced secrets |
| `docker_compose` | Service list, images, `depends_on` chains |

### `contx bootstrap-deploy`

Runs every registered summarizer over its matching `tracked_paths` globs and writes the results as `.contx/` sidecar entries:

```bash
contx bootstrap-deploy
# bootstrap-deploy wrote 12 summary entries
```

Run this once when onboarding a repo that already has deployment manifests. The entries are then visible via `contx show`, `contx log`, and the MCP tools.

## Diagrams

`contx diagram` renders the repo's intent graph as a [draw.io](https://app.diagrams.net) XML file:

```bash
contx diagram                    # writes .contx/diagrams/files.drawio
contx diagram --out my.drawio    # custom output path
```

The output file (`.contx/diagrams/files.drawio`) can be opened with:

- **[app.diagrams.net](https://app.diagrams.net)** — paste/import the file in the browser
- **VS Code** — [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio) extension

Each source file becomes a node, coloured by top-level directory. Tooltip shows the file intent. Edges come from `related` backlinks in entries. Layout is Fruchterman-Reingold force-directed (pure Python, no deps).

`--type symbols` and `--type deploy` are reserved for future work; only `files` is implemented in this MVP.

## Status

Plans 1–5 plus backlog items B1 (`.contxignore`), B2 (bootstrap), B3 (deployment awareness), and B4 (diagrams) shipped: storage + CLI, MCP server, pre-commit hook, `contx draft`, Claude Code skill, local web UI, per-repo ignore file, brownfield bootstrap from AST + git history, deployment-manifest summarizers, and draw.io diagram export. Remaining backlog items: tuple-vs-list immutability on `Entry.tags`/`related`, SessionStart skill auto-load, `__main__.py` test coverage. See `docs/plans/` and `docs/BACKLOG.md`.

