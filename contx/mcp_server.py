"""MCP server exposing contx tools to AI coding agents."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from contx.repo import NotInRepoError, find_repo_root

app: FastMCP = FastMCP("contx")


def resolve_repo_root() -> Path:
    """Resolve the contx repo root: CONTX_REPO_ROOT env var, else cwd.

    Called at the start of every tool. Raises NotInRepoError if not inside a git repo.
    """
    override = os.environ.get("CONTX_REPO_ROOT")
    start = Path(override) if override else Path.cwd()
    return find_repo_root(start)


def main() -> None:
    """Entry point — run the MCP server over stdio."""
    app.run()


if __name__ == "__main__":
    main()
