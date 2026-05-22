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


@app.tool()
def contx_search(query: str, limit: int | None = 50) -> list[dict]:
    """Search for context entries by substring (case-insensitive).

    Matches against entry rationale and tags. Returns up to `limit` results.

    Args:
        query: Free-text substring to search for.
        limit: Max results to return (default 50).

    Returns:
        A list of {file, entry} dicts in walk order.
    """
    repo = resolve_repo_root()
    return mcp_tools.search(repo, query, limit=limit)


@app.tool()
def contx_rename(
    old_file: str,
    new_file: str,
    old_symbol: str | None = None,
    new_symbol: str | None = None,
    rationale: str | None = None,
) -> dict:
    """Record a rename or move. Call this in the SAME turn as the rename Edit.

    Appends a renamed_out/moved_out entry on the old side and a
    renamed_in/moved_in entry on the new side, with backlinks. The full prior
    history stays in the old sidecar — readers follow `related` to trace.

    Args:
        old_file: Original file path.
        new_file: New file path. If same as old_file, treated as a rename.
        old_symbol: Optional original symbol path.
        new_symbol: Optional new symbol path.
        rationale: Optional explanation; a default is generated if omitted.
    """
    repo = resolve_repo_root()
    return mcp_tools.rename(
        repo,
        old_file=old_file,
        new_file=new_file,
        old_symbol=old_symbol,
        new_symbol=new_symbol,
        rationale=rationale,
    )


@app.tool()
def contx_delete(file: str, rationale: str, symbol: str | None = None) -> dict:
    """Record a code deletion. Pair with the actual Edit/Write that removes the code.

    History is preserved — folded views just stop including the deleted
    symbol. The append-only log still shows everything.

    Args:
        file: Path to the source file.
        rationale: Why the symbol/file was removed.
        symbol: Optional symbol path; omit for whole-file deletion.
    """
    repo = resolve_repo_root()
    return mcp_tools.delete(repo, file=file, rationale=rationale, symbol=symbol)


@app.tool()
def contx_audit() -> dict:
    """Find inconsistencies between the source tree and .contx/.

    Returns:
        orphan_sidecars: Sidecars whose source file no longer exists.
        untracked_files: Source files matching tracked languages but with no sidecar.
    """
    repo = resolve_repo_root()
    return mcp_tools.audit(repo)
