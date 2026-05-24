import subprocess
import sys
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
    assert "not inside a git repo" in result.output.lower()


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
    assert "not initialized" in result.output.lower()


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


def test_append_rejects_invalid_event(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, [
        "append", "--ref", "src/foo.py",
        "--event", "explodified",
        "--rationale", "x",
    ])
    assert result.exit_code == 2
    assert "event must be" in result.output.lower()


def test_show_rejects_bad_ref(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["show", "a::b::c"])
    assert result.exit_code == 2
    assert "only one" in result.output.lower()


def test_precommit_check_passes_when_no_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / ".contx" / "src").mkdir(parents=True, exist_ok=True)
    (tmp_repo / ".contx" / "src" / "foo.py.jsonl").write_text('{"id":"x"}\n')
    subprocess.run(["git", "add", ".contx/src/foo.py.jsonl"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0


def test_precommit_check_blocks_when_drift(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code != 0
    assert "src/foo.py" in result.output
    assert "context" in result.output.lower()


def test_precommit_check_soft_warns_when_disabled(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    import json
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    cfg_path = tmp_repo / ".contx" / "config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["require_context_on_commit"] = False
    cfg_path.write_text(json.dumps(cfg))
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0
    assert "warning" in result.output.lower()


def test_precommit_check_passes_on_uninitialized(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    # NO contx init
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)
    result = runner.invoke(app, ["_precommit-check"])
    assert result.exit_code == 0


def test_init_installs_hook_by_default(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()


def test_init_skips_hook_with_flag(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-hook"])
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert not hook.is_file()


def test_install_hook_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-hook"])
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()


def test_uninstall_hook_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["uninstall-hook"])
    assert result.exit_code == 0
    hook = tmp_repo / ".git" / "hooks" / "pre-commit"
    assert not hook.is_file()


def test_draft_appends_entries_for_drifted_files(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)

    # Editor script: replaces "rationale: " with "rationale: filled-by-test "
    helper = tmp_path / "fill.py"
    helper.write_text(
        'import sys\n'
        'p = sys.argv[1]\n'
        'with open(p) as f: t = f.read()\n'
        't = t.replace("rationale: ", "rationale: filled-by-test ")\n'
        'with open(p, "w") as f: f.write(t)\n'
    )
    editor = tmp_path / "fake_editor.sh"
    editor.write_text(f"#!/bin/sh\nexec {sys.executable} {helper} \"$1\"\n")
    editor.chmod(0o755)
    monkeypatch.setenv("CONTX_EDITOR", str(editor))

    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0, result.output

    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.is_file()
    assert "filled-by-test" in sidecar.read_text()


def test_draft_no_drift_is_noop(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0
    assert "no drift" in result.output.lower() or "nothing to draft" in result.output.lower()


def test_draft_skips_blank_rationale(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)

    editor = tmp_path / "noop.sh"
    editor.write_text('#!/bin/sh\nexit 0\n')
    editor.chmod(0o755)
    monkeypatch.setenv("CONTX_EDITOR", str(editor))

    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert not sidecar.is_file()


def test_install_skill_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setenv("CONTX_CLAUDE_HOME", str(tmp_path / "fake_claude"))
    result = runner.invoke(app, ["install-skill"])
    assert result.exit_code == 0, result.output
    dest = tmp_path / "fake_claude" / "skills" / "contx" / "SKILL.md"
    assert dest.is_file()
    assert "contx — git for context" in dest.read_text()


def test_uninstall_skill_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setenv("CONTX_CLAUDE_HOME", str(tmp_path / "fake_claude"))
    runner.invoke(app, ["install-skill"])
    result = runner.invoke(app, ["uninstall-skill"])
    assert result.exit_code == 0
    assert not (tmp_path / "fake_claude" / "skills" / "contx").exists()


def test_serve_command_imports_cleanly(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()


def test_init_creates_contxignore(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    ignore_file = tmp_repo / ".contxignore"
    assert ignore_file.is_file()
    content = ignore_file.read_text()
    assert "node_modules" in content


def test_init_preserves_existing_contxignore(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / ".contxignore").write_text("# user's custom file\nuser/**\n")
    runner.invoke(app, ["init"])
    content = (tmp_repo / ".contxignore").read_text()
    assert "user/**" in content  # untouched


def test_init_with_bootstrap_default_runs_ast(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi():\n    """h"""\n    pass\n')
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert sidecar.is_file()
    assert "mod" in sidecar.read_text()


def test_init_no_bootstrap_skips_bootstrap(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi(): pass\n')
    result = runner.invoke(app, ["init", "--no-bootstrap"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert not sidecar.exists()


def test_bootstrap_command_on_already_initialized_repo(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('"""mod"""\ndef hi(): pass\n')
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0, result.output
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert sidecar.is_file()


def test_bootstrap_refuses_second_run_without_force(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    runner.invoke(app, ["bootstrap"])
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    assert "already bootstrapped" in result.output.lower()


def test_bootstrap_force_succeeds(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    runner.invoke(app, ["bootstrap"])
    result = runner.invoke(app, ["bootstrap", "--force"])
    assert result.exit_code == 0, result.output


def test_bootstrap_dry_run_writes_nothing(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def hi(): pass\n')
    result = runner.invoke(app, ["bootstrap", "--dry-run"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "a.py.jsonl"
    assert not sidecar.exists()


def test_diagram_files_writes_drawio(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone
    from contx.entry import Entry
    from contx.store import append_entry

    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    entry = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file", symbol=None, event="created", rationale="auth module",
        tags=[], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli", related=[],
    )
    append_entry(tmp_repo, "src/auth.py", entry)
    result = runner.invoke(app, ["diagram"])
    assert result.exit_code == 0, result.output
    out_path = tmp_repo / ".contx" / "diagrams" / "files.drawio"
    assert out_path.is_file()
    content = out_path.read_text()
    assert "<mxfile" in content
    assert "src/auth.py" in content


def test_diagram_with_custom_out(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from datetime import datetime, timezone
    from contx.entry import Entry
    from contx.store import append_entry

    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    entry = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file", symbol=None, event="created", rationale="x",
        tags=[], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli", related=[],
    )
    append_entry(tmp_repo, "src/a.py", entry)
    out = tmp_path / "custom.drawio"
    result = runner.invoke(app, ["diagram", "--out", str(out)])
    assert result.exit_code == 0
    assert out.is_file()


def test_diagram_unsupported_type_errors(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    result = runner.invoke(app, ["diagram", "--type", "symbols"])
    assert result.exit_code != 0
    assert "not implemented" in result.output.lower() or "not yet" in result.output.lower()


def test_ignore_appends_pattern(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    result = runner.invoke(app, ["ignore", "vendor/**"])
    assert result.exit_code == 0
    content = (tmp_repo / ".contxignore").read_text()
    assert "vendor/**" in content


def test_ignore_does_not_duplicate(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    runner.invoke(app, ["ignore", "vendor/**"])
    runner.invoke(app, ["ignore", "vendor/**"])
    content = (tmp_repo / ".contxignore").read_text()
    assert content.count("vendor/**") == 1


def test_ignore_creates_contxignore_if_missing(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    (tmp_repo / ".contxignore").unlink()
    result = runner.invoke(app, ["ignore", "tmp/**"])
    assert result.exit_code == 0
    assert (tmp_repo / ".contxignore").is_file()
    assert "tmp/**" in (tmp_repo / ".contxignore").read_text()


def test_bootstrap_deploy_writes_summaries(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import json
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    # Add a k8s tracked-path
    cfg_path = tmp_repo / ".contx" / "config.json"
    raw = json.loads(cfg_path.read_text())
    raw["tracked_paths"].append({"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"})
    cfg_path.write_text(json.dumps(raw))
    (tmp_repo / "k8s").mkdir()
    (tmp_repo / "k8s" / "auth.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: auth, namespace: prod}\nspec: {replicas: 2}\n"
    )
    result = runner.invoke(app, ["bootstrap-deploy"])
    assert result.exit_code == 0, result.output
    sidecar = tmp_repo / ".contx" / "k8s" / "auth.yaml.jsonl"
    assert sidecar.is_file()
    content = sidecar.read_text()
    assert "Deployment" in content
    assert "auto-summary" in content
