from pathlib import Path

import pytest

from contx.repo import find_repo_root, NotInRepoError, ensure_contx_dir, is_initialized


def test_find_repo_root_from_repo_root(tmp_repo: Path):
    assert find_repo_root(tmp_repo) == tmp_repo


def test_find_repo_root_from_subdir(tmp_repo: Path):
    sub = tmp_repo / "src" / "auth"
    sub.mkdir(parents=True)
    assert find_repo_root(sub) == tmp_repo


def test_find_repo_root_outside_repo(tmp_path: Path):
    with pytest.raises(NotInRepoError):
        find_repo_root(tmp_path)


def test_ensure_contx_dir_creates_dir(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    assert (tmp_repo / ".contx").is_dir()


def test_ensure_contx_dir_idempotent(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    ensure_contx_dir(tmp_repo)
    assert (tmp_repo / ".contx").is_dir()


def test_is_initialized_false_initially(tmp_repo: Path):
    assert is_initialized(tmp_repo) is False


def test_is_initialized_true_after_ensure(tmp_repo: Path):
    ensure_contx_dir(tmp_repo)
    (tmp_repo / ".contx" / "config.json").write_text("{}")
    assert is_initialized(tmp_repo) is True
