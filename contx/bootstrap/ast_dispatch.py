"""Dispatch source files to language-specific AST walkers."""

from __future__ import annotations

from pathlib import Path

from contx.bootstrap.ast_python import ParseResult, parse_python_source

# Map file extension → parser. None means "language is known but not yet implemented".
_PARSERS: dict[str, object] = {
    ".py": parse_python_source,
    # Stubs — fall through to None until implemented.
    ".ts": None,
    ".tsx": None,
    ".js": None,
    ".jsx": None,
    ".go": None,
    ".java": None,
    ".kt": None,
    ".rs": None,
    ".rb": None,
    ".php": None,
    ".swift": None,
}


def bootstrap_file(path: Path) -> ParseResult | None:
    """Parse a source file and return its BootstrapSymbol list, or None.

    Returns None when:
        - the file doesn't exist or is unreadable
        - the file extension is unknown
        - the language has no parser implemented yet
    """
    parser = _PARSERS.get(path.suffix)
    if parser is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return parser(text)  # type: ignore[no-any-return,operator]
