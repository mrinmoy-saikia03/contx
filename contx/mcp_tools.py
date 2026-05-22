"""Pure-Python implementations of contx MCP tools.

Kept separate from `mcp_server.py` so the logic can be tested without
spinning up an MCP runtime.
"""

from __future__ import annotations

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
