"""Registry mapping summarizer-name → summarizer function."""

from __future__ import annotations

from typing import Callable

from contx.summarizers import SummaryEntry

Summarizer = Callable[[str, str], list[SummaryEntry]]

_REGISTRY: dict[str, Summarizer] = {}


def register_summarizer(name: str, fn: Summarizer) -> None:
    _REGISTRY[name] = fn


def get_summarizer(name: str) -> Summarizer | None:
    return _REGISTRY.get(name)


def list_summarizers() -> list[str]:
    return sorted(_REGISTRY)
