from pathlib import Path

from contx.skill_install import (
    install_skill,
    is_skill_installed,
    uninstall_skill,
)


def test_install_copies_skill_md(tmp_path: Path):
    src_repo = tmp_path / "contx_repo"
    (src_repo / "skills" / "contx").mkdir(parents=True)
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("# fake skill\n")

    claude_home = tmp_path / "fake_claude"
    install_skill(src_repo=src_repo, claude_home=claude_home)

    dest = claude_home / "skills" / "contx" / "SKILL.md"
    assert dest.is_file()
    assert "# fake skill" in dest.read_text()


def test_install_is_idempotent(tmp_path: Path):
    src_repo = tmp_path / "contx_repo"
    (src_repo / "skills" / "contx").mkdir(parents=True)
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("v1\n")
    claude_home = tmp_path / "fake_claude"
    install_skill(src_repo=src_repo, claude_home=claude_home)
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("v2\n")
    install_skill(src_repo=src_repo, claude_home=claude_home)
    dest = claude_home / "skills" / "contx" / "SKILL.md"
    assert dest.read_text() == "v2\n"


def test_is_skill_installed_reports_correctly(tmp_path: Path):
    claude_home = tmp_path / "fake_claude"
    assert is_skill_installed(claude_home=claude_home) is False
    (claude_home / "skills" / "contx").mkdir(parents=True)
    (claude_home / "skills" / "contx" / "SKILL.md").write_text("x")
    assert is_skill_installed(claude_home=claude_home) is True


def test_uninstall_removes_skill_dir(tmp_path: Path):
    claude_home = tmp_path / "fake_claude"
    (claude_home / "skills" / "contx").mkdir(parents=True)
    (claude_home / "skills" / "contx" / "SKILL.md").write_text("x")
    uninstall_skill(claude_home=claude_home)
    assert not (claude_home / "skills" / "contx").exists()


def test_install_missing_source_raises(tmp_path: Path):
    import pytest
    src_repo = tmp_path / "nope"
    claude_home = tmp_path / "fake_claude"
    with pytest.raises(FileNotFoundError):
        install_skill(src_repo=src_repo, claude_home=claude_home)
