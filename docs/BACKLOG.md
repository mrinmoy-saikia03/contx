# contx — Backlog

Items deferred from spec/plans, to revisit before or alongside future plans.

## Features

### `.contxignore` file (gitignore-style)

**Goal:** Per-repo ignore file at the repo root that lets users exclude paths from context tracking — independent of `.contx/config.json`'s `ignore` field.

**Why both:** `config.json`'s `ignore` is project-wide defaults (set once at `contx init`); `.contxignore` is for paths the team wants every contributor to skip (build artifacts, vendored code, generated files). Same split as `.gitignore` vs git's global ignore.

**Behavior:**
- Located at repo root (next to `.git/`), gitignore syntax (negation `!`, globs, comments).
- Loaded by `contx_query`, `contx_audit`, the CLI commands, and the future MCP server.
- A file matching `.contxignore` is treated as if it has no sidecar — operations silently no-op rather than create entries.
- AI agents (Plan 4 skill) check `.contxignore` before calling `contx_append`.

**Implementation surface:**
- New `contx/ignore.py` — parse + match (use `pathspec` library, gitignore-compatible).
- `contx/store.py` — `is_ignored(repo_root, source_rel_path)` gate before `append_entry`.
- CLI `init` — create `.contxignore` with sensible default block (already present in `config.json`'s `DEFAULT_IGNORE`).
- MCP tools (Plan 2) — `contx_append` should return a clear "ignored" status rather than appending.

**Captured:** 2026-05-21 (user request during Plan 1 wrap-up).

---

## Hardening items from Plan 1 final review

These were flagged "approved with required pre-Plan-2 fixes" by the code reviewer. Bundle into one hardening commit before Plan 2.

1. **Error messages to stderr** — `typer.echo(f"error: …", err=True)` in all CLI error paths. CliRunner's default `mix_stderr=True` will still capture them in test `result.stdout` if needed.
2. **Catch `ValueError` in `cli.append`** — wrap `Entry(...)` construction in try/except; convert to user-friendly CLI error + `Exit(code=2)`.
3. **Defensive `read_entries`** — skip + warn on corrupt JSONL lines rather than raising. Add a test for a sidecar with one good line and one malformed line.

## Minor cleanup

- Move `from dataclasses import dataclass, field` to the top of `store.py` (currently mid-file from incremental TDD).
- Decide `tuple` vs `list` for `Entry.tags`/`Entry.related` before Plan 2's MCP layer bakes in expectations. `tuple` makes the "Immutable by design" docstring claim actually true.
- Add coverage for `contx/__main__.py` (currently 0% — trivial subprocess test).
- Add coverage for whitespace-only rationale rejection (`entry.py` line 52).
- Guard `sidecar_path_for_source` against source paths whose first component is `.contx` (closes a Plan-2 MCP foot-gun).

## Future ideas (not committed, just noted)

- `contx blame <file>:<line>` — show which entries reference a specific code region.
- `contx export --format markdown` for onboarding docs (already in spec §10, deferred from Plan 1).
- `contx import` from existing comment-based intent tracking (TODO comments, docstrings).
