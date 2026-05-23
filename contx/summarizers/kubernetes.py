"""Summarize Kubernetes manifests into contx SummaryEntry list."""

from __future__ import annotations

import yaml

from contx.summarizers import SummaryEntry


def _summarize_one(doc: dict) -> str | None:
    if not isinstance(doc, dict):
        return None
    kind = doc.get("kind")
    meta = doc.get("metadata") or {}
    name = meta.get("name", "<unnamed>")
    namespace = meta.get("namespace", "default")
    spec = doc.get("spec") or {}

    parts = [f"k8s {kind}: {name} (ns={namespace})"]

    if kind == "Deployment":
        replicas = spec.get("replicas", 1)
        parts.append(f"{replicas} replicas")
        containers = (spec.get("template") or {}).get("spec", {}).get("containers", []) or []
        images = [c.get("image") for c in containers if isinstance(c, dict) and c.get("image")]
        if images:
            parts.append("images: " + ", ".join(images))
    elif kind == "Service":
        ports = spec.get("ports") or []
        port_descs = []
        for p in ports:
            if isinstance(p, dict):
                port_descs.append(f"{p.get('port', '?')}→{p.get('targetPort', '?')}")
        if port_descs:
            parts.append("ports: " + ", ".join(port_descs))
        selector = spec.get("selector") or {}
        if selector:
            parts.append("selector: " + ",".join(f"{k}={v}" for k, v in selector.items()))
    elif kind == "Ingress":
        rules = spec.get("rules") or []
        hosts = [r.get("host") for r in rules if isinstance(r, dict) and r.get("host")]
        if hosts:
            parts.append("hosts: " + ", ".join(hosts))

    return " — ".join(parts)


def summarize_kubernetes(yaml_text: str, file_path: str) -> list[SummaryEntry]:
    """Parse a k8s YAML (possibly multi-document) and return file-level summaries."""
    try:
        docs = list(yaml.safe_load_all(yaml_text))
    except yaml.YAMLError:
        return []
    entries: list[SummaryEntry] = []
    for doc in docs:
        rationale = _summarize_one(doc)
        if rationale:
            entries.append(SummaryEntry(
                symbol=None,
                rationale=rationale,
                tags=["deploy", "auto-summary", "kubernetes"],
            ))
    return entries
