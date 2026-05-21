from datetime import datetime, timezone

from contx.entry import Entry


def test_entry_to_dict_roundtrip():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="symbol",
        symbol="User.authenticate",
        event="created",
        rationale="Email-only login because Legal said phone OTP doesn't meet GDPR",
        tags=["compliance", "gdpr"],
        author="mrinmoy.saikia@xeno.in",
        timestamp=datetime(2026, 5, 21, 14, 23, 11, tzinfo=timezone.utc),
        agent="claude-code",
        related=["src/auth/sso.py::route_eu"],
    )
    d = e.to_dict()
    e2 = Entry.from_dict(d)
    assert e2 == e


def test_entry_file_kind_has_no_symbol():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file",
        symbol=None,
        event="created",
        rationale="Auth module — owns login and session lifecycle",
        tags=[],
        author="me",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )
    assert e.to_dict()["symbol"] is None


def test_entry_to_jsonl_line():
    e = Entry(
        id="01HXYZ0000000000000000000K",
        kind="symbol",
        symbol="foo",
        event="created",
        rationale="bar",
        tags=[],
        author="me",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )
    line = e.to_jsonl_line()
    assert "\n" not in line
    assert '"id":"01HXYZ0000000000000000000K"' in line


def test_entry_from_jsonl_line():
    line = (
        '{"id":"01HXYZ0000000000000000000K","kind":"symbol","symbol":"foo",'
        '"event":"created","rationale":"bar","tags":[],"author":"me",'
        '"timestamp":"2026-05-21T00:00:00+00:00","agent":"claude-code","related":[]}'
    )
    e = Entry.from_jsonl_line(line)
    assert e.id == "01HXYZ0000000000000000000K"
    assert e.symbol == "foo"


def test_entry_rejects_invalid_kind():
    import pytest
    with pytest.raises(ValueError, match="kind must be"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="banana",
            symbol=None,
            event="created",
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )


def test_entry_rejects_invalid_event():
    import pytest
    with pytest.raises(ValueError, match="event must be"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="symbol",
            symbol="foo",
            event="exploded",
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )


def test_entry_symbol_required_when_kind_is_symbol():
    import pytest
    with pytest.raises(ValueError, match="symbol is required"):
        Entry(
            id="01HXYZ0000000000000000000K",
            kind="symbol",
            symbol=None,
            event="created",
            rationale="x",
            tags=[],
            author="me",
            timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
            agent="claude-code",
            related=[],
        )
