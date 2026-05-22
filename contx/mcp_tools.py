"""Pure-Python implementations of contx MCP tools.

Kept separate from `mcp_server.py` so the logic can be tested without
spinning up an MCP runtime.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from ulid import ULID

from contx.config import load_config
from contx.entry import Entry
from contx.paths import CTX_DIR, SIDECAR_SUFFIX, source_path_for_sidecar
from contx.search import search_entries
from contx.store import append_entry, fold_entries, read_entries


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

    Returns dict with `entry` (serialized Entry) and `sidecar` (relative path string).
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


def search(repo_root: Path, query: str, limit: int | None = None) -> list[dict]:
    """Substring search across all contx entries."""
    return search_entries(repo_root, query, limit=limit)


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
    rationale = rationale or (
        f"{'renamed' if same_file else 'moved'} "
        f"{old_file}::{old_symbol or ''} → {new_file}::{new_symbol or ''}"
    )
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


def audit(repo_root: Path) -> dict:
    """Find orphan sidecars and untracked source files.

    Reads config from .contx/config.json for languages + ignore patterns.
    """
    try:
        cfg = load_config(repo_root)
    except FileNotFoundError:
        return {"orphan_sidecars": [], "untracked_files": [], "warning": "contx not initialized"}

    extensions = {f".{ext}" for ext in cfg.languages}
    from contx.ignore import load_effective_ignore_patterns, matches_any_pattern
    ignore = load_effective_ignore_patterns(repo_root)

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
        if matches_any_pattern(rel, ignore):
            continue
        sidecar = ctx_dir / (rel + SIDECAR_SUFFIX)
        if not sidecar.is_file():
            untracked.append(rel)

    return {"orphan_sidecars": orphans, "untracked_files": untracked}
