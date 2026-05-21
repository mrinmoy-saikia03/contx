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
