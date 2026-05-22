from datetime import datetime, timezone
from pathlib import Path

from contx.entry import Entry
from contx.search import search_entries
from contx.store import append_entry


def _e(rationale: str, tags: list[str] | None = None) -> Entry:
    return Entry(
        id="01H" + rationale[:4].upper().ljust(23, "0"),
        kind="file",
        symbol=None,
        event="created",
        rationale=rationale,
        tags=tags or [],
        author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )


def test_search_finds_match_in_rationale(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("GDPR — email only"))
    append_entry(tmp_repo, "src/b.py", _e("rate limiting under load"))
    hits = search_entries(tmp_repo, "GDPR")
    assert len(hits) == 1
    assert hits[0]["file"] == "src/a.py"
    assert "GDPR" in hits[0]["entry"]["rationale"]


def test_search_is_case_insensitive(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("Compliance — GDPR"))
    hits = search_entries(tmp_repo, "compliance")
    assert len(hits) == 1


def test_search_matches_tags(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("x", tags=["gdpr"]))
    append_entry(tmp_repo, "src/b.py", _e("y", tags=["perf"]))
    hits = search_entries(tmp_repo, "gdpr")
    assert len(hits) == 1
    assert hits[0]["file"] == "src/a.py"


def test_search_returns_empty_for_no_matches(tmp_repo: Path):
    append_entry(tmp_repo, "src/a.py", _e("x"))
    assert search_entries(tmp_repo, "nope") == []


def test_search_respects_limit(tmp_repo: Path):
    for i in range(5):
        append_entry(tmp_repo, f"src/f{i}.py", _e("GDPR rule"))
    hits = search_entries(tmp_repo, "GDPR", limit=2)
    assert len(hits) == 2


def test_search_missing_contx_dir_returns_empty(tmp_repo: Path):
    assert search_entries(tmp_repo, "anything") == []
