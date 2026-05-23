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
    from contx.summarizers.docker_compose import summarize_docker_compose
    from contx.summarizers.github_actions import summarize_github_actions
    from contx.summarizers.kubernetes import summarize_kubernetes
    from contx.summarizers.registry import register_summarizer
    register_summarizer("kubernetes", summarize_kubernetes)
    register_summarizer("github_actions", summarize_github_actions)
    register_summarizer("docker_compose", summarize_docker_compose)


_register_builtin_summarizers()
