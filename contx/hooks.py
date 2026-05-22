"""Install and uninstall the contx pre-commit hook.

The hook is a short sh script that calls `contx _precommit-check`. We
append it to any existing pre-commit hook (rather than replacing) to play
nicely with other tooling like pre-commit framework, husky, etc.

Idempotence is detected by a sentinel line we insert around our block.
"""

from __future__ import annotations

import stat
from pathlib import Path

HOOK_SENTINEL = "# >>> contx pre-commit hook >>>"
HOOK_END_SENTINEL = "# <<< contx pre-commit hook <<<"

HOOK_BLOCK = f"""\

{HOOK_SENTINEL}
# Managed by `contx init` — to remove, run `contx uninstall-hook`.
if command -v contx >/dev/null 2>&1; then
    contx _precommit-check || exit 1
fi
{HOOK_END_SENTINEL}
"""

HOOK_SHEBANG = "#!/bin/sh\n"


def _hook_path(repo_root: Path) -> Path:
    return repo_root / ".git" / "hooks" / "pre-commit"


def is_pre_commit_hook_installed(repo_root: Path) -> bool:
    hook = _hook_path(repo_root)
    if not hook.is_file():
        return False
    return HOOK_SENTINEL in hook.read_text()


def install_pre_commit_hook(repo_root: Path) -> Path:
    """Install (or top-up) the contx block in .git/hooks/pre-commit.

    Idempotent. Preserves any existing hook content. Returns the hook path.
    """
    hook = _hook_path(repo_root)
    hook.parent.mkdir(parents=True, exist_ok=True)

    existing = hook.read_text() if hook.is_file() else ""

    if HOOK_SENTINEL in existing:
        return hook  # already installed

    if not existing:
        new_content = HOOK_SHEBANG + HOOK_BLOCK
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + HOOK_BLOCK

    hook.write_text(new_content)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def uninstall_pre_commit_hook(repo_root: Path) -> None:
    """Strip the contx block from .git/hooks/pre-commit.

    If after removal the hook is just a shebang or empty, delete the file.
    """
    hook = _hook_path(repo_root)
    if not hook.is_file():
        return
    content = hook.read_text()
    if HOOK_SENTINEL not in content:
        return

    lines = content.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == HOOK_SENTINEL:
            skipping = True
            continue
        if line.strip() == HOOK_END_SENTINEL:
            skipping = False
            continue
        if not skipping:
            out.append(line)

    stripped = "".join(out).rstrip()
    if not stripped or stripped == HOOK_SHEBANG.rstrip():
        hook.unlink()
        return
    hook.write_text(stripped + "\n")
