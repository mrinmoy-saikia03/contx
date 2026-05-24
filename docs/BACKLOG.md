# contx — Backlog

Items deferred from spec/plans, with current status.

## Shipped

- Plan 1 — Storage core + CLI.
- Plan 2 — MCP server with 6 tools.
- Plan 3 — Pre-commit hook + drift detection.
- Plan 3b — `contx draft` interactive command.
- Plan 4 — Claude Code skill + installer.
- Plan 5 — Local read-only web UI.
- B1 — `.contxignore` file with config merge.
- B2 — Bootstrap from git history + Python AST.
- B3 — Deployment-manifest awareness (k8s, GitHub Actions, docker-compose) + `tracked_paths` schema + `contx bootstrap-deploy`.
- B4 — File-level diagrams as draw.io XML.
- Hardening pass (stderr errors, ValueError catches, defensive read_entries).
- Port auto-fallback in `contx serve` (with `--strict-port` opt-out).
- `__main__.py` coverage.
- `contx ignore <pattern>` convenience command.
- `contx export --format markdown`.

## Deferred (intentional)

### Tuple vs list on Entry.tags / Entry.related

`@dataclass(frozen=True)` prevents reassignment but not in-place mutation of list fields. Switching to `tuple[str, ...]` would make immutability true at the value level. Breaking change for many call sites — bundle into a single dedicated PR when it's done.

### SessionStart auto-load for the Claude Code skill

`contx install-skill` copies `SKILL.md` to `~/.claude/skills/contx/`. A SessionStart hook that detects `.contx/` in the project root and auto-loads the skill would close the loop, but requires modifying user-level Claude Code settings — kept explicit on purpose. Possible follow-up: `contx install-skill --auto-load` flag that writes the hook config.

### LLM-based rationale extraction in `contx draft --from-transcript`

Today this uses pure heuristics (sentence proximity to file mentions). An LLM call using the user's own `ANTHROPIC_API_KEY` would give higher-quality drafts. Adds a real dependency on a third-party API; only worth doing if heuristic drafts prove insufficient.

### Negation patterns in `.contxignore`

Standard `.gitignore` supports `!path/to/include` to un-exclude. Not implemented — requires reworking the matcher to be ordered/two-pass rather than first-match.

### `contx blame <file>:<line>`

Mirror of `git blame` showing which contx entries reference a code region. Requires either an optional `line_range` field on `Entry` (schema change) or a `git blame`-derived heuristic at read time. Defer until requested.

### `contx_init` MCP tool

Listed in the design spec §8.1 but skipped — the CLI `contx init` handles repo setup and there's no AI-driven workflow that needs it. Revisit if an MCP host wants to bootstrap a repo programmatically.

### Wheel/PyPI install support for `contx install-skill`

`_source_repo_root()` currently walks up from `contx.__file__` to find `skills/contx/SKILL.md`. Works for `pip install -e .`; a wheel install would need `skills/` in `package_data` and `importlib.resources` to locate. Not blocking until the project is published to PyPI.

## Captured but no plan yet

None at this time.
