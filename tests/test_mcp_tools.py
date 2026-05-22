from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.mcp_tools import query as query_tool
from contx.store import append_entry


def _entry(symbol: str | None, event: str, rationale: str) -> Entry:
    return Entry(
        id=f"01H{(symbol or 'F')[:4]}0000000000000000000K"[:26].ljust(26, "0"),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event=event,
        rationale=rationale,
        tags=[],
        author="test@example.com",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code",
        related=[],
    )


def test_query_file_returns_folded_intent_and_log(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "email-only because GDPR"))
    result = query_tool(tmp_repo, "src/auth.py", symbol=None)
    assert result["file_intent"] == "auth module"
    assert "login" in result["symbols"]
    assert result["symbols"]["login"] == "email-only because GDPR"
    assert len(result["log"]) == 2


def test_query_symbol_returns_just_that_symbol(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "email-only"))
    result = query_tool(tmp_repo, "src/auth.py", symbol="login")
    assert result["symbol_intent"] == "email-only"
    assert all(e["symbol"] == "login" for e in result["log"])


def test_query_missing_file_returns_empty(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = query_tool(tmp_repo, "src/nope.py", symbol=None)
    assert result["file_intent"] is None
    assert result["symbols"] == {}
    assert result["log"] == []


def test_query_missing_symbol_returns_none(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "auth module"))
    result = query_tool(tmp_repo, "src/auth.py", symbol="nope")
    assert result["symbol_intent"] is None
