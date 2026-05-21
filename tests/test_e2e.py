"""End-to-end test: simulate a full session using the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from contx.cli import app

runner = CliRunner()


def test_full_lifecycle(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)

    # init
    r = runner.invoke(app, ["init"])
    assert r.exit_code == 0
    assert (tmp_repo / ".contx" / "config.json").is_file()

    # file-level entry
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py",
        "--event", "created", "--rationale", "Auth module — owns SSO + email login",
        "--tag", "module-purpose",
    ])
    assert r.exit_code == 0

    # symbol creation
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py::User.authenticate",
        "--event", "created",
        "--rationale", "Email-only because Legal said phone OTP fails GDPR",
        "--tag", "compliance", "--tag", "gdpr",
    ])
    assert r.exit_code == 0

    # symbol modified
    r = runner.invoke(app, [
        "append", "--ref", "src/auth/login.py::User.authenticate",
        "--event", "modified",
        "--rationale", "Added rate limit — May incident burst attack",
        "--tag", "incident", "--tag", "security",
    ])
    assert r.exit_code == 0

    # show file
    r = runner.invoke(app, ["show", "src/auth/login.py"])
    assert r.exit_code == 0
    assert "Auth module" in r.stdout
    assert "User.authenticate" in r.stdout

    # show symbol — latest rationale (modified) wins
    r = runner.invoke(app, ["show", "src/auth/login.py::User.authenticate"])
    assert r.exit_code == 0
    assert "May incident" in r.stdout
    assert "GDPR" not in r.stdout  # superseded by latest

    # log symbol — both entries in order
    r = runner.invoke(app, ["log", "src/auth/login.py::User.authenticate"])
    assert r.exit_code == 0
    assert r.stdout.index("GDPR") < r.stdout.index("May incident")
