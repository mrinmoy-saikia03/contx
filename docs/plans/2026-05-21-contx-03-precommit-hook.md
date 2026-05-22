# contx — Plan 3: Pre-commit Hook + Drift Detection

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it mechanically hard to commit code changes without paired context updates. `contx init` installs a `pre-commit` hook in `.git/hooks/`. On `git commit`, the hook runs `contx _precommit-check`, which inspects the staged diff: if a tracked source file changed but its sidecar didn't, the commit is blocked with a clear message telling the user how to fix it. Users can bypass with `--no-verify` per commit or set `require_context_on_commit: false` in `.contx/config.json` to soft-warn instead of block.

**Architecture:** Three new modules. `contx/staging.py` is the pure-logic core — reads `git diff --cached --name-only` and computes drift. `contx/hooks.py` installs/uninstalls hooks (a small bash script that calls back into the CLI). A new hidden CLI subcommand `contx _precommit-check` is the integration point. `contx init` is extended to install the hook by default; a new `contx install-hook` command lets users add the hook to repos that were `init`'d before this plan.

**Scope discipline:** This plan does NOT mine the Claude conversation transcript for rationales — that's the harder workflow and is **deferred to Plan 3b (Backlog)**. Plan 3 ships the *gate* (drift detection + block). The current "fix" path is: user runs `contx append …` (or has their AI agent call `contx_append`), then re-runs `git commit`. That's already enough to be valuable.

**Tech Stack:** Python 3.11+, typer, pytest, the existing storage layer. Hook script is plain `sh`.

**Companion spec:** `docs/specs/2026-05-21-contx-design.md` §12 (Git Integration).

---

## File Structure

```
~/Desktop/xeno/contx/
├── contx/
│   ├── staging.py            # NEW: parse staged diff, compute drift
│   ├── hooks.py              # NEW: install/uninstall pre-commit hook
│   ├── config.py             # MODIFY: add `require_context_on_commit: bool`
│   ├── cli.py                # MODIFY: add `_precommit_check`, `install_hook`;
│   │                         #   extend `init` to install the hook
│   └── (entry, paths, repo, store, search, mcp_*: unchanged)
└── tests/
    ├── test_staging.py       # NEW
    ├── test_hooks.py         # NEW
    └── test_cli.py           # MODIFY: tests for new commands + init --no-hook
```

---

## Task 1: `staging.py` — compute drift from staged diff

**Goal:** A pure-Python module that, given a repo root, returns the list of staged source files that changed without a matching `.contx/` sidecar change. No git invocation lives in the test — we use a small wrapper that's mockable.

**Files:**
- Create: `contx/staging.py`
- Create: `tests/test_staging.py`

- [ ] **Step 1: Write failing tests**

`~/Desktop/xeno/contx/tests/test_staging.py`:

```python
import subprocess
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.staging import (
    Drift,
    compute_drift,
    list_staged_paths,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _write_and_stage(repo: Path, rel_path: str, content: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)


def test_list_staged_paths_returns_added_files(tmp_repo: Path):
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    paths = list_staged_paths(tmp_repo)
    assert "src/foo.py" in paths


def test_list_staged_paths_includes_contx_dir(tmp_repo: Path):
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    paths = list_staged_paths(tmp_repo)
    assert ".contx/src/foo.py.jsonl" in paths


def test_compute_drift_clean_when_both_staged(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    drift = compute_drift(tmp_repo)
    assert drift.missing == []


def test_compute_drift_flags_code_without_context(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    # No matching .contx/src/foo.py.jsonl staged
    drift = compute_drift(tmp_repo)
    assert "src/foo.py" in drift.missing


def test_compute_drift_respects_ignore_patterns(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    # default ignore includes **/node_modules/**
    _write_and_stage(tmp_repo, "node_modules/lib.js", "x")
    drift = compute_drift(tmp_repo)
    assert "node_modules/lib.js" not in drift.missing


def test_compute_drift_respects_language_filter(tmp_repo: Path):
    cfg = default_config()
    save_config(tmp_repo, cfg)
    # A file that is NOT in cfg.languages (e.g. README.md) should be ignored.
    _write_and_stage(tmp_repo, "README.md", "# hi")
    drift = compute_drift(tmp_repo)
    assert "README.md" not in drift.missing


def test_compute_drift_uninitialized_returns_clean(tmp_repo: Path):
    # No config.json → cannot enforce drift → treat as clean.
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    drift = compute_drift(tmp_repo)
    assert drift.missing == []
    assert drift.uninitialized is True


def test_compute_drift_pairs_sidecar_to_source(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    # Stage ONLY the sidecar, not the source. This is unusual but should not error.
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    drift = compute_drift(tmp_repo)
    assert drift.missing == []
```

- [ ] **Step 2: Run, verify failure**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_staging.py -v
```

Expected: `ModuleNotFoundError: No module named 'contx.staging'`.

- [ ] **Step 3: Implement `~/Desktop/xeno/contx/contx/staging.py`**

```python
"""Compute drift between staged code changes and staged contx sidecars."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from contx.config import load_config
from contx.paths import CTX_DIR, SIDECAR_SUFFIX


@dataclass(frozen=True)
class Drift:
    """Result of comparing staged source changes with staged sidecar changes."""
    missing: list[str] = field(default_factory=list)  # source rels with no paired sidecar
    uninitialized: bool = False                       # True iff .contx/config.json missing


def list_staged_paths(repo_root: Path) -> list[str]:
    """Return all staged file paths relative to repo root.

    Includes added, modified, renamed. Uses --diff-filter=ACMRT to avoid
    deletes (which can't have a paired context entry — deletes are tracked
    via contx_delete tool calls instead).
    """
    out = subprocess.run(
        [
            "git", "-C", str(repo_root),
            "diff", "--cached", "--name-only",
            "--diff-filter=ACMRT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    """Simple ** glob match, segment-based to handle `**/dir/**`."""
    # Reuse the segment-based logic from contx.mcp_tools._is_ignored.
    from fnmatch import fnmatchcase
    parts = rel_path.split("/")
    for pat in patterns:
        pat_parts = pat.split("/")
        if _segments_match(parts, pat_parts):
            return True
    return False


def _segments_match(parts: list[str], pat_parts: list[str]) -> bool:
    """Recursive ** matcher."""
    from fnmatch import fnmatchcase
    if not pat_parts:
        return not parts
    head, *rest = pat_parts
    if head == "**":
        if not rest:
            return True
        for i in range(len(parts) + 1):
            if _segments_match(parts[i:], rest):
                return True
        return False
    if not parts:
        return False
    if fnmatchcase(parts[0], head):
        return _segments_match(parts[1:], rest)
    return False


def compute_drift(repo_root: Path) -> Drift:
    """Compare staged source files against staged sidecar files.

    Returns Drift describing missing sidecars. If `.contx/` is not yet
    initialized, returns Drift(uninitialized=True) and an empty missing list
    (we don't enforce on uninitialized repos).
    """
    try:
        cfg = load_config(repo_root)
    except FileNotFoundError:
        return Drift(missing=[], uninitialized=True)

    extensions = {f".{ext}" for ext in cfg.languages}
    ignore = cfg.ignore

    staged = list_staged_paths(repo_root)
    staged_sidecars = {p for p in staged if p.startswith(f"{CTX_DIR}/") and p.endswith(SIDECAR_SUFFIX)}

    # Compute the set of source paths whose sidecar is staged.
    paired_sources: set[str] = set()
    for sc in staged_sidecars:
        # Strip leading .contx/ and trailing .jsonl
        inner = sc[len(CTX_DIR) + 1 :]
        if inner.endswith(SIDECAR_SUFFIX):
            paired_sources.add(inner[: -len(SIDECAR_SUFFIX)])

    missing: list[str] = []
    for p in staged:
        if p.startswith(f"{CTX_DIR}/"):
            continue  # skip sidecars themselves
        ext = Path(p).suffix
        if ext not in extensions:
            continue  # not a tracked language
        if _matches_any(p, ignore):
            continue
        if p in paired_sources:
            continue
        missing.append(p)

    return Drift(missing=missing, uninitialized=False)
```

- [ ] **Step 4: Run, verify 8 tests pass**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_staging.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/staging.py tests/test_staging.py && git commit -m "feat(staging): compute drift between staged code and contx sidecars

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Extend `Config` with `require_context_on_commit`

**Files:**
- Modify: `contx/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `~/Desktop/xeno/contx/tests/test_config.py`:

```python
def test_default_config_requires_context_on_commit():
    cfg = default_config()
    assert cfg.require_context_on_commit is True


def test_config_can_disable_commit_enforcement(tmp_repo: Path):
    cfg = Config(
        granularity="both",
        languages=["py"],
        ignore=[],
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
        require_context_on_commit=False,
    )
    save_config(tmp_repo, cfg)
    loaded = load_config(tmp_repo)
    assert loaded.require_context_on_commit is False
```

- [ ] **Step 2: Run, verify failure**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_config.py -v
```

Expected: `TypeError: Config.__init__() got an unexpected keyword argument 'require_context_on_commit'`.

- [ ] **Step 3: Extend the `Config` dataclass**

In `~/Desktop/xeno/contx/contx/config.py`, add the new field. The class must remain `@dataclass(frozen=True)`. To avoid breaking the old JSON files (config.json from earlier inits), `load_config` should default the new field to `True` when absent.

Update the dataclass:
```python
@dataclass(frozen=True)
class Config:
    granularity: Granularity
    languages: list[str]
    ignore: list[str]
    require_rationale_on_create: bool
    extract_rationale_on_modify: bool
    require_context_on_commit: bool = True
    # ... post_init unchanged
```

Update `default_config()` to pass the new field (it already defaults to True, so no change needed in the constructor call — but be explicit for clarity):
```python
def default_config() -> Config:
    return Config(
        granularity="both",
        languages=list(DEFAULT_LANGUAGES),
        ignore=list(DEFAULT_IGNORE),
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
        require_context_on_commit=True,
    )
```

Update `load_config` to handle older config.json files without the new field:
```python
def load_config(repo_root: Path) -> Config:
    p = _config_path(repo_root)
    if not p.is_file():
        raise FileNotFoundError(f"No contx config at {p}. Run `contx init` first.")
    data = json.loads(p.read_text())
    return Config(
        granularity=data["granularity"],
        languages=list(data["languages"]),
        ignore=list(data["ignore"]),
        require_rationale_on_create=bool(data["require_rationale_on_create"]),
        extract_rationale_on_modify=bool(data["extract_rationale_on_modify"]),
        require_context_on_commit=bool(data.get("require_context_on_commit", True)),
    )
```

- [ ] **Step 4: Run tests**

Expected: 7 config tests pass (5 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/config.py tests/test_config.py && git commit -m "feat(config): add require_context_on_commit flag (default True)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `contx _precommit-check` CLI subcommand

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

This is the integration point the hook script calls. Hidden from `--help` via `hidden=True`.

- [ ] **Step 1: Append tests to `tests/test_cli.py`**

```python
def test_precommit_check_passes_when_no_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    # Stage a contx entry, no code change
    (tmp_repo / ".contx" / "src" / "foo.py.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_repo / ".contx" / "src" / "foo.py.jsonl").write_text('{"id":"x"}\n')
    subprocess.run(["git", "add", ".contx/src/foo.py.jsonl"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0


def test_precommit_check_blocks_when_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code != 0
    assert "src/foo.py" in result.output
    assert "context" in result.output.lower()


def test_precommit_check_soft_warns_when_disabled(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    import json
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    # Flip the flag to False
    cfg_path = tmp_repo / ".contx" / "config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["require_context_on_commit"] = False
    cfg_path.write_text(json.dumps(cfg))
    # Stage a code file
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    # Exit 0 (soft warn), but warning message present
    assert result.exit_code == 0
    assert "warning" in result.output.lower()


def test_precommit_check_passes_on_uninitialized(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    # NO contx init
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run, verify failure**

Expected: `No such command '_precommit-check'`.

- [ ] **Step 3: Add the command to `~/Desktop/xeno/contx/contx/cli.py`**

Append:

```python


from contx.staging import compute_drift


@app.command(name="_precommit-check", hidden=True)
def _precommit_check() -> None:
    """Internal: invoked by the pre-commit hook.

    Exits 0 if staged changes have paired context (or contx is not
    initialized, or enforcement is disabled). Exits 1 with a helpful
    message if drift is detected and `require_context_on_commit` is True.
    """
    repo = _resolve_repo()
    drift = compute_drift(repo)

    if drift.uninitialized:
        # Nothing to enforce.
        return

    if not drift.missing:
        return

    # Read enforcement flag
    from contx.config import load_config
    cfg = load_config(repo)

    if cfg.require_context_on_commit:
        typer.echo("error: contx drift — the following files changed without a matching .contx/ entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        typer.echo("")
        typer.echo("Fix: add a contx entry for each file, then re-stage and re-commit.")
        typer.echo("Example:")
        typer.echo(f"  contx append --ref {drift.missing[0]} --event modified --rationale 'why this changed'")
        typer.echo("  git add .contx/")
        typer.echo("  git commit")
        typer.echo("")
        typer.echo("To bypass once: git commit --no-verify")
        typer.echo("To disable enforcement: set 'require_context_on_commit': false in .contx/config.json")
        raise typer.Exit(code=1)
    else:
        typer.echo("warning: contx drift — these files changed without a context entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        # Soft warn: still exit 0
        return
```

- [ ] **Step 4: Verify tests pass**

Expected: all cli tests pass (prior + 4 new).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): add hidden _precommit-check subcommand

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `contx/hooks.py` — install/uninstall

**Files:**
- Create: `contx/hooks.py`
- Create: `tests/test_hooks.py`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pytest

from contx.hooks import (
    HOOK_SENTINEL,
    install_pre_commit_hook,
    is_pre_commit_hook_installed,
    uninstall_pre_commit_hook,
)


def test_install_creates_hook_file(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    assert HOOK_SENTINEL in hook.read_text()
    # Must be executable
    assert hook.stat().st_mode & 0o111


def test_install_is_idempotent(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    install_pre_commit_hook(tmp_repo)  # No error
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    # Sentinel should appear exactly once
    assert hook.read_text().count(HOOK_SENTINEL) == 1


def test_install_preserves_existing_hook(tmp_repo: Path):
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho user-hook\n")
    hook.chmod(0o755)
    install_pre_commit_hook(tmp_repo)
    content = hook.read_text()
    assert "echo user-hook" in content
    assert HOOK_SENTINEL in content


def test_is_installed_reports_correctly(tmp_repo: Path):
    assert is_pre_commit_hook_installed(tmp_repo) is False
    install_pre_commit_hook(tmp_repo)
    assert is_pre_commit_hook_installed(tmp_repo) is True


def test_uninstall_removes_contx_block(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    uninstall_pre_commit_hook(tmp_repo)
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        assert HOOK_SENTINEL not in hook.read_text()


def test_uninstall_keeps_user_hook(tmp_repo: Path):
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho user-hook\n")
    hook.chmod(0o755)
    install_pre_commit_hook(tmp_repo)
    uninstall_pre_commit_hook(tmp_repo)
    assert hook.exists()
    content = hook.read_text()
    assert "echo user-hook" in content
    assert HOOK_SENTINEL not in content
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `~/Desktop/xeno/contx/contx/hooks.py`**

```python
"""Install and uninstall the contx pre-commit hook.

The hook is a short sh script that calls `contx _precommit-check`. We
append it to any existing pre-commit hook (rather than replacing) to play
nicely with other tooling like pre-commit framework, husky, etc.

Idempotence is detected by a sentinel line we insert around our block.
"""

from __future__ import annotations

import stat
from pathlib import Path

HOOK_SENTINEL = "# >>> contx pre-commit hook >>>"
HOOK_END_SENTINEL = "# <<< contx pre-commit hook <<<"

HOOK_BLOCK = f"""\

{HOOK_SENTINEL}
# Managed by `contx init` — to remove, run `contx uninstall-hook`.
if command -v contx >/dev/null 2>&1; then
    contx _precommit-check || exit 1
fi
{HOOK_END_SENTINEL}
"""

HOOK_SHEBANG = "#!/bin/sh\n"


def _hook_path(repo_root: Path) -> Path:
    return repo_root / ".git" / "hooks" / "pre-commit"


def is_pre_commit_hook_installed(repo_root: Path) -> bool:
    hook = _hook_path(repo_root)
    if not hook.is_file():
        return False
    return HOOK_SENTINEL in hook.read_text()


def install_pre_commit_hook(repo_root: Path) -> Path:
    """Install (or top-up) the contx block in .git/hooks/pre-commit.

    Idempotent. Preserves any existing hook content.
    Returns the hook path.
    """
    hook = _hook_path(repo_root)
    hook.parent.mkdir(parents=True, exist_ok=True)

    existing = hook.read_text() if hook.is_file() else ""

    if HOOK_SENTINEL in existing:
        return hook  # already installed

    if not existing:
        new_content = HOOK_SHEBANG + HOOK_BLOCK
    else:
        # Append our block to the existing hook
        if not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + HOOK_BLOCK

    hook.write_text(new_content)
    # Ensure executable
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def uninstall_pre_commit_hook(repo_root: Path) -> None:
    """Strip the contx block from .git/hooks/pre-commit.

    If after removal the hook is just a shebang or empty, delete the file.
    """
    hook = _hook_path(repo_root)
    if not hook.is_file():
        return
    content = hook.read_text()
    if HOOK_SENTINEL not in content:
        return

    lines = content.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == HOOK_SENTINEL:
            skipping = True
            continue
        if line.strip() == HOOK_END_SENTINEL:
            skipping = False
            continue
        if not skipping:
            out.append(line)

    stripped = "".join(out).rstrip()
    if not stripped or stripped == HOOK_SHEBANG.rstrip():
        hook.unlink()
        return
    hook.write_text(stripped + "\n")
```

- [ ] **Step 4: Verify 6 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/hooks.py tests/test_hooks.py && git commit -m "feat(hooks): add install/uninstall for the pre-commit hook

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Wire the hook installer into `contx init` + new `install-hook` / `uninstall-hook` commands

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Update tests for `init` behavior**

Append to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
def test_init_installs_hook_by_default(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()


def test_init_skips_hook_with_flag(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-hook"])
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert not hook.is_file()


def test_install_hook_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-hook"])
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()


def test_uninstall_hook_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["uninstall-hook"])
    assert result.exit_code == 0
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    # File should be gone (no other hook content)
    assert not hook.is_file()
```

- [ ] **Step 2: Run, verify some tests fail**

- [ ] **Step 3: Update `init` and add the two new commands in `cli.py`**

Modify the existing `init` command:

```python
@app.command()
def init(
    no_hook: bool = typer.Option(False, "--no-hook", help="Skip installing the pre-commit hook"),
) -> None:
    """Initialize contx for the current git repo."""
    repo = _resolve_repo()
    if is_initialized(repo):
        typer.echo(f"contx already initialized at {repo / '.contx'}")
        if not no_hook and not is_pre_commit_hook_installed(repo):
            install_pre_commit_hook(repo)
            typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")
        return
    save_config(repo, default_config())
    typer.echo(f"initialized contx at {repo / '.contx'}")
    if not no_hook:
        install_pre_commit_hook(repo)
        typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")
```

Add at the top of the file (with other imports):
```python
from contx.hooks import (
    install_pre_commit_hook,
    is_pre_commit_hook_installed,
    uninstall_pre_commit_hook,
)
```

Add two new commands:

```python
@app.command(name="install-hook")
def install_hook_cmd() -> None:
    """Install the contx pre-commit hook in the current repo."""
    repo = _resolve_repo()
    install_pre_commit_hook(repo)
    typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")


@app.command(name="uninstall-hook")
def uninstall_hook_cmd() -> None:
    """Remove the contx pre-commit hook from the current repo."""
    repo = _resolve_repo()
    uninstall_pre_commit_hook(repo)
    typer.echo("removed contx pre-commit hook")
```

- [ ] **Step 4: Verify all tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): install pre-commit hook in init + add install-hook / uninstall-hook

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: End-to-end test — real `git commit` is blocked

**Files:**
- Create: `tests/test_precommit_e2e.py`

- [ ] **Step 1: Write the e2e test**

```python
"""End-to-end: real `git commit` with the contx hook installed."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def test_real_commit_blocked_without_context(tmp_repo: Path):
    # Install contx via the CLI binary in the venv
    venv_bin = Path(sys.executable).parent
    contx = str(venv_bin / "contx")

    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)

    # Stage a source file without a sidecar
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")

    # Attempt to commit — should fail
    result = _git(tmp_repo, "commit", "-m", "no context", check=False)
    assert result.returncode != 0
    assert "drift" in (result.stdout + result.stderr).lower() or "context" in (result.stdout + result.stderr).lower()


def test_real_commit_succeeds_with_context(tmp_repo: Path):
    venv_bin = Path(sys.executable).parent
    contx = str(venv_bin / "contx")

    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)

    # Create file and add a contx entry for it via the CLI
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(
        [
            contx, "append",
            "--ref", "src/foo.py",
            "--event", "created",
            "--rationale", "test scaffold",
        ],
        cwd=tmp_repo, check=True, capture_output=True,
    )
    _git(tmp_repo, "add", "src/foo.py", ".contx/")

    result = _git(tmp_repo, "commit", "-m", "with context", check=False)
    assert result.returncode == 0, result.stderr


def test_no_verify_bypasses_hook(tmp_repo: Path):
    venv_bin = Path(sys.executable).parent
    contx = str(venv_bin / "contx")
    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")
    result = _git(tmp_repo, "commit", "-m", "bypass", "--no-verify", check=False)
    assert result.returncode == 0
```

- [ ] **Step 2: Run the test**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_precommit_e2e.py -v
```

Expected: 3 PASS. If any fail, the hook install or the drift logic has a bug — debug from the actual `git commit` stderr.

- [ ] **Step 3: Run full suite, commit**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest -v
```

Expected: ~97 tests pass (80 from Plan 2 + ~17 from Plan 3).

```bash
cd ~/Desktop/xeno/contx && git add tests/test_precommit_e2e.py && git commit -m "test(precommit): add real git commit e2e tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append a "Pre-commit hook" section**

Append to `~/Desktop/xeno/contx/README.md`:

```markdown

## Pre-commit hook

`contx init` installs a `pre-commit` hook in `.git/hooks/pre-commit` (use `--no-hook` to opt out). The hook blocks any commit where a tracked source file changed but its `.contx/` sidecar didn't.

Example:

\`\`\`
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
\`\`\`

### Bypass

- **One commit:** `git commit --no-verify`
- **Whole repo:** set `"require_context_on_commit": false` in `.contx/config.json` to convert the block into a soft warning.

### Manage the hook

- `contx install-hook` — install (or top up) the hook on a repo that wasn't `init`'d with it.
- `contx uninstall-hook` — remove the contx block (preserves other content in the hook).
```

- [ ] **Step 2: Commit**

```bash
cd ~/Desktop/xeno/contx && git add README.md && git commit -m "docs: document pre-commit hook behavior and bypass options

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 3):**
- §12 Git Integration — Tasks 1–6 ✓
  - Pre-commit hook installed by `contx init` (Task 5) ✓
  - Hook scans staged code changes, cross-references staged `.contx/` (Tasks 1, 3) ✓
  - Drift detection respects `languages` + `ignore` config (Task 1) ✓
  - Bypass via `--no-verify` (Task 6 test) and config flag (Task 2, 3) ✓
- §7.2 Commit-time extraction — **deferred to Plan 3b** (conversation-transcript mining). This plan ships the gate; Plan 3b ships the auto-extraction. The current "fix" is manual: user runs `contx append`, re-stages, re-commits.

**Placeholder scan:** no TBDs. Every step has real code or shell commands.

**Type consistency:** `Drift` dataclass, `compute_drift`, `Config.require_context_on_commit`, `HOOK_SENTINEL`, `install_pre_commit_hook` — all named and used consistently across modules.

**Risk:** The e2e test (Task 6) calls the actual `contx` binary from the venv. If the venv path resolution is fragile across systems, the test may flake. Mitigation: the test uses `sys.executable`'s parent to locate the binary, which is the standard pattern.

---

## What ships after Plan 3

`contx` becomes self-enforcing: once installed in a repo, code changes cannot land without an accompanying context entry (unless the user explicitly opts out per-commit or globally). The combined system is now:

- **CLI** (Plan 1) — humans write context manually.
- **MCP server** (Plan 2) — AI agents write context as they edit.
- **Pre-commit hook** (Plan 3) — git itself enforces the pairing.

A user could go all-in: install the hook, run Claude Code with the MCP server, and the AI will be physically unable to land code without context. That's the wedge.

---

## Plan 3b (Backlog — not in this plan)

Auto-extract rationales from Claude Code session transcripts at commit time. Open the editor (like `git commit -e`) with draft entries the user can edit/approve. This depends on:
- Knowing where Claude Code writes session transcripts (path varies by version).
- A reliable way to identify which transcript matches the current commit (timestamp window? PID?).
- An LLM call to mine "the user told me to do X" patterns.

Defer to a focused Plan 3b once Plan 3's gate is shipping value on its own.

---

## Plan 4 preview

Claude Code skill that loads on session start when `.contx/` is detected. Enforces (via the skill's prompt rules) that the agent calls `contx_query` before editing and `contx_append` after editing. Lives entirely in `~/.claude/skills/contx/SKILL.md`; no Python changes needed in this repo.
