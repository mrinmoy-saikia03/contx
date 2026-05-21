import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_init_creates_contx_dir_and_config(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_repo / ".contx").is_dir()
    assert (tmp_repo / ".contx" / "config.json").is_file()


def test_init_idempotent(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "already initialized" in result.stdout.lower()


def test_init_outside_git_repo_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "not inside a git repo" in result.stdout.lower()


def test_append_writes_entry(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        [
            "append",
            "--ref", "src/auth/login.py::User.authenticate",
            "--event", "created",
            "--rationale", "GDPR — email-only login",
            "--tag", "compliance",
            "--tag", "gdpr",
        ],
    )
    assert result.exit_code == 0, result.stdout
    sidecar = tmp_repo / ".contx" / "src" / "auth" / "login.py.jsonl"
    assert sidecar.is_file()
    content = sidecar.read_text()
    assert "User.authenticate" in content
    assert "GDPR" in content
    assert "compliance" in content


def test_append_requires_init(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    result = runner.invoke(
        app,
        ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "x"],
    )
    assert result.exit_code != 0
    assert "not initialized" in result.stdout.lower()


def test_append_file_level_when_no_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "module purpose"],
    )
    assert result.exit_code == 0, result.stdout
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    content = sidecar.read_text()
    assert '"kind":"file"' in content or '"kind": "file"' in content


def test_show_file_level(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, [
        "append", "--ref", "src/foo.py",
        "--event", "created", "--rationale", "module purpose XYZ",
    ])
    result = runner.invoke(app, ["show", "src/foo.py"])
    assert result.exit_code == 0, result.stdout
    assert "module purpose XYZ" in result.stdout


def test_show_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, [
        "append", "--ref", "src/foo.py::do_thing",
        "--event", "created", "--rationale", "because reasons XYZ",
    ])
    result = runner.invoke(app, ["show", "src/foo.py::do_thing"])
    assert result.exit_code == 0, result.stdout
    assert "because reasons XYZ" in result.stdout


def test_show_missing_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["show", "src/foo.py::nope"])
    assert result.exit_code == 0
    assert "no context" in result.stdout.lower()


def test_log_shows_all_entries_for_file(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "AAA"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "created", "--rationale", "BBB"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "modified", "--rationale", "CCC"])
    result = runner.invoke(app, ["log", "src/foo.py"])
    assert result.exit_code == 0, result.stdout
    assert "AAA" in result.stdout
    assert "BBB" in result.stdout
    assert "CCC" in result.stdout


def test_log_filters_by_symbol(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["append", "--ref", "src/foo.py", "--event", "created", "--rationale", "FILE"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::bar", "--event", "created", "--rationale", "BAR-1"])
    runner.invoke(app, ["append", "--ref", "src/foo.py::baz", "--event", "created", "--rationale", "BAZ-1"])
    result = runner.invoke(app, ["log", "src/foo.py::bar"])
    assert result.exit_code == 0
    assert "BAR-1" in result.stdout
    assert "BAZ-1" not in result.stdout
    assert "FILE" not in result.stdout
