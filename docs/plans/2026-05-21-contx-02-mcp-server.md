# contx — Plan 2: MCP Server

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the Plan 1 storage layer as MCP tools so AI coding agents (Claude Code, Cursor, etc.) can read and write contx entries during a coding session. Output: a `contx-mcp` server binary that any MCP-compatible host can launch over stdio.

**Architecture:** A new `contx/mcp_server.py` module uses the official `mcp` Python SDK (`FastMCP`). Each MCP tool is a thin wrapper around an existing function in `contx.store`, `contx.entry`, or `contx.repo`. No new business logic — Plan 2 is *the integration layer*. Repo root is resolved from `os.getcwd()` at startup with `CONTX_REPO_ROOT` env var as override.

**Tech Stack:** Python 3.11+, `mcp>=1.0.0` (official Anthropic SDK), `python-ulid`, pytest. Stdio transport (MCP default).

**Companion spec:** `~/Desktop/xeno/contx/docs/specs/2026-05-21-contx-design.md` §8 (MCP Tool Surface).

---

## File Structure

```
~/Desktop/xeno/contx/
├── pyproject.toml                       # MODIFY: add mcp dep + contx-mcp script
├── contx/
│   ├── mcp_server.py                    # NEW: FastMCP server + 6 tools
│   ├── mcp_tools.py                     # NEW: tool implementations (pure functions, no MCP dep)
│   └── search.py                        # NEW: substring search across sidecars
└── tests/
    ├── test_mcp_tools.py                # NEW: unit tests for each tool function
    ├── test_search.py                   # NEW: unit tests for search
    └── test_mcp_e2e.py                  # NEW: end-to-end via in-process MCP client
```

**Separation of concerns:**
- `mcp_tools.py` holds plain Python functions (the *what* each tool does). Testable without any MCP runtime.
- `mcp_server.py` is the FastMCP wiring (the *how* MCP exposes them). Thin.
- `search.py` is its own module because substring search across the `.contx/` tree is non-trivial and reusable from the future web UI.

---

## Task 1: Add `mcp` dependency + scaffold server module

**Files:**
- Modify: `~/Desktop/xeno/contx/pyproject.toml`
- Create: `~/Desktop/xeno/contx/contx/mcp_server.py`
- Create: `~/Desktop/xeno/contx/contx/mcp_tools.py`

- [ ] **Step 1: Update `pyproject.toml`**

Read `~/Desktop/xeno/contx/pyproject.toml`. Find the `dependencies` list under `[project]`. Add `"mcp>=1.0.0"`. Under `[project.scripts]`, add `contx-mcp = "contx.mcp_server:main"`.

Result excerpt:
```toml
dependencies = [
    "typer>=0.12.0",
    "python-ulid>=2.2.0",
    "mcp>=1.0.0",
]

[project.scripts]
contx = "contx.cli:app"
contx-mcp = "contx.mcp_server:main"
```

- [ ] **Step 2: Reinstall to pick up new dependency**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pip install -e .[dev]
```

Expected: installs `mcp` and any transitive deps successfully.

- [ ] **Step 3: Create the empty server module stub**

`~/Desktop/xeno/contx/contx/mcp_tools.py`:

```python
"""Pure-Python implementations of contx MCP tools.

Kept separate from `mcp_server.py` so the logic can be tested without
spinning up an MCP runtime.
"""

from __future__ import annotations
```

`~/Desktop/xeno/contx/contx/mcp_server.py`:

```python
"""MCP server exposing contx tools to AI coding agents."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from contx.repo import NotInRepoError, find_repo_root

app: FastMCP = FastMCP("contx")


def resolve_repo_root() -> Path:
    """Resolve the contx repo root: CONTX_REPO_ROOT env var, else cwd.

    Called at the start of every tool. Raises if not inside a git repo.
    """
    override = os.environ.get("CONTX_REPO_ROOT")
    start = Path(override) if override else Path.cwd()
    return find_repo_root(start)


def main() -> None:
    """Entry point — run the MCP server over stdio."""
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the stub runs**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && python -c "from contx.mcp_server import app; print(app.name)"
```

Expected output: `contx`

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add pyproject.toml contx/mcp_server.py contx/mcp_tools.py && git commit -m "chore(mcp): scaffold MCP server module + add mcp dependency

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `contx_query` tool (TDD)

**Files:**
- Create: `~/Desktop/xeno/contx/tests/test_mcp_tools.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_tools.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_server.py`

`contx_query(file, symbol=None)` returns the folded intent + raw log for a file or symbol.

- [ ] **Step 1: Write the failing test**

`~/Desktop/xeno/contx/tests/test_mcp_tools.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.mcp_tools import query as query_tool
from contx.store import append_entry


def _entry(symbol: str | None, event: str, rationale: str) -> Entry:
    return Entry(
        id=f"01H{(symbol or 'F')[:4]}0000000000000000000K"[:26].ljust(26, "0"),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=[],
        author="test@example.com",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )


def test_query_file_returns_folded_intent_and_log(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "email-only because GDPR"))
    result = query_tool(tmp_repo, "src/auth.py", symbol=None)
    assert result["file_intent"] == "auth module"
    assert "login" in result["symbols"]
    assert result["symbols"]["login"] == "email-only because GDPR"
    assert len(result["log"]) == 2


def test_query_symbol_returns_just_that_symbol(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "email-only"))
    result = query_tool(tmp_repo, "src/auth.py", symbol="login")
    assert result["symbol_intent"] == "email-only"
    # log filtered to that symbol only
    assert all(e["symbol"] == "login" for e in result["log"])


def test_query_missing_file_returns_empty(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = query_tool(tmp_repo, "src/nope.py", symbol=None)
    assert result["file_intent"] is None
    assert result["symbols"] == {}
    assert result["log"] == []


def test_query_missing_symbol_returns_none(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    result = query_tool(tmp_repo, "src/auth.py", symbol="nope")
    assert result["symbol_intent"] is None
```

- [ ] **Step 2: Run, verify failures**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_mcp_tools.py -v
```

Expected: `ImportError: cannot import name 'query'`.

- [ ] **Step 3: Implement `query` in `mcp_tools.py`**

Append to `~/Desktop/xeno/contx/contx/mcp_tools.py`:

```python


from pathlib import Path

from contx.entry import Entry
from contx.store import fold_entries, read_entries


def _entry_to_dict(e: Entry) -> dict:
    """Serialize an Entry to a plain dict suitable for MCP JSON responses."""
    return e.to_dict()


def query(repo_root: Path, file: str, symbol: str | None = None) -> dict:
    """Read folded intent + raw log for a file or symbol.

    Returns a dict shaped:
      - file_intent: str | None
      - symbols: dict[str, str]      (always present; symbol → folded rationale)
      - symbol_intent: str | None    (present only when symbol is requested)
      - log: list[dict]              (raw entries in file order; filtered by symbol if requested)
    """
    entries = read_entries(repo_root, file)
    folded = fold_entries(entries)

    log = entries
    if symbol is not None:
        log = [e for e in entries if e.symbol == symbol]

    out: dict = {
        "file_intent": folded.file_intent,
        "symbols": dict(folded.symbols),
        "log": [_entry_to_dict(e) for e in log],
    }
    if symbol is not None:
        out["symbol_intent"] = folded.symbols.get(symbol)
    return out
```

- [ ] **Step 4: Verify tests pass**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_mcp_tools.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Register the MCP tool wrapper in `mcp_server.py`**

Append to `~/Desktop/xeno/contx/contx/mcp_server.py`:

```python


from contx import mcp_tools


@app.tool()
def contx_query(file: str, symbol: str | None = None) -> dict:
    """Read the folded intent and full log for a file or symbol.

    Use this BEFORE editing a file to learn its existing context.

    Args:
        file: Path to the source file, relative to the repo root.
        symbol: Optional dotted symbol path within the file (e.g. "Class.method").
                When omitted, returns the file-level intent and lists all symbols.

    Returns:
        file_intent: The folded "current" file-level rationale, or None.
        symbols: Dict mapping symbol name to its current rationale.
        symbol_intent: Present only when symbol is provided; the symbol's current rationale or None.
        log: Raw entries (filtered by symbol if specified) in file order.
    """
    repo = resolve_repo_root()
    return mcp_tools.query(repo, file, symbol=symbol)
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py contx/mcp_server.py tests/test_mcp_tools.py && git commit -m "feat(mcp): add contx_query tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `contx_append` tool (TDD)

**Files:**
- Modify: `~/Desktop/xeno/contx/tests/test_mcp_tools.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_tools.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_server.py`

`contx_append` is the write path used by AI agents.

- [ ] **Step 1: Append tests**

```python
from contx.mcp_tools import append as append_tool


def test_append_symbol_creates_sidecar(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = append_tool(
        tmp_repo,
        file="src/auth.py",
        event="created",
        rationale="email-only login because GDPR",
        symbol="login",
        tags=["compliance"],
        related=[],
        agent="claude-code",
    )
    assert result["sidecar"].endswith("src/auth.py.jsonl")
    assert result["entry"]["symbol"] == "login"
    assert result["entry"]["event"] == "created"
    assert "compliance" in result["entry"]["tags"]
    # Verify it actually landed on disk
    sidecar = tmp_repo / ".contx" / "src" / "auth.py.jsonl"
    assert sidecar.is_file()
    assert "GDPR" in sidecar.read_text()


def test_append_file_kind(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = append_tool(
        tmp_repo,
        file="src/auth.py",
        event="created",
        rationale="owns SSO + email login",
        symbol=None,
        tags=[],
        related=[],
        agent="claude-code",
    )
    assert result["entry"]["kind"] == "file"
    assert result["entry"]["symbol"] is None


def test_append_rejects_invalid_event(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    with pytest.raises(ValueError, match="event must be"):
        append_tool(
            tmp_repo,
            file="src/auth.py",
            event="banana",
            rationale="x",
            symbol=None,
            tags=[],
            related=[],
            agent="claude-code",
        )
```

- [ ] **Step 2: Run, verify failure**

Expected: `ImportError: cannot import name 'append'`.

- [ ] **Step 3: Implement `append` in `mcp_tools.py`**

```python


from datetime import datetime, timezone

from ulid import ULID

from contx.store import append_entry


def append(
    repo_root: Path,
    file: str,
    event: str,
    rationale: str,
    symbol: str | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
    agent: str = "claude-code",
) -> dict:
    """Append a new context entry. ValueError on invalid inputs.

    Returns dict with `entry` (serialized Entry) and `sidecar` (path string).
    """
    entry = Entry(
        id=str(ULID()),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=list(tags or []),
        author=os.environ.get("CONTX_AUTHOR", "claude-code"),
        timestamp=datetime.now(timezone.utc),
        agent=agent,  # type: ignore[arg-type]
        related=list(related or []),
    )
    sidecar = append_entry(repo_root, file, entry)
    return {
        "entry": _entry_to_dict(entry),
        "sidecar": str(sidecar.relative_to(repo_root)),
    }
```

Add `import os` at top of file if not present.

- [ ] **Step 4: Verify tests pass**

Expected: 7 PASS (4 from Task 2 + 3 new).

- [ ] **Step 5: Register MCP tool**

```python
@app.tool()
def contx_append(
    file: str,
    event: str,
    rationale: str,
    symbol: str | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
) -> dict:
    """Append a context entry for a file or symbol.

    Call this whenever you create, modify, rename, or delete code — paired
    with the corresponding Edit/Write tool call. Never edit code without a
    matching contx_append call.

    Args:
        file: Path to the source file, relative to the repo root.
        event: One of: created, modified, renamed_in, renamed_out,
               moved_in, moved_out, deleted.
        rationale: Free-text explaining the WHY (never the WHAT — the code
                   itself shows what; the rationale captures decisions,
                   constraints, business reasons, incidents).
        symbol: Optional dotted symbol path (e.g. "Class.method"). Omit for
                file-level intent.
        tags: Optional list of tags (e.g. ["compliance", "gdpr"]).
        related: Optional list of related symbol refs.

    Returns:
        entry: The serialized entry just written.
        sidecar: Relative path to the sidecar file that was updated.
    """
    repo = resolve_repo_root()
    return mcp_tools.append(
        repo,
        file=file,
        event=event,
        rationale=rationale,
        symbol=symbol,
        tags=tags,
        related=related,
        agent="claude-code",
    )
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py contx/mcp_server.py tests/test_mcp_tools.py && git commit -m "feat(mcp): add contx_append tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `contx_search` tool + `search.py` module (TDD)

**Files:**
- Create: `~/Desktop/xeno/contx/contx/search.py`
- Create: `~/Desktop/xeno/contx/tests/test_search.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_tools.py`
- Modify: `~/Desktop/xeno/contx/contx/mcp_server.py`

MVP search: walk `.contx/` and substring-match each entry's rationale + tags.

- [ ] **Step 1: Write `tests/test_search.py`**

```python
from datetime import datetime, timezone
from pathlib import Path

from contx.entry import Entry
from contx.search import search_entries
from contx.store import append_entry


def _e(rationale: str, tags: list[str] | None = None) -> Entry:
    return Entry(
        id="01H" + rationale[:4].upper().ljust(23, "0"),
        kind="file",
        symbol=None,
        event="created",
        rationale=rationale,
        tags=tags or [],
        author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )


def test_search_finds_match_in_rationale(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("GDPR — email only"))
    append_entry(tmp_repo, "src/b.py", _e("rate limiting under load"))
    hits = search_entries(tmp_repo, "GDPR")
    assert len(hits) == 1
    assert hits[0]["file"] == "src/a.py"
    assert "GDPR" in hits[0]["entry"]["rationale"]


def test_search_is_case_insensitive(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("Compliance — GDPR"))
    hits = search_entries(tmp_repo, "compliance")
    assert len(hits) == 1


def test_search_matches_tags(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("x", tags=["gdpr"]))
    append_entry(tmp_repo, "src/b.py", _e("y", tags=["perf"]))
    hits = search_entries(tmp_repo, "gdpr")
    assert len(hits) == 1
    assert hits[0]["file"] == "src/a.py"


def test_search_returns_empty_for_no_matches(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("x"))
    assert search_entries(tmp_repo, "nope") == []


def test_search_respects_limit(tmp_repo: Path):
    for i in range(5):
        append_entry(tmp_repo, f"src/f{i}.py", _e("GDPR rule"))
    hits = search_entries(tmp_repo, "GDPR", limit=2)
    assert len(hits) == 2


def test_search_missing_contx_dir_returns_empty(tmp_repo: Path):
    assert search_entries(tmp_repo, "anything") == []
```

- [ ] **Step 2: Run, verify failure**

Expected: `ModuleNotFoundError: No module named 'contx.search'`.

- [ ] **Step 3: Implement `~/Desktop/xeno/contx/contx/search.py`**

```python
"""Substring search across all contx sidecar entries in a repo."""

from __future__ import annotations

from pathlib import Path

from contx.entry import Entry
from contx.paths import CTX_DIR, SIDECAR_SUFFIX, source_path_for_sidecar
from contx.store import read_entries


def _entry_matches(entry: Entry, needle: str) -> bool:
    n = needle.lower()
    if n in entry.rationale.lower():
        return True
    if any(n in tag.lower() for tag in entry.tags):
        return True
    return False


def search_entries(
    repo_root: Path,
    query: str,
    *,
    limit: int | None = None,
) -> list[dict]:
    """Substring search (case-insensitive) across rationale + tags.

    Returns a list of {file: str, entry: dict} dicts in directory-walk
    order. When `limit` is set, stops scanning after `limit` hits.
    """
    ctx_dir = repo_root / CTX_DIR
    if not ctx_dir.is_dir():
        return []

    hits: list[dict] = []
    for sidecar in sorted(ctx_dir.rglob(f"*{SIDECAR_SUFFIX}")):
        try:
            source = source_path_for_sidecar(repo_root, sidecar)
        except ValueError:
            continue
        rel_file = str(source.relative_to(repo_root))
        for entry in read_entries(repo_root, rel_file):
            if _entry_matches(entry, query):
                hits.append({"file": rel_file, "entry": entry.to_dict()})
                if limit is not None and len(hits) >= limit:
                    return hits
    return hits
```

- [ ] **Step 4: Verify tests pass**

Expected: 6 PASS.

- [ ] **Step 5: Add the tool to `mcp_tools.py` and `mcp_server.py`**

In `mcp_tools.py`:
```python


from contx.search import search_entries


def search(repo_root: Path, query: str, limit: int | None = None) -> list[dict]:
    """Substring search across all contx entries."""
    return search_entries(repo_root, query, limit=limit)
```

In `mcp_server.py`:
```python
@app.tool()
def contx_search(query: str, limit: int | None = 50) -> list[dict]:
    """Search for context entries by substring (case-insensitive).

    Matches against entry rationale and tags. Returns up to `limit` results.

    Args:
        query: Free-text substring to search for.
        limit: Max results to return (default 50).

    Returns:
        A list of {file, entry} dicts in walk order.
    """
    repo = resolve_repo_root()
    return mcp_tools.search(repo, query, limit=limit)
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/search.py contx/mcp_tools.py contx/mcp_server.py tests/test_search.py && git commit -m "feat(mcp): add contx_search tool with substring search

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: `contx_rename` tool (TDD)

`contx_rename(old_file, new_file, old_symbol=None, new_symbol=None, rationale=None)` — bookkeeping for refactors. Appends `renamed_out`/`moved_out` to old sidecar and `renamed_in`/`moved_in` to new sidecar.

- [ ] **Step 1: Append tests**

```python
from contx.mcp_tools import rename as rename_tool


def test_rename_within_same_file(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    result = rename_tool(
        tmp_repo,
        old_file="src/auth.py", old_symbol="login",
        new_file="src/auth.py", new_symbol="authenticate",
        rationale="renamed for clarity",
    )
    assert result["status"] == "ok"
    entries = read_entries(tmp_repo, "src/auth.py")
    events = [e.event for e in entries]
    # original + renamed_out + renamed_in, all in same file
    assert "renamed_out" in events
    assert "renamed_in" in events


def test_move_across_files(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    rename_tool(
        tmp_repo,
        old_file="src/auth.py", old_symbol="login",
        new_file="src/sso/handlers.py", new_symbol="route_eu",
        rationale="moved to SSO subpackage",
    )
    old_entries = read_entries(tmp_repo, "src/auth.py")
    new_entries = read_entries(tmp_repo, "src/sso/handlers.py")
    # old sidecar has moved_out; new sidecar has moved_in with backlink
    assert any(e.event == "moved_out" for e in old_entries)
    moved_in = [e for e in new_entries if e.event == "moved_in"]
    assert moved_in
    assert "src/auth.py::login" in moved_in[0].related
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `rename` in `mcp_tools.py`**

```python
def rename(
    repo_root: Path,
    old_file: str,
    new_file: str,
    old_symbol: str | None = None,
    new_symbol: str | None = None,
    rationale: str | None = None,
) -> dict:
    """Refactor bookkeeping: rename and/or move a file or symbol.

    Appends a `*_out` entry on the old side and a `*_in` entry on the new
    side, with `related` backlinks. Uses `renamed_*` when the file is the
    same and `moved_*` when files differ.
    """
    same_file = old_file == new_file
    out_event = "renamed_out" if same_file else "moved_out"
    in_event = "renamed_in" if same_file else "moved_in"
    rationale = rationale or f"{'renamed' if same_file else 'moved'} {old_file}::{old_symbol or ''} → {new_file}::{new_symbol or ''}"
    old_ref = f"{old_file}::{old_symbol}" if old_symbol else old_file
    new_ref = f"{new_file}::{new_symbol}" if new_symbol else new_file

    old_kind = "symbol" if old_symbol else "file"
    new_kind = "symbol" if new_symbol else "file"

    out_entry = Entry(
        id=str(ULID()),
        kind=old_kind,
        symbol=old_symbol,
        event=out_event,
        rationale=rationale,
        tags=[],
        author=os.environ.get("CONTX_AUTHOR", "claude-code"),
        timestamp=datetime.now(timezone.utc),
        agent="claude-code",
        related=[new_ref],
    )
    in_entry = Entry(
        id=str(ULID()),
        kind=new_kind,
        symbol=new_symbol,
        event=in_event,
        rationale=rationale,
        tags=[],
        author=os.environ.get("CONTX_AUTHOR", "claude-code"),
        timestamp=datetime.now(timezone.utc),
        agent="claude-code",
        related=[old_ref],
    )

    append_entry(repo_root, old_file, out_entry)
    append_entry(repo_root, new_file, in_entry)

    return {"status": "ok", "old_ref": old_ref, "new_ref": new_ref}
```

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Register MCP tool**

```python
@app.tool()
def contx_rename(
    old_file: str,
    new_file: str,
    old_symbol: str | None = None,
    new_symbol: str | None = None,
    rationale: str | None = None,
) -> dict:
    """Record a rename or move. Call this in the SAME turn as the rename Edit.

    Appends a renamed_out/moved_out entry on the old side and a
    renamed_in/moved_in entry on the new side, with backlinks. The full prior
    history stays in the old sidecar — readers follow `related` to trace.

    Args:
        old_file: Original file path.
        new_file: New file path. If same as old_file, treated as a rename.
        old_symbol: Optional original symbol path.
        new_symbol: Optional new symbol path.
        rationale: Optional explanation; a default is generated if omitted.
    """
    repo = resolve_repo_root()
    return mcp_tools.rename(
        repo,
        old_file=old_file,
        new_file=new_file,
        old_symbol=old_symbol,
        new_symbol=new_symbol,
        rationale=rationale,
    )
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py contx/mcp_server.py tests/test_mcp_tools.py && git commit -m "feat(mcp): add contx_rename tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: `contx_delete` tool (TDD)

Simple — append a `deleted` event. History is preserved; the fold logic removes the symbol from the "current" view.

- [ ] **Step 1: Append tests**

```python
from contx.mcp_tools import delete as delete_tool


def test_delete_symbol_appends_deleted_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    delete_tool(tmp_repo, file="src/auth.py", symbol="login", rationale="superseded")
    entries = read_entries(tmp_repo, "src/auth.py")
    deleted = [e for e in entries if e.event == "deleted"]
    assert len(deleted) == 1
    assert deleted[0].rationale == "superseded"


def test_delete_file_appends_deleted_file_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "v1"))
    delete_tool(tmp_repo, file="src/auth.py", symbol=None, rationale="module retired")
    entries = read_entries(tmp_repo, "src/auth.py")
    deleted = [e for e in entries if e.event == "deleted"]
    assert len(deleted) == 1
    assert deleted[0].kind == "file"
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `delete` in `mcp_tools.py`**

```python
def delete(
    repo_root: Path,
    file: str,
    rationale: str,
    symbol: str | None = None,
) -> dict:
    """Append a `deleted` entry. History is preserved."""
    entry = Entry(
        id=str(ULID()),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event="deleted",
        rationale=rationale,
        tags=[],
        author=os.environ.get("CONTX_AUTHOR", "claude-code"),
        timestamp=datetime.now(timezone.utc),
        agent="claude-code",
        related=[],
    )
    sidecar = append_entry(repo_root, file, entry)
    return {"entry": _entry_to_dict(entry), "sidecar": str(sidecar.relative_to(repo_root))}
```

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Register MCP tool**

```python
@app.tool()
def contx_delete(file: str, rationale: str, symbol: str | None = None) -> dict:
    """Record a code deletion. Pair with the actual Edit/Write that removes the code.

    History is preserved — folded views just stop including the deleted
    symbol. The append-only log still shows everything.

    Args:
        file: Path to the source file.
        rationale: Why the symbol/file was removed.
        symbol: Optional symbol path; omit for whole-file deletion.
    """
    repo = resolve_repo_root()
    return mcp_tools.delete(repo, file=file, rationale=rationale, symbol=symbol)
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py contx/mcp_server.py tests/test_mcp_tools.py && git commit -m "feat(mcp): add contx_delete tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: `contx_audit` tool (TDD)

Walks the source tree, walks `.contx/`, returns two lists:
- `orphan_sidecars`: sidecars whose source file no longer exists
- `untracked_files`: source files with no sidecar (filtered by config `languages` + `ignore`)

- [ ] **Step 1: Append tests**

```python
from contx.mcp_tools import audit as audit_tool


def test_audit_finds_orphan_sidecar(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    # Create a sidecar entry for a file that does not exist on disk
    append_entry(tmp_repo, "src/deleted.py", _entry(None, "created", "x"))
    result = audit_tool(tmp_repo)
    orphan_files = [o["file"] for o in result["orphan_sidecars"]]
    assert "src/deleted.py" in orphan_files


def test_audit_finds_untracked_python_file(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    # Create a source file but no entry
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "untracked.py").write_text("pass\n")
    result = audit_tool(tmp_repo)
    assert "src/untracked.py" in result["untracked_files"]


def test_audit_respects_ignore_patterns(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "node_modules").mkdir()
    (tmp_repo / "node_modules" / "lib.js").write_text("x")
    result = audit_tool(tmp_repo)
    assert "node_modules/lib.js" not in result["untracked_files"]


def test_audit_skips_dotcontx_dir(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    # The .contx directory itself should never be reported as untracked
    (tmp_repo / ".contx" / "config.json").touch()
    result = audit_tool(tmp_repo)
    assert not any(p.startswith(".contx/") for p in result["untracked_files"])
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `audit` in `mcp_tools.py`**

```python


from fnmatch import fnmatch

from contx.config import load_config
from contx.paths import CTX_DIR, SIDECAR_SUFFIX, source_path_for_sidecar


def _is_ignored(rel_path: str, ignore_patterns: list[str]) -> bool:
    for pat in ignore_patterns:
        if fnmatch(rel_path, pat):
            return True
    return False


def audit(repo_root: Path) -> dict:
    """Find orphan sidecars and untracked source files.

    Reads config from .contx/config.json for languages + ignore patterns.
    """
    try:
        cfg = load_config(repo_root)
    except FileNotFoundError:
        return {"orphan_sidecars": [], "untracked_files": [], "warning": "contx not initialized"}

    extensions = {f".{ext}" for ext in cfg.languages}
    ignore = cfg.ignore

    # 1. Orphan sidecars: walk .contx/, check the source it mirrors exists
    orphans: list[dict] = []
    ctx_dir = repo_root / CTX_DIR
    if ctx_dir.is_dir():
        for sidecar in sorted(ctx_dir.rglob(f"*{SIDECAR_SUFFIX}")):
            try:
                source = source_path_for_sidecar(repo_root, sidecar)
            except ValueError:
                continue
            rel = str(source.relative_to(repo_root))
            if not source.is_file():
                orphans.append({"file": rel, "sidecar": str(sidecar.relative_to(repo_root))})

    # 2. Untracked: walk repo, find files matching extensions but with no sidecar, not ignored
    untracked: list[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        rel = str(path.relative_to(repo_root))
        if rel.startswith(f"{CTX_DIR}/") or rel.startswith(".git/"):
            continue
        if _is_ignored(rel, ignore):
            continue
        sidecar = ctx_dir / (rel + SIDECAR_SUFFIX)
        if not sidecar.is_file():
            untracked.append(rel)

    return {"orphan_sidecars": orphans, "untracked_files": untracked}
```

- [ ] **Step 4: Verify tests pass**

- [ ] **Step 5: Register MCP tool**

```python
@app.tool()
def contx_audit() -> dict:
    """Find inconsistencies between the source tree and .contx/.

    Returns:
        orphan_sidecars: Sidecars whose source file no longer exists.
        untracked_files: Source files matching tracked languages but with no sidecar.
    """
    repo = resolve_repo_root()
    return mcp_tools.audit(repo)
```

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py contx/mcp_server.py tests/test_mcp_tools.py && git commit -m "feat(mcp): add contx_audit tool

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end test via in-process MCP client

**Files:**
- Create: `~/Desktop/xeno/contx/tests/test_mcp_e2e.py`

The MCP SDK exposes a client/server pair that can run in-process for tests. We use it to verify the actual stdio protocol works.

- [ ] **Step 1: Write the test**

```python
"""End-to-end test: spin up the MCP server and call tools via the client."""

import asyncio
from pathlib import Path

import pytest

from contx.config import default_config, save_config


@pytest.mark.asyncio
async def test_mcp_e2e_full_lifecycle(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Exercise the full MCP loop: connect, call contx_append, call contx_query."""
    # Point the server at our tmp_repo
    monkeypatch.setenv("CONTX_REPO_ROOT", str(tmp_repo))
    save_config(tmp_repo, default_config())

    # Import after env var is set
    from contx.mcp_server import app

    # FastMCP exposes a list_tools()-style API; verify expected tools are registered
    tools = await app.list_tools()
    tool_names = {t.name for t in tools}
    expected = {"contx_query", "contx_append", "contx_search", "contx_rename", "contx_delete", "contx_audit"}
    assert expected.issubset(tool_names), f"missing tools: {expected - tool_names}"

    # Append + query through the FastMCP call interface
    append_result = await app.call_tool(
        "contx_append",
        {
            "file": "src/auth.py",
            "event": "created",
            "rationale": "GDPR — email only",
            "symbol": "login",
            "tags": ["compliance"],
        },
    )
    # call_tool returns a list of TextContent / structured content
    assert append_result, "contx_append returned no content"

    query_result = await app.call_tool(
        "contx_query",
        {"file": "src/auth.py", "symbol": "login"},
    )
    assert query_result, "contx_query returned no content"

    # The sidecar should exist on disk
    assert (tmp_repo / ".contx" / "src" / "auth.py.jsonl").is_file()
```

Add to `pyproject.toml` dev deps: `"pytest-asyncio>=0.23"`, and in `[tool.pytest.ini_options]` add `asyncio_mode = "auto"`.

- [ ] **Step 2: Reinstall deps**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pip install -e .[dev]
```

- [ ] **Step 3: Run the test**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest tests/test_mcp_e2e.py -v
```

Expected: PASS.

Note: the FastMCP API surface may vary by version. If `app.list_tools()` or `app.call_tool()` raise `AttributeError`, consult the installed `mcp` package via `python -c "import mcp; help(mcp.server.fastmcp.FastMCP)"` and adapt the test to use the actual method names (`get_tools()`, `_call_tool()`, etc.). The expected names above match `mcp>=1.0.0`. If the version is older, upgrade.

- [ ] **Step 4: Run full suite with coverage**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest
```

Expected: all tests PASS (Plan 1's 58 + Plan 2's new ~22 = ~80). Coverage ≥80%.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add tests/test_mcp_e2e.py pyproject.toml && git commit -m "test(mcp): add end-to-end MCP server lifecycle test

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Document MCP server setup

**Files:**
- Modify: `~/Desktop/xeno/contx/README.md`

- [ ] **Step 1: Append a "Using with Claude Code" section to README**

Append to `~/Desktop/xeno/contx/README.md`:

```markdown

## Using with Claude Code (MCP)

contx ships an MCP server (`contx-mcp`) so AI coding agents can read and write context entries directly during a session.

### Add to Claude Code

Add to `~/.claude/settings.json`:

\`\`\`json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp"
    }
  }
}
\`\`\`

By default the server uses `os.getcwd()` to find the repo root (walks up looking for `.git`). To point at a specific repo, set:

\`\`\`json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp",
      "env": { "CONTX_REPO_ROOT": "/path/to/repo" }
    }
  }
}
\`\`\`

### Tools exposed

| Tool | Purpose |
|------|---------|
| `contx_query` | Read folded intent + raw log for a file or symbol. |
| `contx_append` | Add a context entry (created / modified / deleted / etc.). |
| `contx_search` | Substring search across all entries (rationale + tags). |
| `contx_rename` | Refactor bookkeeping for renames and moves. |
| `contx_delete` | Append a deletion entry (history preserved). |
| `contx_audit` | Find orphan sidecars and untracked source files. |
```

- [ ] **Step 2: Commit**

```bash
cd ~/Desktop/xeno/contx && git add README.md && git commit -m "docs: document contx-mcp setup and tool surface

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (Plan 2):**
- §8.1 `contx_init` — not added in Plan 2 (the CLI `contx init` already handles repo setup; an MCP-side init has no AI-driven use case yet). Deferred to backlog.
- §8.2 `contx_append` — Task 3 ✓
- §8.3 `contx_rename` — Task 5 ✓
- §8.4 `contx_delete` — Task 6 ✓
- §8.5 `contx_query` — Task 2 ✓
- §8.6 `contx_search` — Task 4 ✓
- §8.7 `contx_audit` — Task 7 ✓
- End-to-end test — Task 8 ✓
- Docs — Task 9 ✓

**Placeholder scan:** no TBDs. Every step has real code.

**Type consistency:** `Entry`, `FoldedIntent`, `tmp_repo` fixture, `parse_symbol_ref`, `append_entry`, `read_entries`, `fold_entries` reused exactly as defined in Plan 1. `mcp_tools.py` functions are all `(repo_root: Path, …) -> dict` shaped consistently.

**Risk on the MCP SDK surface:** FastMCP's exact method names (`list_tools`, `call_tool`) can vary by version. Task 8 includes a fallback note. If the SDK breaks, the simplest fix is to pin the version (`mcp==1.0.0` or whatever is current) and adapt the test once.

---

## What ships after Plan 2

A working MCP server that any MCP-capable AI coding host can launch. Combined with Plan 1's CLI, this is the minimum viable contx: humans use the CLI, agents use MCP, both write to the same `.contx/` mirror tree, all changes flow through git.

Plan 3 will add the commit-time extraction workflow (the pre-commit hook that mines the AI conversation transcript for rationales). Plan 4 will add the Claude Code skill that enforces "every Edit must be paired with a contx call." Plan 5 will add the local web UI.

---

## Backlog items (carried forward from Plan 1's docs/BACKLOG.md)

The following are still pending and may be folded into Plan 2 implementation if convenient, but are not required by this plan:
- `.contxignore` file (gitignore-style; complements `config.json`'s `ignore` list).
- Tuple-vs-list decision for `Entry.tags`/`Entry.related` — if changed, update `mcp_tools.append` signature accordingly.
- `__main__.py` coverage gap.
