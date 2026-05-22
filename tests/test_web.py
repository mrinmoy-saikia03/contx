"""Tests for the read-only web UI (FastAPI + Jinja2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.store import append_entry
from contx.web.app import create_app


_counter = 0


def _entry(symbol: str | None, rationale: str) -> Entry:
    global _counter
    _counter += 1
    eid = f"01HWB{str(_counter).zfill(21)}"
    return Entry(
        id=eid,
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event="created",
        rationale=rationale,
        tags=[],
        author="test@example.com",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli",
        related=[],
    )


# ---------------------------------------------------------------------------
# Task 2: / (index), /file/<path>, /symbol/<ref>
# ---------------------------------------------------------------------------


def test_index_shows_files_with_entries(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "auth module"))
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/")
    assert r.status_code == 200
    assert "src/auth.py" in r.text


def test_file_view_shows_intent_and_symbols(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "auth module purpose"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "email-only"))
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/file/src/auth.py")
    assert r.status_code == 200
    assert "auth module purpose" in r.text
    assert "login" in r.text


def test_symbol_view_shows_intent_and_log(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "first reason"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "second reason"))
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/symbol/src/auth.py::login")
    assert r.status_code == 200
    # Latest in folded intent
    assert "second reason" in r.text
    # Both in log
    assert "first reason" in r.text


def test_file_view_404_when_missing(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/file/src/nope.py")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Task 3: /search, /timeline
# ---------------------------------------------------------------------------


def test_search_returns_hits(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/a.py", _entry(None, "GDPR compliance gate"))
    append_entry(tmp_repo, "src/b.py", _entry(None, "perf optimization"))
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/search?q=gdpr")
    assert r.status_code == 200
    assert "src/a.py" in r.text
    assert "src/b.py" not in r.text


def test_search_empty_query_returns_form(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/search")
    assert r.status_code == 200
    assert "search" in r.text.lower()


def test_timeline_shows_recent_entries(tmp_repo: Path) -> None:
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/a.py", _entry(None, "X-RATIONALE-X"))
    client = TestClient(create_app(repo_root=tmp_repo))
    r = client.get("/timeline")
    assert r.status_code == 200
    assert "X-RATIONALE-X" in r.text
