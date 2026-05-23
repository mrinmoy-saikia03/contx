# contx — Plan B2: Bootstrap from history + AST

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Make `contx init` actually populate a brownfield repo. Walk the source tree and emit one baseline entry per file/symbol (using docstrings when available), and walk `git log` to emit per-commit history entries — both heavily filtered so the noise stays low.

**Architecture:** A new `contx/bootstrap/` package with four units: `bootstrap_filter` (noise heuristic), `ast_python` (Python AST walker), `ast_dispatch` (language → walker), `git_history` (git log walker). The CLI's `init` command gains `--bootstrap` / `--no-bootstrap` (default on), and a new standalone `contx bootstrap` command handles already-initialized repos.

**Tech Stack:** Python 3.11+, stdlib `ast` and `subprocess`, `python-ulid` (already a dep). No new packages.

**Companion spec:** `docs/specs/2026-05-23-contx-bootstrap-deploy-diagrams-design.md` §1.

---

## Task 1: bootstrap_filter — noise heuristic (TDD)

**Files:**
- Create: `contx/bootstrap/__init__.py`
- Create: `contx/bootstrap/bootstrap_filter.py`
- Create: `tests/test_bootstrap_filter.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_bootstrap_filter.py`:

```python
from contx.bootstrap.bootstrap_filter import is_noisy_commit, NOISY_PREFIXES


def test_is_noisy_commit_wip_prefix():
    assert is_noisy_commit("wip: more work", diff_lines=100) is True


def test_is_noisy_commit_typo():
    assert is_noisy_commit("fix typo in docs", diff_lines=100) is True


def test_is_noisy_commit_format():
    assert is_noisy_commit("format(black): apply", diff_lines=100) is True


def test_is_noisy_commit_lint():
    assert is_noisy_commit("lint: fix ruff", diff_lines=100) is True


def test_is_noisy_commit_merge():
    assert is_noisy_commit("Merge branch 'main' into feature", diff_lines=0) is True


def test_is_noisy_commit_bump():
    assert is_noisy_commit("bump deps", diff_lines=200) is True


def test_is_noisy_commit_chore_deps():
    assert is_noisy_commit("chore(deps): bump pytest from 8.0 to 8.1", diff_lines=10) is True


def test_is_noisy_commit_small_diff():
    assert is_noisy_commit("real change", diff_lines=3) is True


def test_is_noisy_commit_real_change():
    assert is_noisy_commit("Switch retry to linear for May incident", diff_lines=42) is False


def test_is_noisy_commit_case_insensitive_prefix():
    assert is_noisy_commit("WIP try X", diff_lines=100) is True


def test_noisy_prefixes_constant_has_expected_entries():
    for needle in ("wip", "typo", "fix typo", "format", "fmt", "lint", "merge", "bump", "chore(deps)", "version"):
        assert needle in NOISY_PREFIXES, f"missing prefix {needle}"


def test_is_noisy_commit_respects_threshold():
    # diff_lines below the default threshold (5) is noisy regardless of subject
    assert is_noisy_commit("Switch retry to linear", diff_lines=4) is True
    assert is_noisy_commit("Switch retry to linear", diff_lines=5) is False
```

- [ ] **Step 2: Run, verify failure**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_bootstrap_filter.py -v
```

Expected: `ModuleNotFoundError: No module named 'contx.bootstrap'`.

- [ ] **Step 3: Create the package**

`~/Desktop/xeno/contx/contx/bootstrap/__init__.py`:
```python
"""contx bootstrap — seed entries from git history + source AST."""

from __future__ import annotations
```

- [ ] **Step 4: Implement `bootstrap_filter.py`**

`~/Desktop/xeno/contx/contx/bootstrap/bootstrap_filter.py`:

```python
"""Heuristic for skipping low-signal commits during bootstrap."""

from __future__ import annotations

# Prefixes that mark a commit as low-signal. Matched case-insensitively against
# the commit subject after stripping leading whitespace.
NOISY_PREFIXES: tuple[str, ...] = (
    "wip",
    "typo",
    "fix typo",
    "format",
    "fmt",
    "lint",
    "merge",
    "bump",
    "chore(deps)",
    "version",
)

DEFAULT_MIN_DIFF_LINES = 5


def is_noisy_commit(
    subject: str,
    *,
    diff_lines: int,
    min_diff_lines: int = DEFAULT_MIN_DIFF_LINES,
) -> bool:
    """True if the commit should be skipped during bootstrap.

    Args:
        subject: Commit subject line.
        diff_lines: Total lines added+removed by this commit for the file under
            consideration.
        min_diff_lines: Threshold below which the commit is considered noise.
    """
    if diff_lines < min_diff_lines:
        return True
    s = subject.strip().lower()
    return any(s.startswith(prefix) for prefix in NOISY_PREFIXES)
```

- [ ] **Step 5: Verify 12 tests pass**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_bootstrap_filter.py -v
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/bootstrap/ tests/test_bootstrap_filter.py && git commit -m "feat(bootstrap): add noise-filter heuristic for git history walks

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: ast_python — Python AST walker (TDD)

**Files:**
- Create: `contx/bootstrap/ast_python.py`
- Create: `tests/test_ast_python.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_ast_python.py`:

```python
from pathlib import Path

from contx.bootstrap.ast_python import (
    BootstrapSymbol,
    parse_python_source,
)


def test_parse_top_level_function():
    src = '''"""module docstring"""


def hello(name):
    """Say hi."""
    return f"hi {name}"
'''
    result = parse_python_source(src)
    assert result.file_doc == "module docstring"
    syms = {s.symbol: s for s in result.symbols}
    assert "hello" in syms
    assert syms["hello"].doc == "Say hi."
    assert syms["hello"].kind == "function"


def test_parse_class_and_methods():
    src = '''
class Greeter:
    """A greeter."""

    def hello(self):
        """method doc"""
        pass

    def bye(self):
        pass
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert "Greeter" in syms
    assert syms["Greeter"].doc == "A greeter."
    assert syms["Greeter"].kind == "class"
    assert "Greeter.hello" in syms
    assert syms["Greeter.hello"].doc == "method doc"
    assert syms["Greeter.hello"].kind == "method"
    assert "Greeter.bye" in syms
    assert syms["Greeter.bye"].doc is None


def test_parse_async_function():
    src = '''
async def fetch_user(user_id):
    """Async fetcher."""
    return user_id
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert "fetch_user" in syms
    assert syms["fetch_user"].kind == "function"
    assert syms["fetch_user"].doc == "Async fetcher."


def test_parse_empty_module():
    result = parse_python_source("")
    assert result.file_doc is None
    assert result.symbols == []


def test_parse_no_docstrings():
    src = '''
def foo():
    return 1
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert syms["foo"].doc is None


def test_parse_syntax_error_returns_empty():
    # We don't want bootstrap to crash on one bad file.
    result = parse_python_source("def def def")
    assert result.symbols == []


def test_bootstrap_symbol_is_immutable():
    s = BootstrapSymbol(symbol="foo", kind="function", doc=None)
    import dataclasses
    assert dataclasses.is_dataclass(s) and s.__dataclass_params__.frozen
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `ast_python.py`**

`~/Desktop/xeno/contx/contx/bootstrap/ast_python.py`:

```python
"""Walk a Python module's AST and emit BootstrapSymbol entries."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

SymbolKind = Literal["function", "method", "class"]


@dataclass(frozen=True)
class BootstrapSymbol:
    symbol: str          # dotted path, e.g. "Greeter.hello"
    kind: SymbolKind
    doc: str | None      # docstring (first line summary or full), or None


@dataclass(frozen=True)
class ParseResult:
    file_doc: str | None
    symbols: list[BootstrapSymbol] = field(default_factory=list)


def parse_python_source(source: str) -> ParseResult:
    """Parse Python source code and return its module doc + top-level symbols.

    Resilient: returns empty ParseResult on SyntaxError.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ParseResult(file_doc=None, symbols=[])

    file_doc = ast.get_docstring(tree)
    symbols: list[BootstrapSymbol] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(BootstrapSymbol(
                symbol=node.name,
                kind="function",
                doc=ast.get_docstring(node),
            ))
        elif isinstance(node, ast.ClassDef):
            symbols.append(BootstrapSymbol(
                symbol=node.name,
                kind="class",
                doc=ast.get_docstring(node),
            ))
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(BootstrapSymbol(
                        symbol=f"{node.name}.{inner.name}",
                        kind="method",
                        doc=ast.get_docstring(inner),
                    ))

    return ParseResult(file_doc=file_doc, symbols=symbols)
```

- [ ] **Step 4: Verify 7 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/bootstrap/ast_python.py tests/test_ast_python.py && git commit -m "feat(bootstrap): add Python AST walker for symbol/docstring extraction

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: ast_dispatch — language → walker (TDD)

**Files:**
- Create: `contx/bootstrap/ast_dispatch.py`
- Create: `tests/test_ast_dispatch.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_ast_dispatch.py`:

```python
from pathlib import Path

from contx.bootstrap.ast_dispatch import bootstrap_file


def test_dispatch_python_file(tmp_path: Path):
    p = tmp_path / "foo.py"
    p.write_text('"""mod"""\ndef hi():\n    """h"""\n    pass\n')
    result = bootstrap_file(p)
    assert result is not None
    assert result.file_doc == "mod"
    assert any(s.symbol == "hi" for s in result.symbols)


def test_dispatch_unknown_language_returns_none(tmp_path: Path):
    p = tmp_path / "foo.unknownlang"
    p.write_text("whatever")
    assert bootstrap_file(p) is None


def test_dispatch_unsupported_typescript_returns_none(tmp_path: Path):
    p = tmp_path / "foo.ts"
    p.write_text("export const x = 1;")
    # TS stubbed for now; should return None until implemented.
    assert bootstrap_file(p) is None


def test_dispatch_missing_file_returns_none(tmp_path: Path):
    assert bootstrap_file(tmp_path / "nope.py") is None
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `ast_dispatch.py`**

`~/Desktop/xeno/contx/contx/bootstrap/ast_dispatch.py`:

```python
"""Dispatch source files to language-specific AST walkers."""

from __future__ import annotations

from pathlib import Path

from contx.bootstrap.ast_python import ParseResult, parse_python_source

# Map file extension → parser. None means "language is known but not yet implemented".
_PARSERS: dict[str, object] = {
    ".py": parse_python_source,
    # Stubs — fall through to None until implemented.
    ".ts": None,
    ".tsx": None,
    ".js": None,
    ".jsx": None,
    ".go": None,
    ".java": None,
    ".kt": None,
    ".rs": None,
    ".rb": None,
    ".php": None,
    ".swift": None,
}


def bootstrap_file(path: Path) -> ParseResult | None:
    """Parse a source file and return its BootstrapSymbol list, or None.

    Returns None when:
        - the file doesn't exist or is unreadable
        - the file extension is unknown
        - the language has no parser implemented yet
    """
    parser = _PARSERS.get(path.suffix)
    if parser is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return parser(text)  # type: ignore[no-any-return,operator]
```

- [ ] **Step 4: Verify 4 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/bootstrap/ast_dispatch.py tests/test_ast_dispatch.py && git commit -m "feat(bootstrap): add language dispatch (Python only for MVP)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: git_history — git log walker (TDD)

**Files:**
- Create: `contx/bootstrap/git_history.py`
- Create: `tests/test_git_history.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_git_history.py`:

```python
import subprocess
from pathlib import Path

from contx.bootstrap.git_history import (
    GitCommit,
    iter_commits_for_file,
    iter_commits_with_files,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, rel_path: str, content: str, message: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


def test_iter_commits_with_files_returns_commits_in_order(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "first commit")
    _commit(tmp_repo, "src/a.py", "x=2\n", "second commit")
    commits = list(iter_commits_with_files(tmp_repo))
    assert len(commits) == 2
    assert commits[0].subject == "first commit"
    assert commits[1].subject == "second commit"
    assert "src/a.py" in commits[0].files
    assert "src/a.py" in commits[1].files


def test_iter_commits_includes_author_and_timestamp(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "first commit")
    commits = list(iter_commits_with_files(tmp_repo))
    assert commits[0].author == "test@example.com"
    assert commits[0].timestamp.endswith("+00:00") or "T" in commits[0].timestamp


def test_iter_commits_respects_max_commits(tmp_repo: Path):
    for i in range(5):
        _commit(tmp_repo, f"src/a{i}.py", "x", f"commit {i}")
    commits = list(iter_commits_with_files(tmp_repo, max_commits=3))
    assert len(commits) == 3


def test_iter_commits_diff_lines_per_file(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "line1\nline2\nline3\n", "add a")
    commits = list(iter_commits_with_files(tmp_repo))
    assert commits[0].diff_lines_by_file.get("src/a.py", 0) >= 3


def test_iter_commits_for_file_filters(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "touched a")
    _commit(tmp_repo, "src/b.py", "y=1\n", "touched b")
    a_commits = list(iter_commits_for_file(tmp_repo, "src/a.py"))
    assert len(a_commits) == 1
    assert a_commits[0].subject == "touched a"


def test_iter_commits_empty_repo(tmp_repo: Path):
    assert list(iter_commits_with_files(tmp_repo)) == []


def test_iter_commits_handles_merge_commit(tmp_repo: Path):
    # Just ensure we don't crash on a merge commit with no diff.
    _commit(tmp_repo, "src/a.py", "x=1\n", "first")
    _git(tmp_repo, "checkout", "-b", "feature")
    _commit(tmp_repo, "src/b.py", "y=1\n", "on feature")
    _git(tmp_repo, "checkout", "master")
    # Try to merge; some git defaults may use 'main' — handle both.
    try:
        _git(tmp_repo, "merge", "feature", "--no-ff", "-m", "merge feature")
    except subprocess.CalledProcessError:
        _git(tmp_repo, "branch", "-m", "master", "main")
        _git(tmp_repo, "merge", "feature", "--no-ff", "-m", "merge feature")
    commits = list(iter_commits_with_files(tmp_repo))
    # At least the 3 commits exist; the merge may or may not have files.
    assert len(commits) >= 3
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `git_history.py`**

`~/Desktop/xeno/contx/contx/bootstrap/git_history.py`:

```python
"""Walk `git log` and yield commits with their file lists + diff line counts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

_SEP = "\x1e"          # record separator
_END = "\n---END---\n"


@dataclass(frozen=True)
class GitCommit:
    sha: str
    author: str            # author email
    timestamp: str         # ISO8601
    subject: str
    body: str
    files: list[str] = field(default_factory=list)
    diff_lines_by_file: dict[str, int] = field(default_factory=dict)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def iter_commits_with_files(
    repo_root: Path,
    *,
    max_commits: int | None = None,
    since: str | None = None,
) -> Iterator[GitCommit]:
    """Yield each commit (oldest first) with its changed file list + diff stats.

    Resilient to empty repos (returns no commits).
    """
    fmt = _SEP.join(["%H", "%ae", "%aI", "%s", "%b"]) + _END
    args = ["log", "--reverse", "--all", f"--pretty=format:{fmt}", "--numstat"]
    if since:
        args.append(f"{since}..HEAD")
    try:
        raw = _git(repo_root, *args)
    except subprocess.CalledProcessError:
        return

    # Each record is fields joined by _SEP + _END, then numstat lines until the next record.
    chunks = raw.split(_END)
    count = 0
    for chunk in chunks:
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        # First line: SHA<sep>email<sep>iso<sep>subject<sep>body-line-1
        # Subsequent lines: more body lines, then numstat lines (added\tdeleted\tpath)
        # Body is everything before the first numstat-looking line.
        lines = chunk.split("\n")
        head = lines[0]
        head_parts = head.split(_SEP)
        if len(head_parts) < 5:
            continue
        sha, author, ts, subject, body_first = head_parts[0], head_parts[1], head_parts[2], head_parts[3], head_parts[4]

        files: list[str] = []
        diffs: dict[str, int] = {}
        body_extra: list[str] = []
        in_body = True
        for line in lines[1:]:
            # numstat line: "added\tdeleted\tpath" or "-\t-\tpath" (binary)
            parts = line.split("\t")
            if len(parts) == 3 and (parts[0].isdigit() or parts[0] == "-"):
                in_body = False
                path = parts[2]
                added = int(parts[0]) if parts[0].isdigit() else 0
                deleted = int(parts[1]) if parts[1].isdigit() else 0
                files.append(path)
                diffs[path] = added + deleted
            elif in_body:
                body_extra.append(line)

        body = body_first + ("\n" + "\n".join(body_extra) if body_extra else "")
        yield GitCommit(
            sha=sha,
            author=author,
            timestamp=ts,
            subject=subject,
            body=body.strip(),
            files=files,
            diff_lines_by_file=diffs,
        )
        count += 1
        if max_commits is not None and count >= max_commits:
            return


def iter_commits_for_file(
    repo_root: Path,
    rel_path: str,
    *,
    max_commits: int | None = None,
) -> Iterator[GitCommit]:
    """Same as iter_commits_with_files but filtered to commits that touched rel_path."""
    for commit in iter_commits_with_files(repo_root, max_commits=max_commits):
        if rel_path in commit.files:
            yield commit
```

- [ ] **Step 4: Verify 7 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/bootstrap/git_history.py tests/test_git_history.py && git commit -m "feat(bootstrap): add git log walker with per-file diff stats

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: bootstrap_repo orchestrator (TDD)

Top-level function that runs AST + git_history together, applies the noise filter, writes entries via the existing `append_entry`.

**Files:**
- Modify: `contx/bootstrap/__init__.py`
- Create: `tests/test_bootstrap_repo.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_bootstrap_repo.py`:

```python
import subprocess
from pathlib import Path

import pytest

from contx.bootstrap import bootstrap_repo
from contx.config import default_config, save_config
from contx.store import read_entries


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, rel_path: str, content: str, message: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


def test_bootstrap_writes_ast_entries(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "auth.py").write_text(
        '"""Auth module."""\n\ndef login(user):\n    """Log a user in."""\n    pass\n'
    )
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    entries = read_entries(tmp_repo, "src/auth.py")
    # one file-level + one symbol-level entry
    assert any(e.kind == "file" and "Auth module" in e.rationale for e in entries)
    assert any(e.kind == "symbol" and e.symbol == "login" for e in entries)
    # All bootstrap entries are tagged + agent="audit"
    for e in entries:
        assert "bootstrap" in e.tags
        assert e.agent == "audit"


def test_bootstrap_writes_git_history_entries(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/auth.py", "line1\nline2\nline3\nline4\nline5\nline6\n", "Add login flow because GDPR")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/auth.py")
    assert any("GDPR" in e.rationale for e in entries)
    for e in entries:
        assert "git-history" in e.tags or "bootstrap" in e.tags
        assert e.agent == "audit"


def test_bootstrap_skips_noisy_commits(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/a.py", "x\n" * 10, "WIP work in progress")  # noisy prefix
    _commit(tmp_repo, "src/a.py", "x\n" * 12, "real change because incident")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/a.py")
    rationales = " ".join(e.rationale for e in entries)
    assert "incident" in rationales
    assert "WIP" not in rationales


def test_bootstrap_first_commit_is_created_event(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/a.py", "x\n" * 10, "Add a because we needed it")
    _commit(tmp_repo, "src/a.py", "x\n" * 15, "Modify a because incident")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/a.py")
    events = [e.event for e in entries]
    assert events[0] == "created"
    assert "modified" in events


def test_bootstrap_refuses_if_already_bootstrapped(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_repo(tmp_repo, do_ast=True, do_git=False)


def test_bootstrap_force_writes_supersede_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False, force=True)
    entries = read_entries(tmp_repo, "src/a.py")
    # at least one entry mentions "re-bootstrap"
    assert any("re-bootstrap" in e.rationale for e in entries)


def test_bootstrap_respects_contxignore(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / ".contxignore").write_text("vendor/**\n")
    (tmp_repo / "vendor").mkdir()
    (tmp_repo / "vendor" / "skip.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    # No sidecar should have been created under vendor/
    assert not (tmp_repo / ".contx" / "vendor" / "skip.py.jsonl").exists()
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement the orchestrator**

Replace `~/Desktop/xeno/contx/contx/bootstrap/__init__.py` contents with:

```python
"""contx bootstrap — seed entries from git history + source AST."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ulid import ULID

from contx.bootstrap.ast_dispatch import bootstrap_file
from contx.bootstrap.bootstrap_filter import is_noisy_commit
from contx.bootstrap.git_history import iter_commits_with_files
from contx.entry import Entry
from contx.ignore import load_effective_ignore_patterns, matches_any_pattern
from contx.paths import CTX_DIR, SIDECAR_SUFFIX
from contx.store import append_entry, read_entries

BOOTSTRAP_TAG = "bootstrap"
GIT_HISTORY_TAG = "git-history"


def _has_bootstrap_entries(repo_root: Path) -> bool:
    ctx_dir = repo_root / CTX_DIR
    if not ctx_dir.is_dir():
        return False
    for sidecar in ctx_dir.rglob(f"*{SIDECAR_SUFFIX}"):
        try:
            inner = sidecar.relative_to(ctx_dir)
            source_rel = str(inner)[:-len(SIDECAR_SUFFIX)]
        except ValueError:
            continue
        for e in read_entries(repo_root, source_rel):
            if BOOTSTRAP_TAG in e.tags:
                return True
    return False


def _iter_source_files(repo_root: Path, ignore_patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(repo_root))
        if rel.startswith(".git/") or rel.startswith(f"{CTX_DIR}/"):
            continue
        if matches_any_pattern(rel, ignore_patterns):
            continue
        out.append(path)
    return out


def _make_entry(
    *,
    kind: str,
    symbol: str | None,
    event: str,
    rationale: str,
    tags: list[str],
    author: str,
    timestamp: datetime,
) -> Entry:
    # Generate a ULID with the entry's timestamp so entries sort chronologically
    # across re-runs.
    ulid = ULID.from_timestamp(timestamp.timestamp())
    return Entry(
        id=str(ulid),
        kind=kind,  # type: ignore[arg-type]
        symbol=symbol,
        event=event,  # type: ignore[arg-type]
        rationale=rationale or "auto-bootstrapped — please fill in",
        tags=list(tags),
        author=author,
        timestamp=timestamp,
        agent="audit",
        related=[],
    )


def bootstrap_repo(
    repo_root: Path,
    *,
    do_ast: bool = True,
    do_git: bool = True,
    max_commits: int = 1000,
    min_diff_lines: int = 5,
    since: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Bootstrap `.contx/` entries for the repo. Returns the number of entries written."""
    if not force and _has_bootstrap_entries(repo_root):
        raise RuntimeError(
            "repo already bootstrapped; pass force=True to re-run (will append a supersede entry)"
        )

    ignore_patterns = load_effective_ignore_patterns(repo_root)
    now = datetime.now(timezone.utc)
    written = 0

    if force and _has_bootstrap_entries(repo_root):
        if not dry_run:
            # Write a marker on each file that already had bootstrap entries.
            ctx_dir = repo_root / CTX_DIR
            for sidecar in ctx_dir.rglob(f"*{SIDECAR_SUFFIX}"):
                inner = str(sidecar.relative_to(ctx_dir))[:-len(SIDECAR_SUFFIX)]
                marker = _make_entry(
                    kind="file",
                    symbol=None,
                    event="modified",
                    rationale="re-bootstrap; previous bootstrap entries superseded",
                    tags=[BOOTSTRAP_TAG, "supersede"],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                append_entry(repo_root, inner, marker)
                written += 1

    if do_ast:
        for path in _iter_source_files(repo_root, ignore_patterns):
            result = bootstrap_file(path)
            if result is None:
                continue
            rel = str(path.relative_to(repo_root))
            if result.file_doc or result.symbols:
                file_entry = _make_entry(
                    kind="file",
                    symbol=None,
                    event="created",
                    rationale=(result.file_doc or ""),
                    tags=[BOOTSTRAP_TAG],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                if not dry_run:
                    append_entry(repo_root, rel, file_entry)
                written += 1
            for sym in result.symbols:
                sym_entry = _make_entry(
                    kind="symbol",
                    symbol=sym.symbol,
                    event="created",
                    rationale=sym.doc or "",
                    tags=[BOOTSTRAP_TAG, sym.kind],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                if not dry_run:
                    append_entry(repo_root, rel, sym_entry)
                written += 1

    if do_git:
        seen_files: set[str] = set()
        for commit in iter_commits_with_files(repo_root, max_commits=max_commits, since=since):
            for f in commit.files:
                if f.startswith(f"{CTX_DIR}/") or f.startswith(".git/"):
                    continue
                if matches_any_pattern(f, ignore_patterns):
                    continue
                diff = commit.diff_lines_by_file.get(f, 0)
                if is_noisy_commit(commit.subject, diff_lines=diff, min_diff_lines=min_diff_lines):
                    continue
                event = "created" if f not in seen_files else "modified"
                seen_files.add(f)
                # Compose rationale: subject + first line of body if present
                rationale = commit.subject
                body_first = commit.body.splitlines()[0] if commit.body.strip() else ""
                if body_first:
                    rationale = f"{commit.subject}\n\n{body_first}"
                try:
                    ts = datetime.fromisoformat(commit.timestamp)
                except ValueError:
                    ts = now
                entry = _make_entry(
                    kind="file",
                    symbol=None,
                    event=event,
                    rationale=rationale,
                    tags=[BOOTSTRAP_TAG, GIT_HISTORY_TAG],
                    author=commit.author,
                    timestamp=ts,
                )
                if not dry_run:
                    append_entry(repo_root, f, entry)
                written += 1

    return written
```

- [ ] **Step 4: Verify 7 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/bootstrap/__init__.py tests/test_bootstrap_repo.py && git commit -m "feat(bootstrap): add bootstrap_repo orchestrator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: CLI integration (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Tests**

Append to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
def test_init_with_bootstrap_default_runs_ast(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi():\n    """h"""\n    pass\n')
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert sidecar.is_file()
    assert "mod" in sidecar.read_text()


def test_init_no_bootstrap_skips_bootstrap(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi(): pass\n')
    result = runner.invoke(app, ["init", "--no-bootstrap"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert not sidecar.exists()


def test_bootstrap_command_on_already_initialized_repo(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi(): pass\n')
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0, result.output
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert sidecar.is_file()


def test_bootstrap_refuses_second_run_without_force(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    runner.invoke(app, ["bootstrap"])
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    assert "already bootstrapped" in result.output.lower()


def test_bootstrap_force_succeeds(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    runner.invoke(app, ["bootstrap"])
    result = runner.invoke(app, ["bootstrap", "--force"])
    assert result.exit_code == 0, result.output


def test_bootstrap_dry_run_writes_nothing(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    result = runner.invoke(app, ["bootstrap", "--dry-run"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert not sidecar.exists()
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Modify `contx/cli.py`**

(a) Add import at top:

```python
from contx.bootstrap import bootstrap_repo
```

(b) Modify the `init` command signature + body to add `--bootstrap` / `--no-bootstrap` and `--bootstrap-ast` / `--bootstrap-git`. Replace the existing `init` command with:

```python
@app.command()
def init(
    no_hook: bool = typer.Option(False, "--no-hook", help="Skip installing the pre-commit hook"),
    no_bootstrap: bool = typer.Option(False, "--no-bootstrap", help="Skip bootstrap pass after init"),
    bootstrap_ast: bool = typer.Option(False, "--bootstrap-ast", help="Bootstrap from AST only (skip git history)"),
    bootstrap_git: bool = typer.Option(False, "--bootstrap-git", help="Bootstrap from git history only (skip AST)"),
) -> None:
    """Initialize contx for the current git repo."""
    repo = _resolve_repo()
    fresh = not is_initialized(repo)
    if not fresh:
        typer.echo(f"contx already initialized at {repo / '.contx'}")
    else:
        save_config(repo, default_config())
        typer.echo(f"initialized contx at {repo / '.contx'}")

    if not no_hook and not is_pre_commit_hook_installed(repo):
        install_pre_commit_hook(repo)
        typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")

    if _write_default_contxignore(repo):
        typer.echo(f"created .contxignore at {repo / '.contxignore'}")

    if not no_bootstrap and fresh:
        do_ast = not bootstrap_git
        do_git = not bootstrap_ast
        try:
            written = bootstrap_repo(repo, do_ast=do_ast, do_git=do_git)
            typer.echo(f"bootstrap wrote {written} entries (tag=bootstrap, agent=audit)")
        except RuntimeError as exc:
            typer.echo(f"bootstrap skipped: {exc}")
```

(c) Add a new top-level command:

```python
@app.command()
def bootstrap(
    ast: bool = typer.Option(False, "--ast", help="AST only (skip git history)"),
    git: bool = typer.Option(False, "--git", help="Git history only (skip AST)"),
    force: bool = typer.Option(False, "--force", help="Re-run even if already bootstrapped"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print counts without writing"),
    since: str | None = typer.Option(None, "--since", help="Git ref to start history walk from"),
) -> None:
    """Seed entries from git history + AST. Run on already-initialized repos."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized. Run `contx init --no-bootstrap` first.", err=True)
        raise typer.Exit(code=2)
    do_ast = not git
    do_git = not ast
    try:
        written = bootstrap_repo(
            repo,
            do_ast=do_ast,
            do_git=do_git,
            force=force,
            dry_run=dry_run,
            since=since,
        )
    except RuntimeError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)
    if dry_run:
        typer.echo(f"dry-run: would write {written} entries")
    else:
        typer.echo(f"bootstrap wrote {written} entries (tag=bootstrap, agent=audit)")
```

- [ ] **Step 4: Verify 6 new CLI tests pass + full suite**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest -q
```

Expected: ~189 PASS (148 prior + bootstrap tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): wire bootstrap into init + add 'contx bootstrap' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: README

Add a "Bootstrapping a brownfield repo" section to README.md describing the `--bootstrap` flow, the `bootstrap` command, the `--force`/`--dry-run`/`--since`/`--ast`/`--git` options, and what entries are tagged with. Then commit the plan doc too.

```bash
cd ~/Desktop/xeno/contx && git add README.md docs/plans/2026-05-23-contx-b2-bootstrap.md && git commit -m "docs: document bootstrap commands + Plan B2 file

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1.1 AST baseline → Tasks 2, 3, 5
- §1.2 Git history → Tasks 1, 4, 5
- §1.3 Noise heuristic → Task 1
- §1.4 CLI surface → Task 6 (all flags: `--bootstrap`, `--no-bootstrap`, `--bootstrap-ast`, `--bootstrap-git`, `bootstrap --since`, `--dry-run`, `--force`, `--ast`, `--git`)
- §1.5 Output volume control → Task 5 (`max_commits`, `min_diff_lines`) + Task 6 (`--since`)
- §1.6 Idempotence → Task 5 (`_has_bootstrap_entries`, `force=True` writes supersede marker)
- §1.7 Module structure → Tasks 1-5

**Placeholders:** none.

**Type consistency:** `BootstrapSymbol`, `ParseResult`, `GitCommit`, `bootstrap_repo`, `is_noisy_commit`, `bootstrap_file` — used consistently across tasks. `Entry` from `contx.entry` is constructed identically everywhere via `_make_entry`.
