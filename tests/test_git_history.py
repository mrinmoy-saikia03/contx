import subprocess
from pathlib import Path

from contx.bootstrap.git_history import (
    GitCommit,
    iter_commits_for_file,
    iter_commits_with_files,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, rel_path: str, content: str, message: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)
    _git(repo, "commit", "-m", message)


def test_iter_commits_with_files_returns_commits_in_order(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "first commit")
    _commit(tmp_repo, "src/a.py", "x=2\n", "second commit")
    commits = list(iter_commits_with_files(tmp_repo))
    assert len(commits) == 2
    assert commits[0].subject == "first commit"
    assert commits[1].subject == "second commit"
    assert "src/a.py" in commits[0].files
    assert "src/a.py" in commits[1].files


def test_iter_commits_includes_author_and_timestamp(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "first commit")
    commits = list(iter_commits_with_files(tmp_repo))
    assert commits[0].author == "test@example.com"
    assert commits[0].timestamp.endswith("+00:00") or "T" in commits[0].timestamp


def test_iter_commits_respects_max_commits(tmp_repo: Path):
    for i in range(5):
        _commit(tmp_repo, f"src/a{i}.py", "x", f"commit {i}")
    commits = list(iter_commits_with_files(tmp_repo, max_commits=3))
    assert len(commits) == 3


def test_iter_commits_diff_lines_per_file(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "line1\nline2\nline3\n", "add a")
    commits = list(iter_commits_with_files(tmp_repo))
    assert commits[0].diff_lines_by_file.get("src/a.py", 0) >= 3


def test_iter_commits_for_file_filters(tmp_repo: Path):
    _commit(tmp_repo, "src/a.py", "x=1\n", "touched a")
    _commit(tmp_repo, "src/b.py", "y=1\n", "touched b")
    a_commits = list(iter_commits_for_file(tmp_repo, "src/a.py"))
    assert len(a_commits) == 1
    assert a_commits[0].subject == "touched a"


def test_iter_commits_empty_repo(tmp_repo: Path):
    assert list(iter_commits_with_files(tmp_repo)) == []


def test_iter_commits_handles_merge_commit(tmp_repo: Path):
    # Just ensure we don't crash on a merge commit with no diff.
    _commit(tmp_repo, "src/a.py", "x=1\n", "first")
    _git(tmp_repo, "checkout", "-b", "feature")
    _commit(tmp_repo, "src/b.py", "y=1\n", "on feature")
    _git(tmp_repo, "checkout", "master")
    # Try to merge; some git defaults may use 'main' — handle both.
    try:
        _git(tmp_repo, "merge", "feature", "--no-ff", "-m", "merge feature")
    except subprocess.CalledProcessError:
        _git(tmp_repo, "branch", "-m", "master", "main")
        _git(tmp_repo, "merge", "feature", "--no-ff", "-m", "merge feature")
    commits = list(iter_commits_with_files(tmp_repo))
    # At least the 3 commits exist; the merge may or may not have files.
    assert len(commits) >= 3
