"""Compute drift between staged code changes and staged contx sidecars."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

from contx.config import load_config
from contx.paths import CTX_DIR, SIDECAR_SUFFIX


@dataclass(frozen=True)
class Drift:
    """Result of comparing staged source changes with staged sidecar changes."""
    missing: list[str] = field(default_factory=list)
    uninitialized: bool = False


def list_staged_paths(repo_root: Path) -> list[str]:
    """Return staged file paths relative to repo root (ACMRT — no deletes)."""
    out = subprocess.run(
        [
            "git", "-C", str(repo_root),
            "diff", "--cached", "--name-only",
            "--diff-filter=ACMRT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _segments_match(parts: list[str], pat_parts: list[str]) -> bool:
    """Recursive ** glob matcher (segment-based)."""
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


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    parts = rel_path.split("/")
    for pat in patterns:
        if _segments_match(parts, pat.split("/")):
            return True
    return False


def compute_drift(repo_root: Path) -> Drift:
    """Compare staged source files against staged sidecar files."""
    try:
        cfg = load_config(repo_root)
    except FileNotFoundError:
        return Drift(missing=[], uninitialized=True)

    extensions = {f".{ext}" for ext in cfg.languages}
    ignore = cfg.ignore

    staged = list_staged_paths(repo_root)
    staged_sidecars = {
        p for p in staged
        if p.startswith(f"{CTX_DIR}/") and p.endswith(SIDECAR_SUFFIX)
    }

    paired_sources: set[str] = set()
    for sc in staged_sidecars:
        inner = sc[len(CTX_DIR) + 1:]
        if inner.endswith(SIDECAR_SUFFIX):
            paired_sources.add(inner[: -len(SIDECAR_SUFFIX)])

    missing: list[str] = []
    for p in staged:
        if p.startswith(f"{CTX_DIR}/"):
            continue
        ext = Path(p).suffix
        if ext not in extensions:
            continue
        if _matches_any(p, ignore):
            continue
        if p in paired_sources:
            continue
        missing.append(p)

    return Drift(missing=missing, uninitialized=False)
