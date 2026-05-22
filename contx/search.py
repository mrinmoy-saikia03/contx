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
