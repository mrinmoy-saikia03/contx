"""Install/uninstall the contx skill + slash commands into a Claude Code home directory."""

from __future__ import annotations

import shutil
from pathlib import Path

SKILL_NAME = "contx"
SKILL_FILE = "SKILL.md"
COMMANDS_PREFIX = "contx-"


def _default_claude_home() -> Path:
    return Path.home() / ".claude"


def _source_skill_path(src_repo: Path) -> Path:
    return src_repo / "skills" / SKILL_NAME / SKILL_FILE


def _source_commands_dir(src_repo: Path) -> Path:
    return src_repo / "skills" / SKILL_NAME / "commands"


def _dest_skill_dir(claude_home: Path) -> Path:
    return claude_home / "skills" / SKILL_NAME


def _dest_commands_dir(claude_home: Path) -> Path:
    return claude_home / "commands"


def install_skill(*, src_repo: Path, claude_home: Path | None = None) -> Path:
    """Copy SKILL.md and slash-command files into the Claude home directory."""
    claude_home = claude_home or _default_claude_home()
    src = _source_skill_path(src_repo)
    if not src.is_file():
        raise FileNotFoundError(f"Source skill not found: {src}")

    dest_dir = _dest_skill_dir(claude_home)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / SKILL_FILE
    shutil.copyfile(src, dest)

    # Also copy any contx-*.md slash commands.
    src_cmds = _source_commands_dir(src_repo)
    if src_cmds.is_dir():
        dest_cmds = _dest_commands_dir(claude_home)
        dest_cmds.mkdir(parents=True, exist_ok=True)
        for cmd_file in src_cmds.glob(f"{COMMANDS_PREFIX}*.md"):
            shutil.copyfile(cmd_file, dest_cmds / cmd_file.name)

    return dest


def is_skill_installed(*, claude_home: Path | None = None) -> bool:
    claude_home = claude_home or _default_claude_home()
    return (_dest_skill_dir(claude_home) / SKILL_FILE).is_file()


def uninstall_skill(*, claude_home: Path | None = None) -> None:
    """Remove the contx skill dir AND any contx-* slash commands."""
    claude_home = claude_home or _default_claude_home()
    d = _dest_skill_dir(claude_home)
    if d.is_dir():
        shutil.rmtree(d)
    cmds_dir = _dest_commands_dir(claude_home)
    if cmds_dir.is_dir():
        for cmd_file in cmds_dir.glob(f"{COMMANDS_PREFIX}*.md"):
            cmd_file.unlink()
