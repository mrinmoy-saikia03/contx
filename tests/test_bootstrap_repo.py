import subprocess
from pathlib import Path

import pytest

from contx.bootstrap import bootstrap_repo
from contx.config import default_config, save_config
from contx.store import read_entries


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, rel_path: str, content: str, message: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


def test_bootstrap_writes_ast_entries(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "auth.py").write_text(
        '"""Auth module."""\n\ndef login(user):\n    """Log a user in."""\n    pass\n'
    )
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    entries = read_entries(tmp_repo, "src/auth.py")
    # one file-level + one symbol-level entry
    assert any(e.kind == "file" and "Auth module" in e.rationale for e in entries)
    assert any(e.kind == "symbol" and e.symbol == "login" for e in entries)
    # All bootstrap entries are tagged + agent="audit"
    for e in entries:
        assert "bootstrap" in e.tags
        assert e.agent == "audit"


def test_bootstrap_writes_git_history_entries(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/auth.py", "line1\nline2\nline3\nline4\nline5\nline6\n", "Add login flow because GDPR")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/auth.py")
    assert any("GDPR" in e.rationale for e in entries)
    for e in entries:
        assert "git-history" in e.tags or "bootstrap" in e.tags
        assert e.agent == "audit"


def test_bootstrap_skips_noisy_commits(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/a.py", "x\n" * 10, "WIP work in progress")  # noisy prefix
    _commit(tmp_repo, "src/a.py", "x\n" * 12, "real change because incident")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/a.py")
    rationales = " ".join(e.rationale for e in entries)
    assert "incident" in rationales
    assert "WIP" not in rationales


def test_bootstrap_first_commit_is_created_event(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _commit(tmp_repo, "src/a.py", "x\n" * 10, "Add a because we needed it")
    _commit(tmp_repo, "src/a.py", "x\n" * 15, "Modify a because incident")
    bootstrap_repo(tmp_repo, do_ast=False, do_git=True)
    entries = read_entries(tmp_repo, "src/a.py")
    events = [e.event for e in entries]
    assert events[0] == "created"
    assert "modified" in events


def test_bootstrap_refuses_if_already_bootstrapped(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_repo(tmp_repo, do_ast=True, do_git=False)


def test_bootstrap_force_writes_supersede_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "a.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False, force=True)
    entries = read_entries(tmp_repo, "src/a.py")
    # at least one entry mentions "re-bootstrap"
    assert any("re-bootstrap" in e.rationale for e in entries)


def test_bootstrap_respects_contxignore(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / ".contxignore").write_text("vendor/**\n")
    (tmp_repo / "vendor").mkdir()
    (tmp_repo / "vendor" / "skip.py").write_text('def x():\n    pass\n')
    bootstrap_repo(tmp_repo, do_ast=True, do_git=False)
    # No sidecar should have been created under vendor/
    assert not (tmp_repo / ".contx" / "vendor" / "skip.py.jsonl").exists()
