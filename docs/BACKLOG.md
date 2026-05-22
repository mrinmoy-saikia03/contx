# contx — Backlog

Items deferred from spec/plans, with current status.

## Shipped

- **Plan 1** — Storage core + CLI (`init`, `append`, `show`, `log`, `version`).
- **Plan 2** — MCP server (`contx-mcp`) exposing 6 tools: `contx_query`, `contx_append`, `contx_search`, `contx_rename`, `contx_delete`, `contx_audit`.
- **Plan 3** — Pre-commit hook with drift detection + `--no-hook` opt-out + `install-hook`/`uninstall-hook` commands + soft-warn config flag.
- **Plan 3b** — `contx draft` interactive editor + `--from-transcript` heuristic mining of Claude Code session transcripts.
- **Plan 4** — Claude Code skill at `skills/contx/SKILL.md` + `contx install-skill`/`uninstall-skill`.
- **Plan 5** — Local read-only web UI via `contx serve` (FastAPI + Jinja2 + htmx). Routes: `/`, `/file/<path>`, `/symbol/<ref>`, `/search?q=`, `/timeline`.
- **B1** — `.contxignore` file (gitignore-style) at the repo root; `init` writes a starter; merged with `config.json`'s `ignore`; respected by staging drift detection and `contx_audit`.
- **Plan 1 hardening pass** — stderr for error messages; ValueError catches in CLI; defensive `read_entries` against corrupt JSONL lines.

## Pending — small, non-blocking

### Immutability — tuple vs list on `Entry.tags` / `Entry.related`

`@dataclass(frozen=True)` prevents reassignment but not in-place mutation of list fields. Switching to `tuple[str, ...]` makes the immutability claim true at the value level. Breaking change for any external consumer of these fields (currently only the MCP/CLI/Web layers in this same repo) — touch all call sites in one PR. Probably a 30-minute change.

### `__main__.py` test coverage

Currently 0%. Add one subprocess test that runs `python -m contx version` and asserts `0.1.0` in stdout.

### SessionStart auto-load for the Claude Code skill

Right now `contx install-skill` copies `SKILL.md` to `~/.claude/skills/contx/`. The user has to invoke `/contx` to activate it. A SessionStart hook that detects `.contx/` in the project root and loads the skill automatically would close the loop — but it requires modifying user-level Claude Code settings, which we left explicit on purpose. Optional `contx install-skill --auto-load` could write the hook config; keep behind a flag.

### LLM-based rationale extraction in `contx draft`

`--from-transcript` currently uses pure heuristics (sentence-level proximity to file mentions). An LLM call to the user's own API key would give better-quality drafts. Requires:
- An `ANTHROPIC_API_KEY` env var
- A prompt that takes the diff + transcript + file list and returns one rationale per file
- Graceful fallback to heuristics when the key isn't set or the call fails

Probably worth doing only if heuristic drafts prove insufficient in practice.

### Negation patterns in `.contxignore`

Standard gitignore supports `!path/to/include` to undo an earlier exclude. Not implemented yet — currently `.contxignore` is exclude-only. Add if a real use case appears.

### `contx ignore <pattern>` CLI

Convenience command to append a pattern to `.contxignore` from the shell without opening an editor. Trivial — only if there's demand.

### `contx blame <file>:<line>` (stretch)

Mirror of `git blame` that shows which contx entries reference a code region. Requires linking entries to line ranges, which is currently NOT in the data model — entries attach to symbols, not lines. Either:
- Add an optional `line_range` field to `Entry` (breaking schema change), or
- Compute a heuristic mapping via `git blame` + symbol bounds at read time (slower, no schema change).

Defer until someone asks for it.

### `contx export --format markdown`

Mentioned in spec §10. Generates a single human-readable doc summarizing the repo's intent for onboarding. Useful but not blocking.

### `contx_init` MCP tool

Spec §8.1 lists this. Skipped because the CLI `contx init` already handles repo setup and there's no AI-driven workflow that needs it. Leave deferred — revisit if an MCP host wants to bootstrap a repo programmatically.

### Wheel/PyPI install support for `contx install-skill`

The current `_source_repo_root()` walks up from `contx.__file__` to find `skills/contx/SKILL.md`. This works for editable installs (`pip install -e .`). A wheel install won't include the `skills/` directory unless we add it to `package_data` in `pyproject.toml` and switch to `importlib.resources`. Not blocking until the project is published to PyPI.

## Captured but no plan yet

(None at this time — everything user-requested has either shipped or has a backlog entry above.)
