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


from contx import mcp_tools


@app.tool()
def contx_query(file: str, symbol: str | None = None) -> dict:
    """Read the folded intent and full log for a file or symbol.

    Use this BEFORE editing a file to learn its existing context.

    Args:
        file: Path to the source file, relative to the repo root.
        symbol: Optional dotted symbol path within the file (e.g. "Class.method").
                When omitted, returns the file-level intent and lists all symbols.

    Returns:
        file_intent: The folded "current" file-level rationale, or None.
        symbols: Dict mapping symbol name to its current rationale.
        symbol_intent: Present only when symbol is provided.
        log: Raw entries (filtered by symbol if specified) in file order.
    """
    repo = resolve_repo_root()
    return mcp_tools.query(repo, file, symbol=symbol)


@app.tool()
def contx_append(
    file: str,
    event: str,
    rationale: str,
    symbol: str | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
) -> dict:
    """Append a context entry for a file or symbol.

    Call this whenever you create, modify, rename, or delete code — paired
    with the corresponding Edit/Write tool call. Never edit code without a
    matching contx_append call.

    Args:
        file: Path to the source file, relative to the repo root.
        event: One of: created, modified, renamed_in, renamed_out,
               moved_in, moved_out, deleted.
        rationale: Free-text explaining the WHY (never the WHAT — the code
                   itself shows what; the rationale captures decisions,
                   constraints, business reasons, incidents).
        symbol: Optional dotted symbol path (e.g. "Class.method"). Omit for
                file-level intent.
        tags: Optional list of tags (e.g. ["compliance", "gdpr"]).
        related: Optional list of related symbol refs.

    Returns:
        entry: The serialized entry just written.
        sidecar: Relative path to the sidecar file that was updated.
    """
    repo = resolve_repo_root()
    return mcp_tools.append(
        repo,
        file=file,
        event=event,
        rationale=rationale,
        symbol=symbol,
        tags=tags,
        related=related,
        agent="claude-code",
    )
