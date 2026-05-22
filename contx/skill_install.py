"""Install/uninstall the contx skill into a Claude Code skills directory."""

from __future__ import annotations

import shutil
from pathlib import Path

SKILL_NAME = "contx"
SKILL_FILE = "SKILL.md"


def _default_claude_home() -> Path:
    return Path.home() / ".claude"


def _source_skill_path(src_repo: Path) -> Path:
    return src_repo / "skills" / SKILL_NAME / SKILL_FILE


def _dest_skill_dir(claude_home: Path) -> Path:
    return claude_home / "skills" / SKILL_NAME


def install_skill(*, src_repo: Path, claude_home: Path | None = None) -> Path:
    claude_home = claude_home or _default_claude_home()
    src = _source_skill_path(src_repo)
    if not src.is_file():
        raise FileNotFoundError(f"Source skill not found: {src}")
    dest_dir = _dest_skill_dir(claude_home)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / SKILL_FILE
    shutil.copyfile(src, dest)
    return dest


def is_skill_installed(*, claude_home: Path | None = None) -> bool:
    claude_home = claude_home or _default_claude_home()
    return (_dest_skill_dir(claude_home) / SKILL_FILE).is_file()


def uninstall_skill(*, claude_home: Path | None = None) -> None:
    claude_home = claude_home or _default_claude_home()
    d = _dest_skill_dir(claude_home)
    if d.is_dir():
        shutil.rmtree(d)
