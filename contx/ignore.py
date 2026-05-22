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
    """Read .contxignore at repo_root, strip comments and blanks, return patterns."""
    path = repo_root / CONTXIGNORE_FILENAME
    if not path.is_file():
        return []
    patterns: list[str] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def load_effective_ignore_patterns(repo_root: Path) -> list[str]:
    """Return combined config.ignore + .contxignore patterns.

    config.ignore comes first (so repo-level .contxignore appends).
    If config.json is missing, only .contxignore patterns are returned.
    """
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
