"""Tests for the surviving CLI surface: version, serve, _precommit-check."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_version_prints_0_1_0():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_serve_help_lists_port_and_host():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()
    assert "host" in result.output.lower()
    assert "strict-port" in result.output.lower()


def test_serve_uninitialized_repo_errors(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 2
    assert "not initialized" in result.output.lower()


def test_precommit_check_uninitialized_repo_exits_zero(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0


def test_precommit_check_blocks_when_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from contx.config import default_config, save_config

    monkeypatch.chdir(tmp_repo)
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code != 0
    assert "src/foo.py" in result.output
    assert "context" in result.output.lower()


def test_precommit_check_passes_when_paired(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from contx.config import default_config, save_config

    monkeypatch.chdir(tmp_repo)
    save_config(tmp_repo, default_config())
    (tmp_repo / ".contx" / "src").mkdir(parents=True)
    (tmp_repo / ".contx" / "src" / "foo.py.jsonl").write_text('{"id":"x"}\n')
    subprocess.run(["git", "add", ".contx/src/foo.py.jsonl"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0
