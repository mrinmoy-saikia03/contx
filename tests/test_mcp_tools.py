from datetime import datetime, timezone
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.mcp_tools import append as append_tool
from contx.mcp_tools import audit as audit_tool
from contx.mcp_tools import delete as delete_tool
from contx.mcp_tools import query as query_tool
from contx.mcp_tools import rename as rename_tool
from contx.store import append_entry, read_entries


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


def test_append_symbol_creates_sidecar(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = append_tool(
        tmp_repo,
        file="src/auth.py",
        event="created",
        rationale="email-only login because GDPR",
        symbol="login",
        tags=["compliance"],
        related=[],
        agent="claude-code",
    )
    assert result["sidecar"].endswith("src/auth.py.jsonl")
    assert result["entry"]["symbol"] == "login"
    assert result["entry"]["event"] == "created"
    assert "compliance" in result["entry"]["tags"]
    sidecar = tmp_repo / ".contx" / "src" / "auth.py.jsonl"
    assert sidecar.is_file()
    assert "GDPR" in sidecar.read_text()


def test_append_file_kind(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    result = append_tool(
        tmp_repo,
        file="src/auth.py",
        event="created",
        rationale="owns SSO + email login",
        symbol=None,
        tags=[],
        related=[],
        agent="claude-code",
    )
    assert result["entry"]["kind"] == "file"
    assert result["entry"]["symbol"] is None


def test_append_rejects_invalid_event(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    with pytest.raises(ValueError, match="event must be"):
        append_tool(
            tmp_repo,
            file="src/auth.py",
            event="banana",
            rationale="x",
            symbol=None,
            tags=[],
            related=[],
            agent="claude-code",
        )


def test_rename_within_same_file(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    result = rename_tool(
        tmp_repo,
        old_file="src/auth.py", old_symbol="login",
        new_file="src/auth.py", new_symbol="authenticate",
        rationale="renamed for clarity",
    )
    assert result["status"] == "ok"
    entries = read_entries(tmp_repo, "src/auth.py")
    events = [e.event for e in entries]
    assert "renamed_out" in events
    assert "renamed_in" in events


def test_move_across_files(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    rename_tool(
        tmp_repo,
        old_file="src/auth.py", old_symbol="login",
        new_file="src/sso/handlers.py", new_symbol="route_eu",
        rationale="moved to SSO subpackage",
    )
    old_entries = read_entries(tmp_repo, "src/auth.py")
    new_entries = read_entries(tmp_repo, "src/sso/handlers.py")
    assert any(e.event == "moved_out" for e in old_entries)
    moved_in = [e for e in new_entries if e.event == "moved_in"]
    assert moved_in
    assert "src/auth.py::login" in moved_in[0].related


def test_delete_symbol_appends_deleted_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "created", "v1"))
    delete_tool(tmp_repo, file="src/auth.py", symbol="login", rationale="superseded")
    entries = read_entries(tmp_repo, "src/auth.py")
    deleted = [e for e in entries if e.event == "deleted"]
    assert len(deleted) == 1
    assert deleted[0].rationale == "superseded"


def test_delete_file_appends_deleted_file_entry(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "created", "v1"))
    delete_tool(tmp_repo, file="src/auth.py", symbol=None, rationale="module retired")
    entries = read_entries(tmp_repo, "src/auth.py")
    deleted = [e for e in entries if e.event == "deleted"]
    assert len(deleted) == 1
    assert deleted[0].kind == "file"


def test_audit_finds_orphan_sidecar(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/deleted.py", _entry(None, "created", "x"))
    result = audit_tool(tmp_repo)
    orphan_files = [o["file"] for o in result["orphan_sidecars"]]
    assert "src/deleted.py" in orphan_files


def test_audit_finds_untracked_python_file(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "untracked.py").write_text("pass\n")
    result = audit_tool(tmp_repo)
    assert "src/untracked.py" in result["untracked_files"]


def test_audit_respects_ignore_patterns(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / "node_modules").mkdir()
    (tmp_repo / "node_modules" / "lib.js").write_text("x")
    result = audit_tool(tmp_repo)
    assert "node_modules/lib.js" not in result["untracked_files"]


def test_audit_skips_dotcontx_dir(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    (tmp_repo / ".contx" / "config.json").touch()
    result = audit_tool(tmp_repo)
    assert not any(p.startswith(".contx/") for p in result["untracked_files"])


def test_audit_respects_contxignore(tmp_repo: Path):
    from contx.ignore import CONTXIGNORE_FILENAME
    save_config(tmp_repo, default_config())
    (tmp_repo / CONTXIGNORE_FILENAME).write_text("legacy/**\n")
    (tmp_repo / "legacy").mkdir()
    (tmp_repo / "legacy" / "old.py").write_text("pass\n")
    result = audit_tool(tmp_repo)
    assert "legacy/old.py" not in result["untracked_files"]
