# contx — Plan 1: Storage Core + CLI Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the storage layer (sidecar JSONL files in a `.contx/` mirror tree) plus the human-facing CLI commands that read and write to it. Output of this plan: a working `contx` CLI that can `init` a repo, `append` entries, `show` folded intent, and `log` raw history. No MCP, hooks, skill, or web UI yet — those come in Plans 2–5.

**Architecture:** Single Python package `contx/`. CLI built with typer. JSONL files stored under `.contx/` mirroring the source tree. ULIDs for entry IDs (sortable, collision-free across branches). All code paths are pure-function over file content where possible to keep testing simple. Read this plan's companion spec at `~/Desktop/xeno/contx/docs/specs/2026-05-21-contx-design.md` for the broader design.

**Tech Stack:** Python 3.11+, typer (CLI), python-ulid (entry IDs), pytest (testing). No DB, no parser, no web framework yet.

---

## File Structure (what this plan creates)

```
contx/                         # workspace folder at ~/Desktop/xeno/contx/
├── pyproject.toml
├── README.md
├── .gitignore
├── contx/                     # Python package (same name; conventional, like flask/flask/)
│   ├── __init__.py            # version constant
│   ├── __main__.py            # python -m contx entry point
│   ├── entry.py               # Entry dataclass + JSONL (de)serialization
│   ├── paths.py               # source-path ↔ sidecar-path resolution
│   ├── config.py              # .contx/config.json read/write
│   ├── store.py               # high-level append / query / fold
│   ├── repo.py                # find repo root, ensure .contx exists
│   └── cli.py                 # typer app: init, append, show, log
└── tests/
    ├── __init__.py
    ├── conftest.py            # fixtures: tmp_repo, sample_entries
    ├── test_entry.py
    ├── test_paths.py
    ├── test_config.py
    ├── test_store.py
    ├── test_repo.py
    └── test_cli.py
```

**Repo location.** This plan creates the code at `~/Desktop/xeno/contx/`. `git init` is run inside that directory so it's a self-contained git repo (separate from any parent `xeno` repo). The nested `contx/contx/` Python package layout is conventional Python (compare `flask/flask/`, `requests/requests/`).

---

## Task 1: Project scaffolding

**Files:**
- Create: `~/Desktop/xeno/contx/pyproject.toml`
- Create: `~/Desktop/xeno/contx/.gitignore`
- Create: `~/Desktop/xeno/contx/README.md`
- Create: `~/Desktop/xeno/contx/contx/__init__.py`
- Create: `~/Desktop/xeno/contx/contx/__main__.py`
- Create: `~/Desktop/xeno/contx/tests/__init__.py`

- [ ] **Step 1: Create the repo directory and init git**

```bash
mkdir -p ~/Desktop/xeno/contx/contx ~/Desktop/xeno/contx/tests
cd ~/Desktop/xeno/contx
git init
```

- [ ] **Step 2: Create `pyproject.toml`**

Write to `~/Desktop/xeno/contx/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "contx"
version = "0.1.0"
description = "Git for context: append-only intent logs per file/symbol"
readme = "README.md"
requires-python = ">=3.11"
authors = [{ name = "Mrinmoy Saikia", email = "mrinmoy.saikia@xeno.in" }]
dependencies = [
    "typer>=0.12.0",
    "python-ulid>=2.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
contx = "contx.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=contx --cov-report=term-missing"
```

- [ ] **Step 3: Create `.gitignore`**

Write to `~/Desktop/xeno/contx/.gitignore`:

```
__pycache__/
*.py[cod]
.venv/
venv/
.coverage
htmlcov/
.pytest_cache/
dist/
build/
*.egg-info/
.DS_Store
```

- [ ] **Step 4: Create `README.md`**

Write to `~/Desktop/xeno/contx/README.md`:

```markdown
# contx

Git for context. Append-only logs of *why* each file and function exists, written by AI coding agents as they edit and read by AI agents when explaining code to humans.

See `docs/spec.md` (link the spec here later) for the full design.

## Quickstart

\`\`\`bash
pip install -e .[dev]
contx init
contx show src/foo.py::bar
\`\`\`
```

- [ ] **Step 5: Create `contx/__init__.py`**

Write to `~/Desktop/xeno/contx/contx/__init__.py`:

```python
"""contx — git for context."""

__version__ = "0.1.0"
```

- [ ] **Step 6: Create `contx/__main__.py`**

Write to `~/Desktop/xeno/contx/contx/__main__.py`:

```python
from contx.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 7: Create empty `tests/__init__.py`**

Write to `~/Desktop/xeno/contx/tests/__init__.py`: (empty file)

- [ ] **Step 8: Create a minimal `contx/cli.py` stub so the package imports cleanly**

Write to `~/Desktop/xeno/contx/contx/cli.py`:

```python
import typer

app = typer.Typer(help="contx — git for context")


@app.command()
def version() -> None:
    """Print contx version."""
    from contx import __version__
    typer.echo(__version__)
```

- [ ] **Step 9: Install in editable mode and verify**

```bash
cd ~/Desktop/xeno/contx
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
contx version
```

Expected output: `0.1.0`

- [ ] **Step 10: Commit**

```bash
cd ~/Desktop/xeno/contx
git add pyproject.toml .gitignore README.md contx/ tests/
git commit -m "chore: scaffold contx package

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Entry dataclass + JSONL serialization (TDD)

**Files:**
- Create: `contx/entry.py`
- Create: `tests/test_entry.py`

- [ ] **Step 1: Write the failing test**

Write to `~/Desktop/xeno/contx/tests/test_entry.py`:

```python
from datetime import datetime, timezone

from contx.entry import Entry


def test_entry_to_dict_roundtrip():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="symbol",
        symbol="User.authenticate",
        event="created",
        rationale="Email-only login because Legal said phone OTP doesn't meet GDPR",
        tags=["compliance", "gdpr"],
        author="mrinmoy.saikia@xeno.in",
        timestamp=datetime(2026, 5, 21, 14, 23, 11, tzinfo=timezone.utc),
        agent="claude-code",
        related=["src/auth/sso.py::route_eu"],
    )
    d = e.to_dict()
    e2 = Entry.from_dict(d)
    assert e2 == e


def test_entry_file_kind_has_no_symbol():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file",
        symbol=None,
        event="created",
        rationale="Auth module — owns login and session lifecycle",
        tags=[],
        author="me",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )
    assert e.to_dict()["symbol"] is None


def test_entry_to_jsonl_line():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="symbol",
        symbol="foo",
        event="created",
        rationale="bar",
        tags=[],
        author="me",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )
    line = e.to_jsonl_line()
    assert "\n" not in line
    assert '"id": "01HXYZ0000000000000000000K"' in line


def test_entry_from_jsonl_line():
    line = (
        '{"id":"01HXYZ0000000000000000000K","kind":"symbol","symbol":"foo",'
        '"event":"created","rationale":"bar","tags":[],"author":"me",'
        '"timestamp":"2026-05-21T00:00:00+00:00","agent":"claude-code","related":[]}'
    )
    e = Entry.from_jsonl_line(line)
    assert e.id == "01HXYZ0000000000000000000K"
    assert e.symbol == "foo"


def test_entry_rejects_invalid_kind():
    import pytest
    with pytest.raises(ValueError, match="kind must be"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="banana",  # invalid
            symbol=None,
            event="created",
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )


def test_entry_rejects_invalid_event():
    import pytest
    with pytest.raises(ValueError, match="event must be"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="symbol",
            symbol="foo",
            event="exploded",  # invalid
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )


def test_entry_symbol_required_when_kind_is_symbol():
    import pytest
    with pytest.raises(ValueError, match="symbol is required"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="symbol",
            symbol=None,  # missing
            event="created",
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_entry.py -v`

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'contx.entry'`

- [ ] **Step 3: Write the minimal implementation**

Write to `~/Desktop/xeno/contx/contx/entry.py`:

```python
"""Entry dataclass — one append-only record in a contx sidecar."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

EntryKind = Literal["file", "symbol"]
EntryEvent = Literal[
    "created",
    "modified",
    "renamed_in",
    "renamed_out",
    "moved_in",
    "moved_out",
    "deleted",
]
EntryAgent = Literal["claude-code", "cursor", "human-cli", "audit"]

_VALID_KINDS = {"file", "symbol"}
_VALID_EVENTS = {
    "created", "modified", "renamed_in", "renamed_out",
    "moved_in", "moved_out", "deleted",
}


@dataclass(frozen=True)
class Entry:
    """A single append-only context entry. Immutable by design."""

    id: str
    kind: EntryKind
    symbol: str | None
    event: EntryEvent
    rationale: str
    tags: list[str]
    author: str
    timestamp: datetime
    agent: EntryAgent
    related: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"kind must be one of {_VALID_KINDS}, got {self.kind!r}")
        if self.event not in _VALID_EVENTS:
            raise ValueError(f"event must be one of {_VALID_EVENTS}, got {self.event!r}")
        if self.kind == "symbol" and not self.symbol:
            raise ValueError("symbol is required when kind == 'symbol'")
        if not self.rationale or not self.rationale.strip():
            raise ValueError("rationale must be a non-empty string")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "symbol": self.symbol,
            "event": self.event,
            "rationale": self.rationale,
            "tags": list(self.tags),
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "related": list(self.related),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Entry:
        return cls(
            id=d["id"],
            kind=d["kind"],
            symbol=d.get("symbol"),
            event=d["event"],
            rationale=d["rationale"],
            tags=list(d.get("tags", [])),
            author=d["author"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            agent=d["agent"],
            related=list(d.get("related", [])),
        )

    def to_jsonl_line(self) -> str:
        """Serialize as one line of JSON, no trailing newline."""
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_jsonl_line(cls, line: str) -> Entry:
        return cls.from_dict(json.loads(line))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_entry.py -v`

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/entry.py tests/test_entry.py
git commit -m "feat(entry): add Entry dataclass with JSONL serialization

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Sidecar path resolution (TDD)

**Files:**
- Create: `contx/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

Write to `~/Desktop/xeno/contx/tests/test_paths.py`:

```python
from pathlib import Path

from contx.paths import (
    sidecar_path_for_source,
    source_path_for_sidecar,
    parse_symbol_ref,
)


def test_sidecar_path_for_source_basic():
    repo = Path("/r")
    src = Path("/r/src/auth/login.py")
    assert sidecar_path_for_source(repo, src) == Path("/r/.contx/src/auth/login.py.jsonl")


def test_sidecar_path_for_source_at_root():
    repo = Path("/r")
    src = Path("/r/main.py")
    assert sidecar_path_for_source(repo, src) == Path("/r/.contx/main.py.jsonl")


def test_sidecar_path_rejects_path_outside_repo():
    import pytest
    repo = Path("/r")
    src = Path("/elsewhere/main.py")
    with pytest.raises(ValueError, match="outside the repo"):
        sidecar_path_for_source(repo, src)


def test_source_path_for_sidecar_basic():
    repo = Path("/r")
    sc = Path("/r/.contx/src/auth/login.py.jsonl")
    assert source_path_for_sidecar(repo, sc) == Path("/r/src/auth/login.py")


def test_source_path_rejects_non_sidecar():
    import pytest
    repo = Path("/r")
    sc = Path("/r/src/auth/login.py")
    with pytest.raises(ValueError, match="not a contx sidecar"):
        source_path_for_sidecar(repo, sc)


def test_parse_symbol_ref_file_only():
    assert parse_symbol_ref("src/auth/login.py") == ("src/auth/login.py", None)


def test_parse_symbol_ref_with_symbol():
    assert parse_symbol_ref("src/auth/login.py::User.authenticate") == (
        "src/auth/login.py",
        "User.authenticate",
    )


def test_parse_symbol_ref_rejects_double_separator():
    import pytest
    with pytest.raises(ValueError, match="only one"):
        parse_symbol_ref("a::b::c")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_paths.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'contx.paths'`

- [ ] **Step 3: Write the implementation**

Write to `~/Desktop/xeno/contx/contx/paths.py`:

```python
"""Sidecar path resolution: source files ↔ .contx/ mirror tree."""

from __future__ import annotations

from pathlib import Path

CTX_DIR = ".contx"
SIDECAR_SUFFIX = ".jsonl"


def sidecar_path_for_source(repo_root: Path, source: Path) -> Path:
    """Map a source file path to its sidecar path inside .contx/.

    `source` may be absolute (must live inside `repo_root`) or relative
    (taken as relative-to-repo-root as-is).
    """
    if source.is_absolute():
        try:
            rel = source.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"source {source} is outside the repo {repo_root}") from exc
    else:
        rel = source
    return repo_root / CTX_DIR / (str(rel) + SIDECAR_SUFFIX)


def source_path_for_sidecar(repo_root: Path, sidecar: Path) -> Path:
    """Reverse of sidecar_path_for_source. Raises if path isn't a sidecar."""
    if sidecar.is_absolute():
        try:
            rel = sidecar.relative_to(repo_root / CTX_DIR)
        except ValueError as exc:
            raise ValueError(f"{sidecar} is not a contx sidecar inside {repo_root}") from exc
    else:
        parts = sidecar.parts
        if not parts or parts[0] != CTX_DIR:
            raise ValueError(f"{sidecar} is not a contx sidecar")
        rel = Path(*parts[1:])

    name = rel.name
    if not name.endswith(SIDECAR_SUFFIX):
        raise ValueError(f"{sidecar} is not a contx sidecar (missing {SIDECAR_SUFFIX})")
    rel = rel.with_name(name[: -len(SIDECAR_SUFFIX)])
    return repo_root / rel


SYMBOL_SEP = "::"


def parse_symbol_ref(ref: str) -> tuple[str, str | None]:
    """Parse a reference like 'src/foo.py' or 'src/foo.py::Class.method'.

    Returns (file_path, symbol_or_None).
    """
    parts = ref.split(SYMBOL_SEP)
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"symbol ref must contain only one '{SYMBOL_SEP}' separator, got: {ref!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_paths.py -v`

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/paths.py tests/test_paths.py
git commit -m "feat(paths): add sidecar path resolution + symbol ref parsing

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Repo root detection (TDD)

**Files:**
- Create: `contx/repo.py`
- Create: `tests/test_repo.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Write to `~/Desktop/xeno/contx/tests/conftest.py`:

```python
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A fresh, empty git repo in a tmp dir."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    return tmp_path
```

Write to `~/Desktop/xeno/contx/tests/test_repo.py`:

```python
from pathlib import Path

import pytest

from contx.repo import find_repo_root, NotInRepoError, ensure_contx_dir, is_initialized


def test_find_repo_root_from_repo_root(tmp_repo: Path):
    assert find_repo_root(tmp_repo) == tmp_repo


def test_find_repo_root_from_subdir(tmp_repo: Path):
    sub = tmp_repo / "src" / "auth"
    sub.mkdir(parents=True)
    assert find_repo_root(sub) == tmp_repo


def test_find_repo_root_outside_repo(tmp_path: Path):
    with pytest.raises(NotInRepoError):
        find_repo_root(tmp_path)


def test_ensure_contx_dir_creates_dir(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    assert (tmp_repo / ".contx").is_dir()


def test_ensure_contx_dir_idempotent(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    ensure_contx_dir(tmp_repo)  # no error
    assert (tmp_repo / ".contx").is_dir()


def test_is_initialized_false_initially(tmp_repo: Path):
    assert is_initialized(tmp_repo) is False


def test_is_initialized_true_after_ensure(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    (tmp_repo / ".contx" / "config.json").write_text("{}")
    assert is_initialized(tmp_repo) is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_repo.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'contx.repo'`

- [ ] **Step 3: Write the implementation**

Write to `~/Desktop/xeno/contx/contx/repo.py`:

```python
"""Repo root detection and .contx/ directory bootstrap."""

from __future__ import annotations

from pathlib import Path

from contx.paths import CTX_DIR


class NotInRepoError(Exception):
    """Raised when an operation needs a git repo but isn't inside one."""


def find_repo_root(start: Path) -> Path:
    """Walk up from `start` looking for a .git directory. Raise if not found."""
    p = start.resolve()
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            raise NotInRepoError(f"{start} is not inside a git repo")
        p = p.parent


def ensure_contx_dir(repo_root: Path) -> Path:
    """Create .contx/ if missing. Returns its path."""
    d = repo_root / CTX_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_initialized(repo_root: Path) -> bool:
    """True iff .contx/config.json exists in this repo."""
    return (repo_root / CTX_DIR / "config.json").is_file()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_repo.py -v`

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/repo.py tests/test_repo.py tests/conftest.py
git commit -m "feat(repo): add repo-root detection and .contx/ bootstrap

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Config file read/write (TDD)

**Files:**
- Create: `contx/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Write to `~/Desktop/xeno/contx/tests/test_config.py`:

```python
from pathlib import Path

import pytest

from contx.config import Config, load_config, save_config, default_config


def test_default_config_values():
    cfg = default_config()
    assert cfg.granularity == "both"
    assert "py" in cfg.languages
    assert cfg.require_rationale_on_create is True
    assert cfg.extract_rationale_on_modify is True


def test_save_then_load_roundtrip(tmp_repo: Path):
    cfg = Config(
        granularity="symbol",
        languages=["py", "ts"],
        ignore=["**/__tests__/**"],
        require_rationale_on_create=False,
        extract_rationale_on_modify=True,
    )
    save_config(tmp_repo, cfg)
    loaded = load_config(tmp_repo)
    assert loaded == cfg


def test_load_config_missing_raises(tmp_repo: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_repo)


def test_save_config_creates_contx_dir(tmp_repo: Path):
    cfg = default_config()
    save_config(tmp_repo, cfg)
    assert (tmp_repo / ".contx" / "config.json").is_file()


def test_config_rejects_invalid_granularity():
    with pytest.raises(ValueError, match="granularity"):
        Config(
            granularity="weekly",  # invalid
            languages=["py"],
            ignore=[],
            require_rationale_on_create=True,
            extract_rationale_on_modify=True,
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'contx.config'`

- [ ] **Step 3: Write the implementation**

Write to `~/Desktop/xeno/contx/contx/config.py`:

```python
"""Per-repo config: .contx/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from contx.paths import CTX_DIR
from contx.repo import ensure_contx_dir

Granularity = Literal["file", "symbol", "both"]
_VALID_GRANULARITY = {"file", "symbol", "both"}

CONFIG_FILENAME = "config.json"

DEFAULT_LANGUAGES = ["py", "ts", "tsx", "js", "jsx", "go", "java", "kt", "rs", "rb", "php", "swift"]
DEFAULT_IGNORE = [
    "**/node_modules/**",
    "**/__tests__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/build/**",
]


@dataclass(frozen=True)
class Config:
    granularity: Granularity
    languages: list[str]
    ignore: list[str]
    require_rationale_on_create: bool
    extract_rationale_on_modify: bool

    def __post_init__(self) -> None:
        if self.granularity not in _VALID_GRANULARITY:
            raise ValueError(
                f"granularity must be one of {_VALID_GRANULARITY}, got {self.granularity!r}"
            )


def default_config() -> Config:
    return Config(
        granularity="both",
        languages=list(DEFAULT_LANGUAGES),
        ignore=list(DEFAULT_IGNORE),
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
    )


def _config_path(repo_root: Path) -> Path:
    return repo_root / CTX_DIR / CONFIG_FILENAME


def save_config(repo_root: Path, cfg: Config) -> None:
    ensure_contx_dir(repo_root)
    _config_path(repo_root).write_text(json.dumps(asdict(cfg), indent=2) + "\n")


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
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_config.py -v`

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/config.py tests/test_config.py
git commit -m "feat(config): add per-repo Config with JSON read/write

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Store — append entries (TDD)

**Files:**
- Create: `contx/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write the failing test (append portion)**

Write to `~/Desktop/xeno/contx/tests/test_store.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.entry import Entry
from contx.store import append_entry, read_entries


def _make_entry(symbol: str | None = "User.authenticate", event: str = "created", rationale: str = "why") -> Entry:
    return Entry(
        id=f"01H{symbol or 'F'}0000000000000000000K"[:26].ljust(26, "0"),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=[],
        author="test@example.com",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli",
        related=[],
    )


def test_append_creates_sidecar(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "src/auth/login.py", e)
    sidecar = tmp_repo / ".contx" / "src" / "auth" / "login.py.jsonl"
    assert sidecar.is_file()


def test_append_creates_parent_dirs(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "very/deeply/nested/file.py", e)
    sidecar = tmp_repo / ".contx" / "very" / "deeply" / "nested" / "file.py.jsonl"
    assert sidecar.is_file()


def test_append_writes_one_line(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "src/foo.py", e)
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.read_text().count("\n") == 1


def test_append_two_entries_appends_not_overwrites(tmp_repo: Path):
    e1 = _make_entry(rationale="first")
    e2 = _make_entry(rationale="second")
    append_entry(tmp_repo, "src/foo.py", e1)
    append_entry(tmp_repo, "src/foo.py", e2)
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.read_text().count("\n") == 2


def test_read_entries_returns_in_file_order(tmp_repo: Path):
    e1 = _make_entry(rationale="first")
    e2 = _make_entry(rationale="second")
    append_entry(tmp_repo, "src/foo.py", e1)
    append_entry(tmp_repo, "src/foo.py", e2)
    entries = read_entries(tmp_repo, "src/foo.py")
    assert [e.rationale for e in entries] == ["first", "second"]


def test_read_entries_missing_sidecar_returns_empty(tmp_repo: Path):
    assert read_entries(tmp_repo, "src/nope.py") == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_store.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'contx.store'`

- [ ] **Step 3: Write the implementation**

Write to `~/Desktop/xeno/contx/contx/store.py`:

```python
"""High-level store: append and read entries from sidecar JSONL files."""

from __future__ import annotations

from pathlib import Path

from contx.entry import Entry
from contx.paths import sidecar_path_for_source


def append_entry(repo_root: Path, source_rel_path: str, entry: Entry) -> Path:
    """Append `entry` to the sidecar for `source_rel_path` (relative to repo root).

    Returns the sidecar path written.
    """
    sidecar = sidecar_path_for_source(repo_root, Path(source_rel_path))
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    with sidecar.open("a", encoding="utf-8") as f:
        f.write(entry.to_jsonl_line() + "\n")
    return sidecar


def read_entries(repo_root: Path, source_rel_path: str) -> list[Entry]:
    """Read all entries from the sidecar for `source_rel_path`, in file order.

    Returns [] if the sidecar doesn't exist.
    """
    sidecar = sidecar_path_for_source(repo_root, Path(source_rel_path))
    if not sidecar.is_file():
        return []
    out: list[Entry] = []
    with sidecar.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Entry.from_jsonl_line(line))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_store.py -v`

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/store.py tests/test_store.py
git commit -m "feat(store): add append_entry and read_entries

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Store — fold entries into current intent (TDD)

**Files:**
- Modify: `contx/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write the failing test for `fold_entries`**

Add to `~/Desktop/xeno/contx/tests/test_store.py` (append at the end):

```python
from contx.store import fold_entries, FoldedIntent


def test_fold_empty_returns_empty_intent():
    folded = fold_entries([])
    assert folded.file_intent is None
    assert folded.symbols == {}


def test_fold_collects_file_level_intent():
    file_e = _make_entry(symbol=None, event="created", rationale="auth module")
    folded = fold_entries([file_e])
    assert folded.file_intent == "auth module"


def test_fold_latest_file_intent_wins():
    e1 = _make_entry(symbol=None, event="created", rationale="v1")
    e2 = _make_entry(symbol=None, event="modified", rationale="v2 — pivot to SSO")
    folded = fold_entries([e1, e2])
    assert folded.file_intent == "v2 — pivot to SSO"


def test_fold_collects_symbol_intent_keyed_by_symbol():
    a = _make_entry(symbol="foo", rationale="foo why")
    b = _make_entry(symbol="bar", rationale="bar why")
    folded = fold_entries([a, b])
    assert folded.symbols["foo"] == "foo why"
    assert folded.symbols["bar"] == "bar why"


def test_fold_latest_symbol_intent_wins():
    a = _make_entry(symbol="foo", event="created", rationale="initial")
    b = _make_entry(symbol="foo", event="modified", rationale="updated for incident X")
    folded = fold_entries([a, b])
    assert folded.symbols["foo"] == "updated for incident X"


def test_fold_skips_deleted_symbol():
    a = _make_entry(symbol="foo", event="created", rationale="initial")
    b = _make_entry(symbol="foo", event="deleted", rationale="removed — superseded by bar")
    folded = fold_entries([a, b])
    assert "foo" not in folded.symbols
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_store.py -v`

Expected: FAIL with `ImportError: cannot import name 'fold_entries'`

- [ ] **Step 3: Implement `fold_entries`**

Append to `~/Desktop/xeno/contx/contx/store.py`:

```python


from dataclasses import dataclass, field


@dataclass(frozen=True)
class FoldedIntent:
    """The 'current view' of a file's intent after folding all entries."""
    file_intent: str | None
    symbols: dict[str, str] = field(default_factory=dict)


def fold_entries(entries: list[Entry]) -> FoldedIntent:
    """Collapse an append-only log into the current intent view.

    Rules:
    - Entries are processed in file order (already sorted by caller).
    - For kind=file: latest rationale wins.
    - For kind=symbol: latest rationale wins per symbol, EXCEPT event=deleted
      removes the symbol entirely.
    - rename_out / move_out events remove the entry under the old symbol;
      the new symbol's history lives in a different sidecar.
    """
    file_intent: str | None = None
    symbols: dict[str, str] = {}
    for e in entries:
        if e.kind == "file":
            if e.event == "deleted":
                file_intent = None
            else:
                file_intent = e.rationale
        elif e.kind == "symbol" and e.symbol is not None:
            if e.event in ("deleted", "renamed_out", "moved_out"):
                symbols.pop(e.symbol, None)
            else:
                symbols[e.symbol] = e.rationale
    return FoldedIntent(file_intent=file_intent, symbols=symbols)
```

- [ ] **Step 4: Run all tests**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_store.py -v`

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/store.py tests/test_store.py
git commit -m "feat(store): add fold_entries to compute current intent view

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: CLI — `contx init` command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Write to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_init_creates_contx_dir_and_config(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_repo / ".contx").is_dir()
    assert (tmp_repo / ".contx" / "config.json").is_file()


def test_init_idempotent(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "already initialized" in result.stdout.lower()


def test_init_outside_git_repo_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "not inside a git repo" in result.stdout.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py::test_init_creates_contx_dir_and_config -v`

Expected: FAIL — no `init` command exists yet.

- [ ] **Step 3: Implement the `init` command**

Replace the contents of `~/Desktop/xeno/contx/contx/cli.py` with:

```python
"""contx CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer

from contx import __version__
from contx.config import default_config, save_config
from contx.repo import (
    NotInRepoError,
    find_repo_root,
    is_initialized,
)

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
def init() -> None:
    """Initialize contx for the current git repo."""
    repo = _resolve_repo()
    if is_initialized(repo):
        typer.echo(f"contx already initialized at {repo / '.contx'}")
        return
    save_config(repo, default_config())
    typer.echo(f"initialized contx at {repo / '.contx'}")
```

- [ ] **Step 4: Run the tests**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/cli.py tests/test_cli.py
git commit -m "feat(cli): add 'contx init' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: CLI — `contx append` command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
def test_append_writes_entry(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        [
            "append",
            "--ref", "src/auth/login.py::User.authenticate",
            "--event", "created",
            "--rationale", "GDPR — email-only login",
            "--tag", "compliance",
            "--tag", "gdpr",
        ],
    )
    assert result.exit_code == 0, result.stdout
    sidecar = tmp_repo / ".contx" / "src" / "auth" / "login.py.jsonl"
    assert sidecar.is_file()
    content = sidecar.read_text()
    assert "User.authenticate" in content
    assert "GDPR" in content
    assert "compliance" in content


def test_append_requires_init(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(
        app,
        ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "x"],
    )
    assert result.exit_code != 0
    assert "not initialized" in result.stdout.lower()


def test_append_file_level_when_no_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "module purpose"],
    )
    assert result.exit_code == 0, result.stdout
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    content = sidecar.read_text()
    assert '"kind":"file"' in content or '"kind": "file"' in content
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: 3 new tests FAIL — no `append` command yet.

- [ ] **Step 3: Implement the `append` command**

Append to `~/Desktop/xeno/contx/contx/cli.py`:

```python


from datetime import datetime, timezone

from ulid import ULID

from contx.entry import Entry
from contx.paths import parse_symbol_ref
from contx.store import append_entry


def _git_author(repo: Path) -> str:
    """Read the user.email from git config, falling back to 'unknown'."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "config", "user.email"],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip() or "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


@app.command()
def append(
    ref: str = typer.Option(..., "--ref", help="file path, e.g. src/foo.py or src/foo.py::Class.method"),
    event: str = typer.Option(..., "--event", help="created|modified|renamed_in|renamed_out|moved_in|moved_out|deleted"),
    rationale: str = typer.Option(..., "--rationale", help="The *why* — free text"),
    tag: list[str] = typer.Option(None, "--tag", help="Optional tag (repeatable)"),
    related: list[str] = typer.Option(None, "--related", help="Related symbol refs (repeatable)"),
    agent: str = typer.Option("human-cli", "--agent", help="Source: claude-code|cursor|human-cli|audit"),
) -> None:
    """Append a context entry for a file or symbol."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    file_path, symbol = parse_symbol_ref(ref)
    entry = Entry(
        id=str(ULID()),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=list(tag or []),
        author=_git_author(repo),
        timestamp=datetime.now(timezone.utc),
        agent=agent,  # type: ignore[arg-type]
        related=list(related or []),
    )
    sidecar = append_entry(repo, file_path, entry)
    typer.echo(f"appended entry {entry.id} → {sidecar.relative_to(repo)}")
```

- [ ] **Step 4: Run the tests**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/cli.py tests/test_cli.py
git commit -m "feat(cli): add 'contx append' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: CLI — `contx show` command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
def test_show_file_level(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, [
        "append", "--ref", "src/foo.py",
        "--event", "created", "--rationale", "module purpose XYZ",
    ])
    result = runner.invoke(app, ["show", "src/foo.py"])
    assert result.exit_code == 0, result.stdout
    assert "module purpose XYZ" in result.stdout


def test_show_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, [
        "append", "--ref", "src/foo.py::do_thing",
        "--event", "created", "--rationale", "because reasons XYZ",
    ])
    result = runner.invoke(app, ["show", "src/foo.py::do_thing"])
    assert result.exit_code == 0, result.stdout
    assert "because reasons XYZ" in result.stdout


def test_show_missing_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["show", "src/foo.py::nope"])
    assert result.exit_code == 0
    assert "no context" in result.stdout.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: 3 new tests FAIL — no `show` command yet.

- [ ] **Step 3: Implement the `show` command**

Append to `~/Desktop/xeno/contx/contx/cli.py`:

```python


from contx.store import fold_entries, read_entries


@app.command()
def show(ref: str = typer.Argument(..., help="file path, or file::symbol")) -> None:
    """Print the folded current intent for a file or symbol."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    file_path, symbol = parse_symbol_ref(ref)
    entries = read_entries(repo, file_path)
    folded = fold_entries(entries)

    if symbol is None:
        if folded.file_intent is None:
            typer.echo(f"no context for {file_path}")
            return
        typer.echo(f"# {file_path}")
        typer.echo(folded.file_intent)
        if folded.symbols:
            typer.echo("")
            typer.echo(f"## symbols ({len(folded.symbols)})")
            for sym in sorted(folded.symbols):
                typer.echo(f"- {sym}")
        return

    if symbol not in folded.symbols:
        typer.echo(f"no context for {file_path}::{symbol}")
        return
    typer.echo(f"# {file_path}::{symbol}")
    typer.echo(folded.symbols[symbol])
```

- [ ] **Step 4: Run the tests**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/cli.py tests/test_cli.py
git commit -m "feat(cli): add 'contx show' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: CLI — `contx log` command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `~/Desktop/xeno/contx/tests/test_cli.py`:

```python
def test_log_shows_all_entries_for_file(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "AAA"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "created", "--rationale", "BBB"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "modified", "--rationale", "CCC"])
    result = runner.invoke(app, ["log", "src/foo.py"])
    assert result.exit_code == 0, result.stdout
    assert "AAA" in result.stdout
    assert "BBB" in result.stdout
    assert "CCC" in result.stdout


def test_log_filters_by_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "FILE"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "created", "--rationale", "BAR-1"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::baz", "--event", "created", "--rationale", "BAZ-1"])
    result = runner.invoke(app, ["log", "src/foo.py::bar"])
    assert result.exit_code == 0
    assert "BAR-1" in result.stdout
    assert "BAZ-1" not in result.stdout
    assert "FILE" not in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: 2 new tests FAIL — no `log` command yet.

- [ ] **Step 3: Implement the `log` command**

Append to `~/Desktop/xeno/contx/contx/cli.py`:

```python


@app.command(name="log")
def log_cmd(ref: str = typer.Argument(..., help="file path, or file::symbol")) -> None:
    """Print the full append-only log for a file or symbol."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    file_path, symbol = parse_symbol_ref(ref)
    entries = read_entries(repo, file_path)
    if symbol is not None:
        entries = [e for e in entries if e.symbol == symbol]

    if not entries:
        typer.echo(f"no entries for {ref}")
        return

    for e in entries:
        sym = f"::{e.symbol}" if e.symbol else ""
        typer.echo(f"--- {e.timestamp.isoformat()} | {e.event} | {e.author} | {file_path}{sym}")
        if e.tags:
            typer.echo(f"tags: {', '.join(e.tags)}")
        typer.echo(e.rationale)
        typer.echo("")
```

- [ ] **Step 4: Run the tests**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_cli.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx
git add contx/cli.py tests/test_cli.py
git commit -m "feat(cli): add 'contx log' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: End-to-end smoke test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write the smoke test**

Write to `~/Desktop/xeno/contx/tests/test_e2e.py`:

```python
"""End-to-end test: simulate a full session using the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_full_lifecycle(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)

    # init
    r = runner.invoke(app, ["init"])
    assert r.exit_code == 0
    assert (tmp_repo / ".contx" / "config.json").is_file()

    # file-level entry
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py",
        "--event", "created", "--rationale", "Auth module — owns SSO + email login",
        "--tag", "module-purpose",
    ])
    assert r.exit_code == 0

    # symbol creation
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py::User.authenticate",
        "--event", "created",
        "--rationale", "Email-only because Legal said phone OTP fails GDPR",
        "--tag", "compliance", "--tag", "gdpr",
    ])
    assert r.exit_code == 0

    # symbol modified
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py::User.authenticate",
        "--event", "modified",
        "--rationale", "Added rate limit — May incident burst attack",
        "--tag", "incident", "--tag", "security",
    ])
    assert r.exit_code == 0

    # show file
    r = runner.invoke(app, ["show", "src/auth/login.py"])
    assert r.exit_code == 0
    assert "Auth module" in r.stdout
    assert "User.authenticate" in r.stdout

    # show symbol — should give latest rationale (modified)
    r = runner.invoke(app, ["show", "src/auth/login.py::User.authenticate"])
    assert r.exit_code == 0
    assert "May incident" in r.stdout
    assert "GDPR" not in r.stdout  # superseded by latest

    # log symbol — should have both entries in order
    r = runner.invoke(app, ["log", "src/auth/login.py::User.authenticate"])
    assert r.exit_code == 0
    assert r.stdout.index("GDPR") < r.stdout.index("May incident")
```

- [ ] **Step 2: Run the test**

Run: `cd ~/Desktop/xeno/contx && pytest tests/test_e2e.py -v`

Expected: PASS.

- [ ] **Step 3: Run the entire suite with coverage**

Run: `cd ~/Desktop/xeno/contx && pytest`

Expected: All tests PASS. Coverage ≥80% per project rules.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx
git add tests/test_e2e.py
git commit -m "test(e2e): add end-to-end lifecycle smoke test

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 1 only):**
- §4.1 Storage layout — Tasks 3, 6 (sidecar paths + append)
- §4.2 Entry schema (minus derived commit_sha) — Task 2
- §4.3 Two temporal modes (current + log) — Task 7 fold, Task 11 log
- §5 Granularity config — Task 5
- §10 CLI commands: `init`, `show`, `log` — Tasks 8, 10, 11
- §10 CLI: `append` (used by humans + later by MCP) — Task 9
- §13 Tech stack — Task 1
- §14 Testing — every task is TDD; Task 12 is end-to-end

**Plan 1 deliberately does NOT cover (these are Plans 2–5):**
- §6 Identity / refactor propagation (`contx_rename`) — requires the MCP integration to make sense in workflow; Plan 2.
- §7 Capture workflow (inline + commit-time extraction) — Plan 3.
- §8 MCP tool surface — Plan 2.
- §9 Claude Code skill — Plan 4.
- §10 `audit`, `serve`, `export` commands — `audit` is Plan 3, `serve` is Plan 5, `export` is Plan 5.
- §11 Web UI — Plan 5.
- §12 Git integration / hooks — Plan 3.

**Placeholder scan:** no TBDs, no "implement appropriate X" hand-waving. Every step has the actual code.

**Type consistency:** `Entry`, `Config`, `FoldedIntent` defined once and used consistently. `parse_symbol_ref` returns `(file_path, symbol_or_None)` — used identically in every CLI command that takes a ref.

---

## What ships after Plan 1

A `contx` CLI binary that can:
- `contx init` — set up a repo
- `contx append --ref ... --event ... --rationale ...` — manually add an entry
- `contx show <ref>` — read the folded current intent
- `contx log <ref>` — read the full history

Not yet automated via AI. The next plans add MCP (so Claude can append), the commit-time workflow (so modifications get captured automatically), the Claude Code skill (so the agent knows to use the MCP), and the web UI (so humans can browse).

---

## Next: Plan 2

Plan 2 will cover the MCP server: tools `contx_append`, `contx_query`, `contx_search`, `contx_rename`, `contx_delete`, `contx_audit`, all wrapping the storage layer this plan builds.
