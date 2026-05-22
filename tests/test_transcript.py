import json
import os
import time
from pathlib import Path

from contx.transcript import (
    extract_rationales_for_files,
    find_recent_transcript,
    sanitize_cwd_for_project_dir,
)


def test_sanitize_cwd_replaces_slashes():
    assert sanitize_cwd_for_project_dir("/Users/me/code/repo") == "-Users-me-code-repo"


def test_find_recent_transcript_returns_none_when_dir_missing(tmp_path: Path):
    assert find_recent_transcript(tmp_path, claude_home=tmp_path / "nope") is None


def test_find_recent_transcript_picks_most_recent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    claude_home = tmp_path / "claude"
    project_dir = claude_home / "projects" / sanitize_cwd_for_project_dir(str(repo))
    project_dir.mkdir(parents=True)
    older = project_dir / "old.jsonl"
    newer = project_dir / "new.jsonl"
    older.write_text("{}\n")
    newer.write_text("{}\n")
    os.utime(older, (time.time() - 1000, time.time() - 1000))
    found = find_recent_transcript(repo, claude_home=claude_home)
    assert found == newer


def test_extract_rationales_finds_file_mentions(tmp_path: Path):
    transcript = tmp_path / "session.jsonl"
    lines = [
        {"type": "user", "message": {"content": "let's change src/foo.py to use linear retry because Auth0 rate-limited us"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/abs/repo/src/foo.py"}}]}},
    ]
    transcript.write_text("\n".join(json.dumps(x) for x in lines))
    rationales = extract_rationales_for_files(transcript, ["src/foo.py"])
    assert "src/foo.py" in rationales
    assert "linear retry" in rationales["src/foo.py"].lower()


def test_extract_rationales_returns_empty_for_unmatched(tmp_path: Path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {"content": "unrelated"}}) + "\n")
    rationales = extract_rationales_for_files(transcript, ["src/foo.py"])
    assert rationales == {}
