from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.entry import Entry
from contx.store import append_entry, read_entries


def _make_entry(symbol: str | None = "User.authenticate", event: str = "created", rationale: str = "why") -> Entry:
    return Entry(
        id=f"01H{symbol or 'F'}0000000000000000000K"[:26].ljust(26, "0"),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=[],
        author="test@example.com",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli",
        related=[],
    )


def test_append_creates_sidecar(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "src/auth/login.py", e)
    sidecar = tmp_repo / ".contx" / "src" / "auth" / "login.py.jsonl"
    assert sidecar.is_file()


def test_append_creates_parent_dirs(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "very/deeply/nested/file.py", e)
    sidecar = tmp_repo / ".contx" / "very" / "deeply" / "nested" / "file.py.jsonl"
    assert sidecar.is_file()


def test_append_writes_one_line(tmp_repo: Path):
    e = _make_entry()
    append_entry(tmp_repo, "src/foo.py", e)
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.read_text().count("\n") == 1


def test_append_two_entries_appends_not_overwrites(tmp_repo: Path):
    e1 = _make_entry(rationale="first")
    e2 = _make_entry(rationale="second")
    append_entry(tmp_repo, "src/foo.py", e1)
    append_entry(tmp_repo, "src/foo.py", e2)
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.read_text().count("\n") == 2


def test_read_entries_returns_in_file_order(tmp_repo: Path):
    e1 = _make_entry(rationale="first")
    e2 = _make_entry(rationale="second")
    append_entry(tmp_repo, "src/foo.py", e1)
    append_entry(tmp_repo, "src/foo.py", e2)
    entries = read_entries(tmp_repo, "src/foo.py")
    assert [e.rationale for e in entries] == ["first", "second"]


def test_read_entries_missing_sidecar_returns_empty(tmp_repo: Path):
    assert read_entries(tmp_repo, "src/nope.py") == []


from contx.store import fold_entries, FoldedIntent


def test_fold_empty_returns_empty_intent():
    folded = fold_entries([])
    assert folded.file_intent is None
    assert folded.symbols == {}


def test_fold_collects_file_level_intent():
    file_e = _make_entry(symbol=None, event="created", rationale="auth module")
    folded = fold_entries([file_e])
    assert folded.file_intent == "auth module"


def test_fold_latest_file_intent_wins():
    e1 = _make_entry(symbol=None, event="created", rationale="v1")
    e2 = _make_entry(symbol=None, event="modified", rationale="v2 — pivot to SSO")
    folded = fold_entries([e1, e2])
    assert folded.file_intent == "v2 — pivot to SSO"


def test_fold_collects_symbol_intent_keyed_by_symbol():
    a = _make_entry(symbol="foo", rationale="foo why")
    b = _make_entry(symbol="bar", rationale="bar why")
    folded = fold_entries([a, b])
    assert folded.symbols["foo"] == "foo why"
    assert folded.symbols["bar"] == "bar why"


def test_fold_latest_symbol_intent_wins():
    a = _make_entry(symbol="foo", event="created", rationale="initial")
    b = _make_entry(symbol="foo", event="modified", rationale="updated for incident X")
    folded = fold_entries([a, b])
    assert folded.symbols["foo"] == "updated for incident X"


def test_fold_skips_deleted_symbol():
    a = _make_entry(symbol="foo", event="created", rationale="initial")
    b = _make_entry(symbol="foo", event="deleted", rationale="removed — superseded by bar")
    folded = fold_entries([a, b])
    assert "foo" not in folded.symbols
