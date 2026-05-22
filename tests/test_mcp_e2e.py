"""End-to-end test: spin up the MCP server and call tools via FastMCP's in-process API."""

from pathlib import Path

import pytest

from contx.config import default_config, save_config


async def test_mcp_e2e_full_lifecycle(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Exercise the full MCP loop: verify tools registered + append + query work."""
    monkeypatch.setenv("CONTX_REPO_ROOT", str(tmp_repo))
    save_config(tmp_repo, default_config())

    from contx.mcp_server import app

    # Verify all 6 contx_* tools are registered
    tools = await app.list_tools()
    tool_names = {t.name for t in tools}
    expected = {"contx_query", "contx_append", "contx_search", "contx_rename", "contx_delete", "contx_audit"}
    assert expected.issubset(tool_names), f"missing tools: {expected - tool_names}"

    # Call contx_append via the MCP machinery
    append_result = await app.call_tool(
        "contx_append",
        {
            "file": "src/auth.py",
            "event": "created",
            "rationale": "GDPR — email only",
            "symbol": "login",
            "tags": ["compliance"],
        },
    )
    assert append_result, "contx_append returned no content"

    # Call contx_query via MCP
    query_result = await app.call_tool(
        "contx_query",
        {"file": "src/auth.py", "symbol": "login"},
    )
    assert query_result, "contx_query returned no content"

    # The sidecar must exist on disk
    assert (tmp_repo / ".contx" / "src" / "auth.py.jsonl").is_file()
