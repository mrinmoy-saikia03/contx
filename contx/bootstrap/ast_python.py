"""Walk a Python module's AST and emit BootstrapSymbol entries."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

SymbolKind = Literal["function", "method", "class"]


@dataclass(frozen=True)
class BootstrapSymbol:
    symbol: str          # dotted path, e.g. "Greeter.hello"
    kind: SymbolKind
    doc: str | None      # docstring (first line summary or full), or None


@dataclass(frozen=True)
class ParseResult:
    file_doc: str | None
    symbols: list[BootstrapSymbol] = field(default_factory=list)


def parse_python_source(source: str) -> ParseResult:
    """Parse Python source code and return its module doc + top-level symbols.

    Resilient: returns empty ParseResult on SyntaxError.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ParseResult(file_doc=None, symbols=[])

    file_doc = ast.get_docstring(tree)
    symbols: list[BootstrapSymbol] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(BootstrapSymbol(
                symbol=node.name,
                kind="function",
                doc=ast.get_docstring(node),
            ))
        elif isinstance(node, ast.ClassDef):
            symbols.append(BootstrapSymbol(
                symbol=node.name,
                kind="class",
                doc=ast.get_docstring(node),
            ))
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(BootstrapSymbol(
                        symbol=f"{node.name}.{inner.name}",
                        kind="method",
                        doc=ast.get_docstring(inner),
                    ))

    return ParseResult(file_doc=file_doc, symbols=symbols)
