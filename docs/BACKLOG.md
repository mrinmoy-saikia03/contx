# contx — Backlog

Items deferred from spec/plans, with current status.

## Shipped

- **Plan 1** — Storage core: `Entry`, sidecar JSONL files, append/read/fold, repo + config + ignore primitives.
- **Plan 2** — MCP server with 6 tools (`contx_query`, `contx_append`, `contx_rename`, `contx_delete`, `contx_search`, `contx_audit`).
- **Plan 3** — Pre-commit hook + drift detection (`_precommit-check`).
- **Plan 4** — Claude Code skill + installer (`./install.sh --skill`).
- **Plan 5** — Local read-only web UI (`contx serve`, port auto-fallback, `--strict-port` opt-out).
- **B1** — `.contxignore` file merged with config's `ignore` list.
- **B2/B3/B4** (Claude-driven) — `/contx-bootstrap`, `/contx-explain`, `/contx-diagram`, `/contx-deploy-summary` slash commands. Replaced the earlier mechanical Python implementations.
- **C1** — Collapsed CLI to MCP + `serve` only. All workflows are now slash commands at `skills/contx/commands/contx-*.md` (`/contx-init`, `/contx-show`, `/contx-log`, `/contx-draft`, `/contx-ignore`, `/contx-export`, `/contx-install-hook`, `/contx-uninstall-hook`).
- Hardening pass: stderr for error messages, `ValueError` catches in CLI, defensive `read_entries` against corrupt JSONL.
- `__main__.py` coverage (`python -m contx version`).

## Deferred (intentional)

### Tuple vs list on `Entry.tags` / `Entry.related`

`@dataclass(frozen=True)` prevents reassignment but not in-place mutation of list fields. Switching to `tuple[str, ...]` would make immutability true at the value level. Breaking change for several call sites — bundle into a single dedicated PR when it's done.

### SessionStart auto-load for the Claude Code skill

`install.sh --skill` copies `SKILL.md` and the `contx-*` slash commands to `~/.claude/`. A SessionStart hook that detects `.contx/` in the project root and auto-loads the skill would close the loop, but requires modifying user-level Claude Code settings — kept explicit on purpose. Possible follow-up: `install.sh --auto-load` flag that writes the hook config.

### Negation patterns in `.contxignore`

Standard `.gitignore` supports `!path/to/include` to un-exclude. Not implemented — requires reworking the matcher to be ordered/two-pass rather than first-match.

### `contx blame <file>:<line>`

Mirror of `git blame` showing which contx entries reference a code region. Requires either an optional `line_range` field on `Entry` (schema change) or a `git blame`-derived heuristic at read time. Defer until requested.

### `contx_init` MCP tool

Spec §8.1 listed an MCP tool that would let an agent bootstrap a repo. Today `/contx-init` does this from Claude Code; non-Claude MCP hosts (Cursor, Windsurf, etc.) would need an equivalent slash-command file or this MCP tool. Revisit when a non-Claude host actually wants it.

### Team mode — conflict resolution at merge time

Two devs append rationales on different branches for the same symbol; merge silently concatenates. A `/contx-resolve` slash command + a tiny MCP tool for listing conflicts would close this. Not built yet.

### Rationale auto-summarization for long entry logs

When a file has 50+ entries the fold view gets noisy. `/contx-summarize` (Claude distills the log into a clean current-intent summary, raw history preserved) is the rough shape. Not built yet.

### Other MCP hosts (Cursor, Windsurf, Codex)

The MCP server already speaks the standard protocol. What's missing is per-host slash-command equivalents for the workflows, plus a small docs pass on how to wire each host. Mostly documentation work.

### IDE plugins (VS Code, JetBrains)

Inline "why is this here?" hover tooltips backed by the sidecar. Closes the loop for moments you're not in Claude Code. Separate repo, separate effort.

## Captured but no plan yet

None at this time.
