"""End-to-end: real `git commit` with the contx hook installed."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.hooks import install_pre_commit_hook
from contx.store import append_entry


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    venv_bin = str(Path(sys.executable).parent)
    env = {**os.environ, "PATH": venv_bin + os.pathsep + os.environ.get("PATH", "")}
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def _init_repo(repo: Path) -> None:
    """Initialize contx (config + hook) using the Python API."""
    save_config(repo, default_config())
    install_pre_commit_hook(repo)


def _append(repo: Path, file_path: str) -> None:
    """Append a minimal entry for the given file."""
    append_entry(repo, file_path, Entry(
        id="01HTEST0000000000000000000",
        kind="file", symbol=None, event="created",
        rationale="test scaffold",
        tags=[], author="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))


def test_real_commit_blocked_without_context(tmp_repo: Path):
    _init_repo(tmp_repo)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")

    result = _git(tmp_repo, "commit", "-m", "no context", check=False)
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "drift" in combined or "context" in combined


def test_real_commit_succeeds_with_context(tmp_repo: Path):
    _init_repo(tmp_repo)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _append(tmp_repo, "src/foo.py")
    _git(tmp_repo, "add", "src/foo.py", ".contx/")

    result = _git(tmp_repo, "commit", "-m", "with context", check=False)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_no_verify_bypasses_hook(tmp_repo: Path):
    _init_repo(tmp_repo)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")

    result = _git(tmp_repo, "commit", "-m", "bypass", "--no-verify", check=False)
    assert result.returncode == 0
