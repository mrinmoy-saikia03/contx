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
