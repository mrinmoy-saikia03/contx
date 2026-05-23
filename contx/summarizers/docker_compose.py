"""Summarize docker-compose YAML."""

from __future__ import annotations

import yaml

from contx.summarizers import SummaryEntry


def summarize_docker_compose(yaml_text: str, file_path: str) -> list[SummaryEntry]:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []

    services = data.get("services") or {}
    if not isinstance(services, dict) or not services:
        return []

    descs: list[str] = []
    deps: list[str] = []
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        image = svc.get("image", "")
        descs.append(f"{name}({image})" if image else name)
        dep = svc.get("depends_on")
        if isinstance(dep, list) and dep:
            deps.append(f"{name} depends_on {','.join(dep)}")
        elif isinstance(dep, dict) and dep:
            deps.append(f"{name} depends_on {','.join(dep.keys())}")

    parts = [f"docker-compose: {', '.join(descs)}"]
    if deps:
        parts.append(" / ".join(deps))

    return [SummaryEntry(
        symbol=None,
        rationale=" — ".join(parts),
        tags=["deploy", "auto-summary", "docker-compose"],
    )]
