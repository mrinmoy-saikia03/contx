from pathlib import Path

import pytest

from contx.hooks import (
    HOOK_SENTINEL,
    install_pre_commit_hook,
    is_pre_commit_hook_installed,
    uninstall_pre_commit_hook,
)


def test_install_creates_hook_file(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    assert HOOK_SENTINEL in hook.read_text()
    assert hook.stat().st_mode & 0o111  # executable


def test_install_is_idempotent(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    install_pre_commit_hook(tmp_repo)
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.read_text().count(HOOK_SENTINEL) == 1


def test_install_preserves_existing_hook(tmp_repo: Path):
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho user-hook\n")
    hook.chmod(0o755)
    install_pre_commit_hook(tmp_repo)
    content = hook.read_text()
    assert "echo user-hook" in content
    assert HOOK_SENTINEL in content


def test_is_installed_reports_correctly(tmp_repo: Path):
    assert is_pre_commit_hook_installed(tmp_repo) is False
    install_pre_commit_hook(tmp_repo)
    assert is_pre_commit_hook_installed(tmp_repo) is True


def test_uninstall_removes_contx_block(tmp_repo: Path):
    install_pre_commit_hook(tmp_repo)
    uninstall_pre_commit_hook(tmp_repo)
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        assert HOOK_SENTINEL not in hook.read_text()


def test_uninstall_keeps_user_hook(tmp_repo: Path):
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho user-hook\n")
    hook.chmod(0o755)
    install_pre_commit_hook(tmp_repo)
    uninstall_pre_commit_hook(tmp_repo)
    assert hook.exists()
    content = hook.read_text()
    assert "echo user-hook" in content
    assert HOOK_SENTINEL not in content
