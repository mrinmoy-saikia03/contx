"""Per-format summarizers — produce contx entries from deployment manifests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryEntry:
    """One contx-entry-shaped summary produced by a summarizer."""

    symbol: str | None        # None for file-level
    rationale: str
    tags: list[str]


def _register_builtin_summarizers() -> None:
    pass  # filled in as summarizers are added (Tasks 5, 6)


_register_builtin_summarizers()
