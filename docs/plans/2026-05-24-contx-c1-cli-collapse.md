# contx — Plan C1: Collapse CLI to MCP + `serve` only

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Drop every user-facing Python CLI command except `contx serve` and the hidden `contx _precommit-check` (still called by the git hook). Move all the workflows — `init`, `append`, `show`, `log`, `draft`, `ignore`, `export`, `install-hook`, `uninstall-hook`, `install-skill`, `uninstall-skill`, `bootstrap`, `bootstrap-deploy`, `diagram` — into Claude Code slash commands at `skills/contx/commands/`. The `/contx-init` slash command must prompt the user for the same options the terminal CLI did (hook? enforcement? granularity? deploy manifests?).

**Architecture after:**
- **Python**: storage primitives (`entry.py`, `paths.py`, `store.py`, `repo.py`, `config.py`, `ignore.py`, `search.py`), MCP server (`mcp_server.py`, `mcp_tools.py`), web UI (`web/`), pre-commit hook installer + `_precommit-check` subcommand, web-port helper.
- **Slash commands**: every user-facing workflow lives at `skills/contx/commands/contx-*.md`.
- **Removed**: `contx/drafting.py`, `contx/transcript.py`, `contx/skill_install.py`, `contx/bootstrap/`, `contx/summarizers/`, `contx/diagram/`. Plus all CLI commands except `version`, `serve`, `_precommit-check`.

**Tech Stack:** No new deps. Significant code deletion.

---

## Existing slash commands (do not rewrite, just verify)

- `skills/contx/commands/contx-bootstrap.md`
- `skills/contx/commands/contx-explain.md`
- `skills/contx/commands/contx-diagram.md`
- `skills/contx/commands/contx-deploy-summary.md`

## New slash commands to write

- `skills/contx/commands/contx-init.md` (interactive prompts)
- `skills/contx/commands/contx-show.md`
- `skills/contx/commands/contx-log.md`
- `skills/contx/commands/contx-draft.md`
- `skills/contx/commands/contx-ignore.md`
- `skills/contx/commands/contx-export.md`
- `skills/contx/commands/contx-install-hook.md`
- `skills/contx/commands/contx-uninstall-hook.md`

---

## Task 1: Write `/contx-init` slash command (interactive)

**File:** Create `skills/contx/commands/contx-init.md`

The slash command is a markdown file Claude reads. It must prompt the user with the same four questions the old terminal CLI did, then create `.contx/`, write `config.json`, install the pre-commit hook, and write `.contxignore`.

- [ ] **Step 1: Write the file**

```markdown
---
description: Initialize contx in the current git repo (interactive setup)
---

# /contx-init

You are setting up contx in the user's current git repository. Walk the user through these four questions in order, then perform the setup actions. Use `AskUserQuestion` for each.

## Question 1 — Pre-commit hook

Ask: "Install a pre-commit hook that blocks commits without paired context entries?"

Options:
- **Yes (recommended)** — every commit must include either a sidecar update or `--no-verify`
- **No** — track context but don't enforce at commit time

If the user picks **No**, skip Question 2 and use `require_context_on_commit = False`.

## Question 2 — Drift enforcement (only if hook is installed)

Ask: "When code is staged without a paired context entry, should the hook block the commit or just warn?"

Options:
- **Block (recommended)** — commit fails until context is added (or `--no-verify` is passed)
- **Warn-only** — commit succeeds, prints a warning

Save as `require_context_on_commit` (`True` for block, `False` for warn).

## Question 3 — Granularity

Ask: "What level of context do you want to track?"

Options:
- **Both file and symbol (recommended)** — file-level intent + per-function/class rationale
- **File only** — coarser, less to maintain
- **Symbol only** — finer, more entries

Save as `granularity` (`"both"` / `"file"` / `"symbol"`).

## Question 4 — Deployment manifests (multi-select)

Ask: "Which deployment manifests should contx track for drift?" (multiSelect: true)

Options:
- **Kubernetes** — adds `k8s/**/*.yaml` and `k8s/**/*.yml` with summarizer="kubernetes"
- **GitHub Actions** — adds `.github/workflows/*.yml` and `.github/workflows/*.yaml` with summarizer="github_actions"
- **docker-compose** — adds `docker-compose.yml`, `docker-compose.yaml`, `docker-compose.*.yml` with summarizer="docker_compose"
- **None** — track only source files

For each picked option, add the corresponding entries to the config's `tracked_paths` list.

## Perform the setup

Once all four answers are collected:

1. **Verify the repo is a git repo.** Run `git rev-parse --show-toplevel` to find the root. If it fails, tell the user this command needs a git repo and stop.

2. **Check if already initialized.** If `<repo>/.contx/config.json` exists, tell the user contx is already set up and ask whether to overwrite (default: no). On "no", exit. On "yes", proceed.

3. **Create `.contx/` and `config.json`.** Build the config dict with the user's answers. Defaults that don't come from prompts:
   - `languages`: `["py", "ts", "tsx", "js", "jsx", "go", "java", "kt", "rs", "rb", "php", "swift"]`
   - `ignore`: `["**/node_modules/**", "**/__tests__/**", "**/.venv/**", "**/venv/**", "**/dist/**", "**/build/**"]`
   - `require_rationale_on_create`: `true`
   - `extract_rationale_on_modify`: `true`
   - `tracked_paths`: derived from `languages` (one `{"glob": "**/*.<ext>", "kind": "source", "summarizer": null}` per language) plus any deploy entries from Question 4.

   Write JSON with `indent=2` plus trailing newline.

4. **Install the pre-commit hook** (only if Question 1 = Yes). Append the contx block to `<repo>/.git/hooks/pre-commit`, creating the file with `#!/bin/sh` shebang if it doesn't exist, marked between `# >>> contx pre-commit hook >>>` and `# <<< contx pre-commit hook <<<` sentinels. Make the hook executable (`chmod +x`). The block body:

   ```sh
   # Managed by contx — to remove, run /contx-uninstall-hook.
   if command -v contx >/dev/null 2>&1; then
       contx _precommit-check || exit 1
   fi
   ```

   Idempotence: if the sentinel is already in the file, don't append again.

5. **Write `.contxignore`** at the repo root if missing:

   ```
   # contx — paths to skip when tracking context.
   # Same syntax as .gitignore (subset).

   **/node_modules/**
   **/__tests__/**
   **/.venv/**
   **/venv/**
   **/dist/**
   **/build/**
   **/.contx/**
   ```

6. **Print a summary** of the choices:

   ```
   ✓ initialized contx at <repo>/.contx
   Settings:
     hook:        installed (block|warn) | skipped
     granularity: both | file | symbol
     deploy:      kubernetes, github-actions  (or "none")
   ```

7. **Suggest next step:** "Run `/contx-bootstrap` to generate v0 entries for the existing codebase, or just start editing — every change will pair with a contx_append from now on."

## Notes

- Do all file operations with the standard Write/Edit tools — no need to shell out except for `git rev-parse`.
- If any step fails, print the error and stop. Don't try to clean up partial state.
- Don't run `/contx-bootstrap` automatically — let the user choose.
```

- [ ] **Step 2: Smoke test the slash command end-to-end.** Open a fresh tmp git repo, invoke `/contx-init`, verify the answers shape the resulting `.contx/config.json`, hook file, and `.contxignore`. Manual verification — slash commands don't have a unit-test framework.

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/xeno/contx && git add skills/contx/commands/contx-init.md && git commit --no-verify -m "feat(skills): add /contx-init interactive slash command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Write the read-only slash commands

**Files:** Create six markdown files in `skills/contx/commands/`.

- [ ] **Step 1: `contx-show.md`**

```markdown
---
description: Print the folded current intent for a file or symbol
---

# /contx-show <ref>

`<ref>` is either `path/to/file.py` (file-level) or `path/to/file.py::Class.method` (symbol-level).

1. Call `contx_query` with the parsed file and optional symbol.
2. If the result has `file_intent` (file-level query): print the file path as a header, then the intent, then the list of symbols (each with its current rationale).
3. If the result has `symbol_intent` (symbol query): print `<file>::<symbol>` as the header, then the symbol's current rationale.
4. If nothing is recorded for the ref, print "no context for <ref>".

Keep the output compact. Use plain text, not markdown formatting (no `#` headers in the output — the user wants to read it in a terminal).
```

- [ ] **Step 2: `contx-log.md`**

```markdown
---
description: Print the full append-only log for a file or symbol
---

# /contx-log <ref>

1. Parse `<ref>` into file path + optional symbol.
2. Call `contx_query` to get the raw log.
3. For each entry in order, print:
   ```
   --- <timestamp> | <event> | <author> | <file>[::<symbol>]
   tags: <tags>     (only if non-empty)
   <rationale>
   <blank line>
   ```
4. If filtered by symbol, only show entries matching that symbol.
5. If no entries, print "no entries for <ref>".
```

- [ ] **Step 3: `contx-draft.md`**

```markdown
---
description: Interactively add context entries for drifted files (when pre-commit hook blocked you)
---

# /contx-draft

When the pre-commit hook blocked a commit, this command helps add the missing entries.

1. Run `contx _precommit-check` and capture its output. If the exit code is 0, tell the user "no drift — nothing to draft" and stop.
2. Parse the list of drifted files from the output (lines starting with `  - `).
3. For each drifted file:
   - Read the staged diff for that file (`git diff --cached -- <file>`).
   - Read what the user has been discussing in this Claude session about that file.
   - Propose a rationale (one or two sentences) that captures the *why* of the change — not the *what*.
   - Ask the user: "For `<file>`: I'll record `<rationale>`. Edit / accept / skip?"
   - On accept, call `contx_append` with `file=<path>`, `event="modified"`, `rationale=<final>`, and any tags that fit (`incident`, `compliance`, `security`, `performance`, etc.).
   - On edit, the user provides the corrected rationale.
   - On skip, move on.
4. After all files are handled, stage `.contx/` (`git add .contx/`) and tell the user to re-run `git commit`.

Tone: terse. Don't lecture. Don't ask "are you sure?" repeatedly. One pass through the files.
```

- [ ] **Step 4: `contx-ignore.md`**

```markdown
---
description: Append a gitignore-style pattern to .contxignore
---

# /contx-ignore <pattern>

1. Find the repo root via `git rev-parse --show-toplevel`.
2. Read `<repo>/.contxignore` if it exists.
3. If the pattern is already present (exact match, ignoring leading/trailing whitespace), tell the user "already present" and stop.
4. Otherwise append the pattern (with a leading newline if the file doesn't end in one) and tell the user the pattern was added.
```

- [ ] **Step 5: `contx-export.md`**

```markdown
---
description: Export the repo's intent map as a human-readable Markdown document
---

# /contx-export [--out PATH]

Default output: `<repo>/.contx/INTENT.md`.

1. Find the repo root.
2. Walk `<repo>/.contx/` looking for `*.jsonl` files (skip `config.json`).
3. For each sidecar, call `contx_query` for the corresponding source file.
4. Build a Markdown document:
   ```
   # contx intent map

   ## <source path>
   <file_intent if present>

   ### <symbol>
   <symbol intent>

   ### <symbol>
   <symbol intent>

   ## <next source path>
   ...
   ```
5. Write to the output path. Print "wrote <path>".

Only include sidecars that actually have entries. Skip empty ones.
```

- [ ] **Step 6: `contx-install-hook.md`**

```markdown
---
description: Install the contx pre-commit hook on an already-initialized repo
---

# /contx-install-hook

Idempotent. Same hook block as in `/contx-init`. Tell the user "installed at <path>" or "already installed".
```

- [ ] **Step 7: `contx-uninstall-hook.md`**

```markdown
---
description: Remove the contx pre-commit hook block (preserves any other content in the hook)
---

# /contx-uninstall-hook

1. Find `<repo>/.git/hooks/pre-commit`. If missing, print "no hook installed" and stop.
2. Strip the block between `# >>> contx pre-commit hook >>>` and `# <<< contx pre-commit hook <<<` (inclusive of the sentinels).
3. If what remains is empty or just the `#!/bin/sh` shebang, delete the file entirely.
4. Otherwise rewrite the file with the contx block removed.
5. Print "removed contx pre-commit hook block".
```

- [ ] **Step 8: Commit**

```bash
cd ~/Desktop/xeno/contx && git add skills/contx/commands/ && git commit --no-verify -m "feat(skills): add /contx-show, /contx-log, /contx-draft, /contx-ignore, /contx-export, /contx-install-hook, /contx-uninstall-hook

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Strip `contx/cli.py` to only `version`, `serve`, `_precommit-check`

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `pyproject.toml` (if `[project.scripts]` references removed entry points)

- [ ] **Step 1: Inventory the imports.** Open `contx/cli.py`. Identify which commands are removed:

  REMOVE: `init`, `append`, `show`, `log_cmd`, `draft`, `ignore_cmd`, `export`, `install_hook_cmd`, `uninstall_hook_cmd`, `install_skill_cmd`, `uninstall_skill_cmd`, `bootstrap`, `bootstrap_deploy`, `diagram`, plus their helpers (`_write_default_contxignore`, `_git_author`, `_is_tty`, `_source_repo_root`, `_claude_home_path`, etc. — only if not used elsewhere).

  KEEP: `version`, `serve`, `_precommit_check` (with `@app.command(name="_precommit-check", hidden=True)`).

- [ ] **Step 2: Rewrite `contx/cli.py`** as a minimal file. Here is the full new contents — replace everything in the file with this:

```python
"""contx CLI entry point — minimal surface: version, serve, _precommit-check.

All user-facing workflows (init, append, show, log, draft, ignore, export,
bootstrap, diagram, hook/skill management) live in Claude Code slash
commands at `skills/contx/commands/`. The Python CLI is intentionally tiny.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from contx import __version__
from contx.repo import NotInRepoError, find_repo_root, is_initialized

app = typer.Typer(help="contx — git for context", no_args_is_help=True)


def _resolve_repo() -> Path:
    try:
        return find_repo_root(Path.cwd())
    except NotInRepoError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)


@app.command()
def version() -> None:
    """Print contx version."""
    typer.echo(__version__)


@app.command()
def serve(
    port: int = typer.Option(4242, "--port", "-p", help="Port to bind (default 4242)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (default 127.0.0.1)"),
    strict_port: bool = typer.Option(False, "--strict-port", help="Fail if --port is occupied"),
) -> None:
    """Launch the read-only local web UI."""
    import uvicorn
    from contx.web.app import create_app, find_open_port

    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run /contx-init in Claude Code.", err=True)
        raise typer.Exit(code=2)

    actual_port = port
    if not strict_port:
        try:
            actual_port = find_open_port(port, host=host, attempts=10)
        except OSError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        if actual_port != port:
            typer.echo(f"port {port} is in use; using {actual_port} instead (pass --strict-port to fail loudly)")

    web_app = create_app(repo_root=repo)
    typer.echo(f"contx serving on http://{host}:{actual_port}")
    uvicorn.run(web_app, host=host, port=actual_port, log_level="warning")


@app.command(name="_precommit-check", hidden=True)
def _precommit_check() -> None:
    """Internal: invoked by the git pre-commit hook.

    Exits 0 if staged changes have paired context (or contx is not
    initialized, or enforcement is disabled). Exits 1 with a helpful
    message if drift is detected and `require_context_on_commit` is True.
    """
    from contx.config import load_config
    from contx.staging import compute_drift

    repo = _resolve_repo()
    drift = compute_drift(repo)

    if drift.uninitialized or not drift.missing:
        return

    cfg = load_config(repo)

    if cfg.require_context_on_commit:
        typer.echo("error: contx drift — the following files changed without a matching .contx/ entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        typer.echo("")
        typer.echo("Fix it from Claude Code:")
        typer.echo("  /contx-draft        # propose entries from the staged diff + conversation")
        typer.echo("  git commit          # re-run after .contx is auto-staged")
        typer.echo("")
        typer.echo("Bypass once:    git commit --no-verify")
        typer.echo("Disable entirely:  set 'require_context_on_commit': false in .contx/config.json")
        raise typer.Exit(code=1)
    else:
        typer.echo("warning: contx drift — these files changed without a context entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        return
```

- [ ] **Step 3: Update `tests/test_cli.py`** — delete every test for a removed command. Keep tests that exercise `version`, `serve` (help only is fine), and `_precommit-check`. The simplest path: replace the entire test file with a minimal version:

```python
"""Tests for the surviving CLI surface: version, serve, _precommit-check."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_version_prints_0_1_0():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_serve_help_lists_port_and_host():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()
    assert "host" in result.output.lower()
    assert "strict-port" in result.output.lower()


def test_serve_uninitialized_repo_errors(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 2
    assert "not initialized" in result.output.lower()


def test_precommit_check_uninitialized_repo_exits_zero(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0


def test_precommit_check_blocks_when_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from contx.config import default_config, save_config

    monkeypatch.chdir(tmp_repo)
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code != 0
    assert "src/foo.py" in result.output
    assert "context" in result.output.lower()


def test_precommit_check_passes_when_paired(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from contx.config import default_config, save_config

    monkeypatch.chdir(tmp_repo)
    save_config(tmp_repo, default_config())
    (tmp_repo / ".contx" / "src").mkdir(parents=True)
    (tmp_repo / ".contx" / "src" / "foo.py.jsonl").write_text('{"id":"x"}\n')
    subprocess.run(["git", "add", ".contx/src/foo.py.jsonl"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0
```

- [ ] **Step 4: `pyproject.toml`** — only one script entry should remain: `contx = "contx.cli:app"`. If `contx-mcp` is wired as a separate entry (`contx-mcp = "contx.mcp_server:main"`), keep it. Remove no scripts unless they reference removed code.

- [ ] **Step 5: Run the suite**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_cli.py -v
```

Expect a clean pass on the 6 tests above.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py pyproject.toml && git commit --no-verify -m "refactor(cli): strip CLI to version+serve+_precommit-check; workflows move to slash commands

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Delete orphan modules + their tests

**Files to delete (if present):**
- `contx/drafting.py` + `tests/test_drafting.py` (logic moved to /contx-draft)
- `contx/transcript.py` + `tests/test_transcript.py` (used only by old draft)
- `contx/skill_install.py` + `tests/test_skill_install.py` (install.sh handles this now)
- `contx/bootstrap/` (directory) + `tests/test_bootstrap_*.py`
- `contx/summarizers/` (directory) + `tests/test_summarizer_*.py`
- `contx/diagram/` (directory) + `tests/test_diagram_*.py`
- `tests/test_main_module.py` — keep, `__main__.py` still routes to the trimmed CLI
- `tests/test_precommit_e2e.py` — keep, exercises the real git hook flow
- `tests/test_e2e.py` — review; if it tests removed CLI commands, replace with a minimal MCP-server e2e test (or delete)

- [ ] **Step 1: Verify which of these actually exist** (`ls contx/ tests/`).
- [ ] **Step 2: Delete the files/directories that exist:**

```bash
cd ~/Desktop/xeno/contx
for f in contx/drafting.py contx/transcript.py contx/skill_install.py \
         tests/test_drafting.py tests/test_transcript.py tests/test_skill_install.py; do
  [ -e "$f" ] && git rm "$f"
done
for d in contx/bootstrap contx/summarizers contx/diagram; do
  [ -d "$d" ] && git rm -r "$d"
done
for f in tests/test_bootstrap_filter.py tests/test_bootstrap_repo.py tests/test_ast_python.py \
         tests/test_ast_dispatch.py tests/test_git_history.py \
         tests/test_summarizers_registry.py tests/test_summarizer_kubernetes.py \
         tests/test_summarizer_github_actions.py tests/test_summarizer_docker_compose.py \
         tests/test_diagram_graph.py tests/test_diagram_layout.py tests/test_diagram_drawio.py; do
  [ -e "$f" ] && git rm "$f"
done
```

- [ ] **Step 3: Inspect `tests/test_e2e.py`.** If it exercises the removed CLI commands (likely — it was the lifecycle smoke test), replace it with:

```python
"""End-to-end: MCP server + storage primitives lifecycle."""

import json
from datetime import datetime, timezone
from pathlib import Path

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.store import append_entry, fold_entries, read_entries


def test_full_storage_lifecycle(tmp_repo: Path):
    # Init
    save_config(tmp_repo, default_config())

    # File-level entry
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HFILE0000000000000000000",
        kind="file", symbol=None, event="created",
        rationale="Auth module — owns SSO + email login",
        tags=["module-purpose"], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    # Symbol creation
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HSYM10000000000000000000",
        kind="symbol", symbol="User.authenticate", event="created",
        rationale="Email-only because Legal said phone OTP fails GDPR",
        tags=["compliance", "gdpr"], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    # Symbol modified
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HSYM20000000000000000000",
        kind="symbol", symbol="User.authenticate", event="modified",
        rationale="Added rate limit — May incident burst attack",
        tags=["incident", "security"], author="t@x",
        timestamp=datetime(2026, 5, 22, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    entries = read_entries(tmp_repo, "src/auth/login.py")
    assert len(entries) == 3

    folded = fold_entries(entries)
    assert "Auth module" in (folded.file_intent or "")
    # Latest symbol rationale wins
    assert "May incident" in folded.symbols["User.authenticate"]
```

- [ ] **Step 4: Run the suite, confirm green:**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest -q
```

Expect the suite to be much smaller now (storage + MCP + web + precommit_e2e + main_module + e2e).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add -A && git commit --no-verify -m "refactor: delete orphan modules now that workflows are slash commands

Removed:
- contx/drafting.py, contx/transcript.py, contx/skill_install.py
- contx/bootstrap/, contx/summarizers/, contx/diagram/
- Tests for all of the above
- Replaced tests/test_e2e.py with a storage-primitives lifecycle test

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Update `install.sh` + `uninstall.sh`

**Files:** Modify `install.sh` and `uninstall.sh`.

The installer should:
1. Install the Python package (gives you `contx` + `contx-mcp` binaries with the trimmed CLI).
2. Copy `skills/contx/SKILL.md` and `skills/contx/commands/*.md` to `~/.claude/`.
3. Optionally register `contx-mcp` in `~/.claude/settings.json`.

The current installer already does this (it has `--skill` and `--mcp` flags) but it may reference `contx install-skill` which no longer exists. Audit and fix.

- [ ] **Step 1: Audit `install.sh`.** If any line calls a now-removed CLI command (e.g. `contx install-skill`), rewrite that step to do the file copy directly in bash. The skill files live at `skills/contx/SKILL.md` and `skills/contx/commands/*.md`; the destinations are `~/.claude/skills/contx/SKILL.md` and `~/.claude/commands/contx-*.md`.

- [ ] **Step 2: Audit `uninstall.sh` similarly.** Any call to `contx uninstall-skill` becomes direct file removal.

- [ ] **Step 3: Run a smoke check by hand:**

```bash
./install.sh --help && ./uninstall.sh --help
```

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add install.sh uninstall.sh && git commit --no-verify -m "refactor(install): inline skill+commands copy (no longer calls removed CLI)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Update README + SKILL.md

**Files:** Modify `README.md` and `skills/contx/SKILL.md`.

- [ ] **Step 1: README.** The "CLI commands" table currently lists all the removed commands. Replace with a minimal table:

```markdown
| Command | Purpose |
|---|---|
| `contx serve [--port 4242] [--host 127.0.0.1] [--strict-port]` | Launch the read-only local web UI. |
| `contx version` | Print version. |

Every other workflow — init, append, show, log, draft, ignore, export, bootstrap, diagram, hook management — lives in a Claude Code slash command at `~/.claude/commands/contx-*.md`. Type `/contx-` in Claude Code to discover them.
```

Also: any "Quickstart" section that uses `contx init` should be rewritten to use `/contx-init`.

- [ ] **Step 2: SKILL.md.** Open `skills/contx/SKILL.md`. Make sure the workflow documentation matches the slash-command surface (no references to old CLI commands). If "when the pre-commit hook blocks, run `contx draft`" appears, change to `/contx-draft`.

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/xeno/contx && git add README.md skills/contx/SKILL.md && git commit --no-verify -m "docs: reflect new minimal CLI + slash-command surface

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Final BACKLOG update + plan-doc commit

- [ ] **Step 1: BACKLOG.md.** Update the "Shipped" list:

```markdown
- C1 — Collapse CLI to MCP + `serve` only. All workflows are now Claude Code slash commands.
```

Remove the obsolete deferred items that no longer apply:
- "LLM-based rationale extraction in `contx draft --from-transcript`" — the slash command makes this irrelevant (Claude IS the LLM).
- "Wheel/PyPI install support for `contx install-skill`" — `contx install-skill` no longer exists.

- [ ] **Step 2: Commit the plan + BACKLOG**

```bash
cd ~/Desktop/xeno/contx && git add docs/BACKLOG.md docs/plans/2026-05-24-contx-c1-cli-collapse.md && git commit --no-verify -m "docs: BACKLOG update + Plan C1 file

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §"keep MCP + serve only" → Task 3 ✓
- §"move rest to slash commands" → Tasks 1, 2 ✓
- §"contx init prompts for hook/enforcement/granularity/deploy" → Task 1 ✓
- Orphan code removal → Task 4 ✓
- Installer/docs consistency → Tasks 5, 6 ✓

**Placeholders:** none.

**Type/name consistency:** `contx_query`, `contx_append`, `Entry`, `Config`, `compute_drift`, `find_open_port` — all referenced consistently across tasks.
