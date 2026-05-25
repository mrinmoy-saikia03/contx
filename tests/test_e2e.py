"""End-to-end: MCP server + storage primitives lifecycle."""

import json
from datetime import datetime, timezone
from pathlib import Path

from contx.config import default_config, save_config
from contx.entry import Entry
from contx.store import append_entry, fold_entries, read_entries


def test_full_storage_lifecycle(tmp_repo: Path):
    # Init
    save_config(tmp_repo, default_config())

    # File-level entry
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HFILE0000000000000000000",
        kind="file", symbol=None, event="created",
        rationale="Auth module — owns SSO + email login",
        tags=["module-purpose"], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    # Symbol creation
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HSYM10000000000000000000",
        kind="symbol", symbol="User.authenticate", event="created",
        rationale="Email-only because Legal said phone OTP fails GDPR",
        tags=["compliance", "gdpr"], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    # Symbol modified
    append_entry(tmp_repo, "src/auth/login.py", Entry(
        id="01HSYM20000000000000000000",
        kind="symbol", symbol="User.authenticate", event="modified",
        rationale="Added rate limit — May incident burst attack",
        tags=["incident", "security"], author="t@x",
        timestamp=datetime(2026, 5, 22, tzinfo=timezone.utc),
        agent="claude-code", related=[],
    ))

    entries = read_entries(tmp_repo, "src/auth/login.py")
    assert len(entries) == 3

    folded = fold_entries(entries)
    assert "Auth module" in (folded.file_intent or "")
    # Latest symbol rationale wins
    assert "May incident" in folded.symbols["User.authenticate"]
