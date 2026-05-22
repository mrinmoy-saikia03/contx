# contx — Backlog Plan B1: `.contxignore` file

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Add a `.contxignore` file at the repo root (gitignore-style syntax) that lets users exclude paths from contx tracking independent of `.contx/config.json`'s `ignore` field. The two sources are merged when computing the effective ignore list.

**Why both:** `config.json`'s `ignore` field travels inside `.contx/` and is per-init defaults. `.contxignore` lives at the repo root next to `.gitignore`, is the natural place for team-wide exclusions, and follows the convention developers already know. Same split as `.gitignore` vs git's global ignore.

**Architecture:** One new module `contx/ignore.py` exposes `load_effective_ignore_patterns(repo_root) -> list[str]`. Existing call sites in `contx/staging.py` and `contx/mcp_tools.py` (audit) replace their `cfg.ignore` reads with calls to this helper. `contx init` writes a starter `.contxignore` with sensible defaults.

**Tech Stack:** Plain Python — no new deps. Reuses the segment-based `**` matcher already in `staging.py`.

---

## File Structure

```
~/Desktop/xeno/contx/
├── contx/
│   ├── ignore.py            # NEW
│   ├── staging.py           # MODIFY: use load_effective_ignore_patterns
│   ├── mcp_tools.py         # MODIFY: same in audit
│   └── cli.py               # MODIFY: init writes .contxignore template
└── tests/
    ├── test_ignore.py       # NEW
    ├── test_staging.py      # MODIFY: 1 new test for .contxignore precedence
    └── test_cli.py          # MODIFY: 1 new test for init creates .contxignore
```

---

## Task 1: `contx/ignore.py` (TDD)

**Files:**
- Create: `contx/ignore.py`
- Create: `tests/test_ignore.py`

- [ ] **Step 1: Write tests**

```python
from pathlib import Path

from contx.ignore import (
    CONTXIGNORE_FILENAME,
    load_contxignore_patterns,
    load_effective_ignore_patterns,
    matches_any_pattern,
)
from contx.config import default_config, save_config


def test_load_contxignore_missing_returns_empty(tmp_path: Path):
    assert load_contxignore_patterns(tmp_path) == []


def test_load_contxignore_strips_comments_and_blanks(tmp_path: Path):
    (tmp_path / CONTXIGNORE_FILENAME).write_text(
        "# a comment\n"
        "\n"
        "vendor/**\n"
        "  # indented comment\n"
        "**/*.generated.py\n"
    )
    assert load_contxignore_patterns(tmp_path) == ["vendor/**", "**/*.generated.py"]


def test_load_effective_combines_config_and_contxignore(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / CONTXIGNORE_FILENAME).write_text("custom/**\n")
    effective = load_effective_ignore_patterns(tmp_repo)
    # Default ignore patterns include node_modules; contxignore adds custom/**
    assert "**/node_modules/**" in effective
    assert "custom/**" in effective


def test_load_effective_without_config_falls_back_to_contxignore_only(tmp_path: Path):
    # No config.json — only the .contxignore should contribute.
    (tmp_path / CONTXIGNORE_FILENAME).write_text("only/**\n")
    effective = load_effective_ignore_patterns(tmp_path)
    assert effective == ["only/**"]


def test_matches_any_pattern_simple_glob():
    assert matches_any_pattern("vendor/foo.py", ["vendor/**"])
    assert not matches_any_pattern("src/foo.py", ["vendor/**"])


def test_matches_any_pattern_double_star_anywhere():
    assert matches_any_pattern("a/b/node_modules/x.js", ["**/node_modules/**"])


def test_matches_any_pattern_extension():
    assert matches_any_pattern("a/b.generated.py", ["**/*.generated.py"])
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement `contx/ignore.py`**

```python
"""Effective ignore-pattern resolution for contx operations.

Combines `.contxignore` (at repo root, gitignore-style) with the
`ignore` field of `.contx/config.json`. Either source alone is fine.

Pattern syntax (subset of gitignore):
- `*` matches a single path segment except `/`
- `**` matches any number of path segments
- `dir/file.py` matches the exact path
- Comments start with `#`; leading/trailing whitespace stripped; blank lines skipped
- Negation (`!`) is NOT yet supported (deferred to a follow-up)
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

CONTXIGNORE_FILENAME = ".contxignore"


def load_contxignore_patterns(repo_root: Path) -> list[str]:
    """Return the patterns from .contxignore at repo root, or [] if missing."""
    path = repo_root / CONTXIGNORE_FILENAME
    if not path.is_file():
        return []
    out: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def load_effective_ignore_patterns(repo_root: Path) -> list[str]:
    """Merge `.contx/config.json`'s ignore list with `.contxignore` patterns."""
    from contx.config import load_config
    patterns: list[str] = []
    try:
        cfg = load_config(repo_root)
        patterns.extend(cfg.ignore)
    except FileNotFoundError:
        pass
    patterns.extend(load_contxignore_patterns(repo_root))
    return patterns


def _segments_match(parts: list[str], pat_parts: list[str]) -> bool:
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


def matches_any_pattern(rel_path: str, patterns: list[str]) -> bool:
    """True if rel_path matches any of the gitignore-style patterns."""
    parts = rel_path.split("/")
    for pat in patterns:
        if _segments_match(parts, pat.split("/")):
            return True
    return False
```

- [ ] **Step 4: Verify 7 tests pass.**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/ignore.py tests/test_ignore.py && git commit -m "feat(ignore): add .contxignore support with config-merged effective patterns

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Wire `.contxignore` into `staging.compute_drift`

**Files:**
- Modify: `contx/staging.py`
- Modify: `tests/test_staging.py`

- [ ] **Step 1: Append test**

```python
def test_compute_drift_respects_contxignore(tmp_repo: Path):
    from contx.ignore import CONTXIGNORE_FILENAME
    save_config(tmp_repo, default_config())
    (tmp_repo / CONTXIGNORE_FILENAME).write_text("vendor/**\n")
    _write_and_stage(tmp_repo, "vendor/lib.py", "x = 1\n")
    drift = compute_drift(tmp_repo)
    assert "vendor/lib.py" not in drift.missing
```

- [ ] **Step 2: Update `staging.py`**

Replace this block in `compute_drift`:

```python
    ignore = cfg.ignore
```

with:

```python
    from contx.ignore import load_effective_ignore_patterns
    ignore = load_effective_ignore_patterns(repo_root)
```

Also delete the now-unused local `_matches_any` and `_segments_match` helpers in `staging.py` and import the helper from `contx.ignore`:

Replace:
```python
def _segments_match(parts: list[str], pat_parts: list[str]) -> bool:
    ...

def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    ...
```

with (top of file with other imports):
```python
from contx.ignore import matches_any_pattern as _matches_any  # noqa: F401
```

And update the call site inside `compute_drift`:
```python
        if _matches_any(p, ignore):
            continue
```

→ unchanged (the import alias preserves the existing function name).

- [ ] **Step 3: Verify all staging tests pass.**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/staging.py tests/test_staging.py && git commit -m "feat(staging): respect .contxignore patterns in drift detection

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Wire `.contxignore` into `mcp_tools.audit`

**Files:**
- Modify: `contx/mcp_tools.py`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Append test**

```python
def test_audit_respects_contxignore(tmp_repo: Path):
    from contx.ignore import CONTXIGNORE_FILENAME
    save_config(tmp_repo, default_config())
    (tmp_repo / CONTXIGNORE_FILENAME).write_text("legacy/**\n")
    (tmp_repo / "legacy").mkdir()
    (tmp_repo / "legacy" / "old.py").write_text("pass\n")
    result = audit_tool(tmp_repo)
    assert "legacy/old.py" not in result["untracked_files"]
```

- [ ] **Step 2: Update `audit` in `mcp_tools.py`**

Find the `_is_ignored` usage and the `ignore = cfg.ignore` line. Replace with:

```python
    from contx.ignore import load_effective_ignore_patterns, matches_any_pattern
    ignore = load_effective_ignore_patterns(repo_root)
    # … and replace any uses of the local _is_ignored with matches_any_pattern
```

Then delete the local `_is_ignored` helper if no other caller uses it.

- [ ] **Step 3: Verify tests pass.**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py tests/test_mcp_tools.py && git commit -m "feat(mcp): contx_audit respects .contxignore

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `contx init` writes a starter `.contxignore`

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append test**

```python
def test_init_creates_contxignore(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    ignore_file = tmp_repo / ".contxignore"
    assert ignore_file.is_file()
    content = ignore_file.read_text()
    assert "node_modules" in content


def test_init_preserves_existing_contxignore(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / ".contxignore").write_text("# user's custom file\nuser/**\n")
    runner.invoke(app, ["init"])
    content = (tmp_repo / ".contxignore").read_text()
    assert "user/**" in content  # untouched
```

- [ ] **Step 2: Update `cli.py`**

Add this helper near `_resolve_repo`:

```python
def _write_default_contxignore(repo: Path) -> bool:
    """Write a starter .contxignore if one doesn't exist. Returns True if written."""
    path = repo / ".contxignore"
    if path.exists():
        return False
    path.write_text(
        "# contx — paths to skip when tracking context.\n"
        "# Same syntax as .gitignore (subset).\n"
        "\n"
        "**/node_modules/**\n"
        "**/__tests__/**\n"
        "**/.venv/**\n"
        "**/venv/**\n"
        "**/dist/**\n"
        "**/build/**\n"
        "**/.contx/**\n"
    )
    return True
```

In the `init` command, after `save_config(repo, default_config())` (and the duplicate-init branch), add:

```python
    if _write_default_contxignore(repo):
        typer.echo(f"created .contxignore at {repo / '.contxignore'}")
```

- [ ] **Step 3: Verify all cli tests pass.**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): contx init creates a starter .contxignore

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: README + plan doc

- [ ] **Step 1: Append a `.contxignore` section** to the README under "Pre-commit hook" (or alongside the Storage layout section, wherever feels natural). Explain syntax, precedence rules (config.json + .contxignore are additive), and that `contx init` creates a starter file.

- [ ] **Step 2: Commit** README + this plan file.

---

## What ships after this plan

`.contxignore` becomes the canonical place to add per-repo exclusions. The config.json `ignore` field stays as the per-init default, and the two merge. Future docs and tooling should point users at `.contxignore` for ongoing maintenance — config.json is for `contx init`-time defaults.

## What's NOT in this plan (deferred)

- Negation patterns (`!path/to/include`).
- `.contxignore` interaction with `contx_search` (currently search walks the full `.contx/` tree regardless — that's intentional because entries inside ignored paths should still be searchable if they exist).
- A `contx ignore <pattern>` CLI to append patterns from the command line.
