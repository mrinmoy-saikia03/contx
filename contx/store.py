"""High-level store: append and read entries from sidecar JSONL files."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
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
    Corrupt lines are skipped with a warning rather than raising.
    """
    sidecar = sidecar_path_for_source(repo_root, Path(source_rel_path))
    if not sidecar.is_file():
        return []
    out: list[Entry] = []
    with sidecar.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(Entry.from_jsonl_line(line))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                warnings.warn(
                    f"{sidecar}:{lineno}: skipping corrupt entry: {exc}",
                    stacklevel=2,
                )
    return out


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
