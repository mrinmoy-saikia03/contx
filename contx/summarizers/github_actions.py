"""Summarize GitHub Actions workflow YAML."""

from __future__ import annotations

import re

import yaml

from contx.summarizers import SummaryEntry

_SECRET_RE = re.compile(r"secrets\.([A-Z0-9_]+)")


def summarize_github_actions(yaml_text: str, file_path: str) -> list[SummaryEntry]:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []

    name = data.get("name") or file_path
    on = data.get("on") or data.get(True)  # PyYAML parses bare `on:` as True
    triggers: list[str] = []
    if isinstance(on, dict):
        triggers = list(on.keys())
    elif isinstance(on, list):
        triggers = list(on)
    elif isinstance(on, str):
        triggers = [on]

    jobs = data.get("jobs") or {}
    job_count = len(jobs) if isinstance(jobs, dict) else 0

    # Not a real workflow if neither triggers nor jobs are present
    if job_count == 0 and not triggers:
        return []

    secrets = sorted(set(_SECRET_RE.findall(yaml_text)))

    parts = [f"GitHub Actions: {name}"]
    if triggers:
        parts.append("triggers: " + ", ".join(triggers))
    parts.append(f"{job_count} jobs")
    if secrets:
        parts.append("secrets: " + ", ".join(secrets))

    return [SummaryEntry(
        symbol=None,
        rationale=" — ".join(parts),
        tags=["deploy", "auto-summary", "github-actions"],
    )]
