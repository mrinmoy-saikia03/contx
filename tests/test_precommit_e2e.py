"""End-to-end: real `git commit` with the contx hook installed."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


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


def _contx_bin() -> str:
    """Locate the `contx` CLI binary in the same venv pytest is running in."""
    venv_bin = Path(sys.executable).parent
    return str(venv_bin / "contx")


def test_real_commit_blocked_without_context(tmp_repo: Path):
    contx = _contx_bin()
    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")

    result = _git(tmp_repo, "commit", "-m", "no context", check=False)
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "drift" in combined or "context" in combined


def test_real_commit_succeeds_with_context(tmp_repo: Path):
    contx = _contx_bin()
    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(
        [
            contx, "append",
            "--ref", "src/foo.py",
            "--event", "created",
            "--rationale", "test scaffold",
        ],
        cwd=tmp_repo, check=True, capture_output=True,
    )
    _git(tmp_repo, "add", "src/foo.py", ".contx/")

    result = _git(tmp_repo, "commit", "-m", "with context", check=False)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_no_verify_bypasses_hook(tmp_repo: Path):
    contx = _contx_bin()
    subprocess.run([contx, "init"], cwd=tmp_repo, check=True, capture_output=True)

    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    _git(tmp_repo, "add", "src/foo.py")

    result = _git(tmp_repo, "commit", "-m", "bypass", "--no-verify", check=False)
    assert result.returncode == 0
