# contx — Plan B3: Deployment-manifest awareness

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Make deployment manifests (k8s, GitHub Actions, docker-compose) first-class contx citizens: tracked by the hook for drift, and auto-summarized at bootstrap time so new devs can read intent without reading raw YAML.

**Architecture:** Two changes. (1) `Config` grows a `tracked_paths` field — a list of `{glob, kind, summarizer}` records. `cfg.languages` projects into it for backward compat. Staging + audit use the merged effective tracked-paths set. (2) A new `contx/summarizers/` package with per-format functions registered by name. A new `contx bootstrap-deploy` command runs every summarizer over its matching files.

**Tech Stack:** Python 3.11+, `pyyaml` (new dep), existing storage layer.

**Companion spec:** `docs/specs/2026-05-23-contx-bootstrap-deploy-diagrams-design.md` §2.

---

## Task 1: Add pyyaml dep + Config.tracked_paths (TDD)

**Files:**
- Modify: `pyproject.toml`
- Modify: `contx/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add pyyaml**

In `pyproject.toml` under `[project] dependencies`, add `"pyyaml>=6.0"`. Then:

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pip install -e .[dev]
```

- [ ] **Step 2: Tests** — append to `tests/test_config.py`:

```python
def test_default_config_has_tracked_paths_with_kind_source(tmp_repo: Path):
    cfg = default_config()
    # tracked_paths is derived from languages on first read
    assert any(tp["kind"] == "source" for tp in cfg.tracked_paths)


def test_config_serializes_tracked_paths(tmp_repo: Path):
    cfg = Config(
        granularity="both",
        languages=["py"],
        ignore=[],
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
        require_context_on_commit=True,
        tracked_paths=[
            {"glob": "**/*.py", "kind": "source", "summarizer": None},
            {"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"},
        ],
    )
    save_config(tmp_repo, cfg)
    loaded = load_config(tmp_repo)
    assert {tp["kind"] for tp in loaded.tracked_paths} == {"source", "deploy"}


def test_legacy_config_without_tracked_paths_projects_languages(tmp_repo: Path):
    import json
    save_config(tmp_repo, default_config())
    raw = json.loads((tmp_repo / ".contx" / "config.json").read_text())
    raw.pop("tracked_paths", None)
    (tmp_repo / ".contx" / "config.json").write_text(json.dumps(raw))
    loaded = load_config(tmp_repo)
    assert any(tp["kind"] == "source" and tp["glob"].endswith("py") for tp in loaded.tracked_paths)
```

- [ ] **Step 3: Modify `contx/config.py`**

Add `tracked_paths: list[dict] = field(default_factory=list)` to `Config`. In `default_config()`, project the default languages list into tracked_paths entries. In `load_config`, if the JSON lacks `tracked_paths`, derive it from `languages`. Concretely:

```python
@dataclass(frozen=True)
class Config:
    granularity: Granularity
    languages: list[str]
    ignore: list[str]
    require_rationale_on_create: bool
    extract_rationale_on_modify: bool
    require_context_on_commit: bool = True
    tracked_paths: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.granularity not in _VALID_GRANULARITY:
            raise ValueError(
                f"granularity must be one of {_VALID_GRANULARITY}, got {self.granularity!r}"
            )


def _languages_to_tracked_paths(languages: list[str]) -> list[dict]:
    return [{"glob": f"**/*.{ext}", "kind": "source", "summarizer": None} for ext in languages]


def default_config() -> Config:
    langs = list(DEFAULT_LANGUAGES)
    return Config(
        granularity="both",
        languages=langs,
        ignore=list(DEFAULT_IGNORE),
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
        require_context_on_commit=True,
        tracked_paths=_languages_to_tracked_paths(langs),
    )
```

Update `load_config`:

```python
    tracked_paths = data.get("tracked_paths")
    if not tracked_paths:
        tracked_paths = _languages_to_tracked_paths(list(data["languages"]))
    return Config(
        granularity=data["granularity"],
        languages=list(data["languages"]),
        ignore=list(data["ignore"]),
        require_rationale_on_create=bool(data["require_rationale_on_create"]),
        extract_rationale_on_modify=bool(data["extract_rationale_on_modify"]),
        require_context_on_commit=bool(data.get("require_context_on_commit", True)),
        tracked_paths=list(tracked_paths),
    )
```

- [ ] **Step 4: Verify tests pass + full suite still green**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add pyproject.toml contx/config.py tests/test_config.py && git commit -m "feat(config): add tracked_paths schema with legacy-languages projection

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Wire tracked_paths into staging drift detection (TDD)

**Files:**
- Modify: `contx/staging.py`
- Modify: `tests/test_staging.py`

- [ ] **Step 1: Test** — append to `tests/test_staging.py`:

```python
def test_compute_drift_flags_deploy_yaml(tmp_repo: Path):
    import json
    save_config(tmp_repo, default_config())
    # Add a deploy tracked-path to config
    cfg_path = tmp_repo / ".contx" / "config.json"
    raw = json.loads(cfg_path.read_text())
    raw["tracked_paths"].append({"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"})
    cfg_path.write_text(json.dumps(raw))
    _write_and_stage(tmp_repo, "k8s/auth.yaml", "apiVersion: v1\n")
    drift = compute_drift(tmp_repo)
    assert "k8s/auth.yaml" in drift.missing


def test_compute_drift_ignores_unmatched_path(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "something.xyz", "blob")
    drift = compute_drift(tmp_repo)
    assert "something.xyz" not in drift.missing
```

- [ ] **Step 2: Update `staging.compute_drift`** to use tracked_paths instead of extensions. Replace:

```python
    extensions = {f".{ext}" for ext in cfg.languages}
    ...
    if ext not in extensions:
        continue
```

with:

```python
    tracked_globs = [tp["glob"] for tp in cfg.tracked_paths]
    ...
    if not _matches_any(p, tracked_globs):
        continue
```

The existing `_matches_any` import (from `contx.ignore`) handles the `**` glob correctly.

- [ ] **Step 3: Verify all staging tests pass**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/staging.py tests/test_staging.py && git commit -m "feat(staging): use tracked_paths globs for drift detection

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Wire tracked_paths into audit (TDD)

**Files:**
- Modify: `contx/mcp_tools.py`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Test** — append to `tests/test_mcp_tools.py`:

```python
def test_audit_finds_untracked_deploy_yaml(tmp_repo: Path):
    import json
    save_config(tmp_repo, default_config())
    cfg_path = tmp_repo / ".contx" / "config.json"
    raw = json.loads(cfg_path.read_text())
    raw["tracked_paths"].append({"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"})
    cfg_path.write_text(json.dumps(raw))
    (tmp_repo / "k8s").mkdir()
    (tmp_repo / "k8s" / "service.yaml").write_text("apiVersion: v1\n")
    result = audit_tool(tmp_repo)
    assert "k8s/service.yaml" in result["untracked_files"]
```

- [ ] **Step 2: Update `audit` in `contx/mcp_tools.py`**

Replace the extension-based filter with tracked_paths globs. The current code is:

```python
    extensions = {f".{ext}" for ext in cfg.languages}
    ...
    if path.suffix not in extensions:
        continue
```

Change to:

```python
    tracked_globs = [tp["glob"] for tp in cfg.tracked_paths]
    ...
    if not matches_any_pattern(rel, tracked_globs):
        continue
```

- [ ] **Step 3: Verify tests pass**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/mcp_tools.py tests/test_mcp_tools.py && git commit -m "feat(mcp): audit uses tracked_paths globs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: summarizers package + registry (TDD)

**Files:**
- Create: `contx/summarizers/__init__.py`
- Create: `contx/summarizers/registry.py`
- Create: `tests/test_summarizers_registry.py`

- [ ] **Step 1: Tests**

`~/Desktop/xeno/contx/tests/test_summarizers_registry.py`:

```python
import pytest

from contx.summarizers import SummaryEntry
from contx.summarizers.registry import (
    get_summarizer,
    list_summarizers,
    register_summarizer,
)


def test_register_and_get():
    def fake(content: str, file_path: str) -> list[SummaryEntry]:
        return [SummaryEntry(symbol=None, rationale="x", tags=["test"])]

    register_summarizer("fake", fake)
    s = get_summarizer("fake")
    out = s("hi", "k8s/a.yaml")
    assert len(out) == 1
    assert out[0].rationale == "x"


def test_get_unknown_returns_none():
    assert get_summarizer("does-not-exist") is None


def test_list_summarizers_includes_registered():
    register_summarizer("listed", lambda c, f: [])
    assert "listed" in list_summarizers()


def test_summary_entry_immutable():
    e = SummaryEntry(symbol="foo", rationale="r", tags=["t"])
    import dataclasses
    assert dataclasses.is_dataclass(e) and e.__dataclass_params__.frozen
```

- [ ] **Step 2: Implement**

`~/Desktop/xeno/contx/contx/summarizers/__init__.py`:

```python
"""Per-format summarizers — produce contx entries from deployment manifests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryEntry:
    """One contx-entry-shaped summary produced by a summarizer."""
    symbol: str | None        # None for file-level
    rationale: str
    tags: list[str]
```

`~/Desktop/xeno/contx/contx/summarizers/registry.py`:

```python
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
```

- [ ] **Step 3: Verify tests pass**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/summarizers/ tests/test_summarizers_registry.py && git commit -m "feat(summarizers): add registry + SummaryEntry shape

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: kubernetes summarizer (TDD)

**Files:**
- Create: `contx/summarizers/kubernetes.py`
- Create: `tests/test_summarizer_kubernetes.py`

- [ ] **Step 1: Tests**

```python
from contx.summarizers.kubernetes import summarize_kubernetes


def test_summarize_deployment():
    yaml_text = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-api
  namespace: prod
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: auth-api
          image: registry/auth-api:latest
          ports:
            - containerPort: 8080
"""
    entries = summarize_kubernetes(yaml_text, "k8s/auth.yaml")
    assert len(entries) == 1
    e = entries[0]
    assert "Deployment" in e.rationale
    assert "auth-api" in e.rationale
    assert "prod" in e.rationale
    assert "3 replicas" in e.rationale
    assert "deploy" in e.tags
    assert "auto-summary" in e.tags
    assert "kubernetes" in e.tags


def test_summarize_service():
    yaml_text = """
apiVersion: v1
kind: Service
metadata:
  name: auth-api
  namespace: prod
spec:
  selector:
    app: auth-api
  ports:
    - port: 80
      targetPort: 8080
"""
    entries = summarize_kubernetes(yaml_text, "k8s/svc.yaml")
    assert any("Service" in e.rationale for e in entries)


def test_summarize_multi_document():
    yaml_text = """
apiVersion: v1
kind: Service
metadata: {name: a, namespace: p}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: a, namespace: p}
spec:
  replicas: 2
"""
    entries = summarize_kubernetes(yaml_text, "k8s/all.yaml")
    kinds = [r for e in entries for r in [e.rationale]]
    assert any("Service" in r for r in kinds)
    assert any("Deployment" in r for r in kinds)


def test_summarize_invalid_yaml_returns_empty():
    assert summarize_kubernetes(":::: not yaml ::::", "x.yaml") == []
```

- [ ] **Step 2: Implement**

`~/Desktop/xeno/contx/contx/summarizers/kubernetes.py`:

```python
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
```

Also register at import time. Add to `contx/summarizers/__init__.py` (after the dataclass):

```python
def _register_builtin_summarizers() -> None:
    from contx.summarizers.kubernetes import summarize_kubernetes
    from contx.summarizers.registry import register_summarizer
    register_summarizer("kubernetes", summarize_kubernetes)


_register_builtin_summarizers()
```

- [ ] **Step 3: Verify tests pass**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/summarizers/ tests/test_summarizer_kubernetes.py && git commit -m "feat(summarizers): add kubernetes summarizer

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: github_actions + docker_compose summarizers (TDD)

**Files:**
- Create: `contx/summarizers/github_actions.py`
- Create: `contx/summarizers/docker_compose.py`
- Create: `tests/test_summarizer_github_actions.py`
- Create: `tests/test_summarizer_docker_compose.py`

- [ ] **Step 1: Tests for github_actions**

`tests/test_summarizer_github_actions.py`:

```python
from contx.summarizers.github_actions import summarize_github_actions


def test_summarize_workflow():
    yaml_text = """
name: CI
on:
  push:
    branches: [main]
  pull_request: {}
jobs:
  test:
    runs-on: ubuntu-latest
    steps: []
  build:
    runs-on: ubuntu-latest
    steps:
      - name: secret
        run: echo ${{ secrets.NPM_TOKEN }}
"""
    entries = summarize_github_actions(yaml_text, ".github/workflows/ci.yml")
    assert len(entries) == 1
    e = entries[0]
    assert "CI" in e.rationale
    assert "2 jobs" in e.rationale
    assert "push" in e.rationale
    assert "NPM_TOKEN" in e.rationale
    assert "github-actions" in e.tags


def test_summarize_invalid_returns_empty():
    assert summarize_github_actions("::::", "x.yml") == []
```

- [ ] **Step 2: Implement github_actions**

`contx/summarizers/github_actions.py`:

```python
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
```

Register it in `contx/summarizers/__init__.py`:

```python
def _register_builtin_summarizers() -> None:
    from contx.summarizers.docker_compose import summarize_docker_compose
    from contx.summarizers.github_actions import summarize_github_actions
    from contx.summarizers.kubernetes import summarize_kubernetes
    from contx.summarizers.registry import register_summarizer
    register_summarizer("kubernetes", summarize_kubernetes)
    register_summarizer("github_actions", summarize_github_actions)
    register_summarizer("docker_compose", summarize_docker_compose)
```

- [ ] **Step 3: Tests for docker_compose**

`tests/test_summarizer_docker_compose.py`:

```python
from contx.summarizers.docker_compose import summarize_docker_compose


def test_summarize_services():
    yaml_text = """
version: '3'
services:
  api:
    image: my/api:latest
    depends_on: [db]
  db:
    image: postgres:15
"""
    entries = summarize_docker_compose(yaml_text, "docker-compose.yml")
    assert len(entries) == 1
    r = entries[0].rationale
    assert "api" in r
    assert "db" in r
    assert "depends_on" in r or "depends on" in r
    assert "docker-compose" in entries[0].tags


def test_summarize_invalid_returns_empty():
    assert summarize_docker_compose("::::", "x.yml") == []
```

- [ ] **Step 4: Implement docker_compose**

`contx/summarizers/docker_compose.py`:

```python
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
    if not isinstance(services, dict):
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
```

- [ ] **Step 5: Verify all tests pass**

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/summarizers/ tests/test_summarizer_github_actions.py tests/test_summarizer_docker_compose.py && git commit -m "feat(summarizers): add github_actions + docker_compose

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: `contx bootstrap-deploy` command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Tests** — append to `tests/test_cli.py`:

```python
def test_bootstrap_deploy_writes_summaries(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    import json
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    # Add a k8s tracked-path
    cfg_path = tmp_repo / ".contx" / "config.json"
    raw = json.loads(cfg_path.read_text())
    raw["tracked_paths"].append({"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"})
    cfg_path.write_text(json.dumps(raw))
    (tmp_repo / "k8s").mkdir()
    (tmp_repo / "k8s" / "auth.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: auth, namespace: prod}\nspec: {replicas: 2}\n"
    )
    result = runner.invoke(app, ["bootstrap-deploy"])
    assert result.exit_code == 0, result.output
    sidecar = tmp_repo / ".contx" / "k8s" / "auth.yaml.jsonl"
    assert sidecar.is_file()
    content = sidecar.read_text()
    assert "Deployment" in content
    assert "auto-summary" in content
```

- [ ] **Step 2: Add the command to `contx/cli.py`**

```python
@app.command(name="bootstrap-deploy")
def bootstrap_deploy() -> None:
    """Run all registered summarizers over their matching tracked_paths."""
    from datetime import datetime, timezone
    from ulid import ULID
    from contx.config import load_config
    from contx.entry import Entry
    from contx.ignore import matches_any_pattern
    from contx.paths import CTX_DIR
    from contx.store import append_entry
    from contx.summarizers.registry import get_summarizer

    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized. Run `contx init --no-bootstrap` first.", err=True)
        raise typer.Exit(code=2)

    cfg = load_config(repo)
    written = 0
    now = datetime.now(timezone.utc)

    for tp in cfg.tracked_paths:
        if tp.get("kind") != "deploy":
            continue
        sname = tp.get("summarizer")
        if not sname:
            continue
        summarizer = get_summarizer(sname)
        if summarizer is None:
            typer.echo(f"warning: summarizer '{sname}' not found, skipping {tp['glob']}", err=True)
            continue
        glob = tp["glob"]
        for path in sorted(repo.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(repo))
            if rel.startswith(".git/") or rel.startswith(f"{CTX_DIR}/"):
                continue
            if not matches_any_pattern(rel, [glob]):
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            summaries = summarizer(text, rel)
            for s in summaries:
                entry = Entry(
                    id=str(ULID()),
                    kind="file" if s.symbol is None else "symbol",
                    symbol=s.symbol,
                    event="created",
                    rationale=s.rationale,
                    tags=list(s.tags),
                    author="contx-bootstrap",
                    timestamp=now,
                    agent="audit",
                    related=[],
                )
                append_entry(repo, rel, entry)
                written += 1

    typer.echo(f"bootstrap-deploy wrote {written} summary entries")
```

- [ ] **Step 3: Verify tests pass + full suite green**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): add 'contx bootstrap-deploy' command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: README + plan doc

Append a "Deployment-manifest awareness" section to README documenting `tracked_paths`, the summarizers, and `bootstrap-deploy`. Then commit:

```bash
cd ~/Desktop/xeno/contx && git add README.md docs/plans/2026-05-23-contx-b3-deployment-awareness.md && git commit -m "docs: deployment awareness + Plan B3 file

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §2.1 Track manifests in the hook → Tasks 1, 2 (tracked_paths schema + staging.compute_drift uses it)
- §2.2 Auto-summarize → Tasks 4-7 (registry + 3 summarizers + bootstrap-deploy command)
- §2.3 When summarizers run → Task 7 (`contx bootstrap-deploy`) — `audit --summarize-new` deferred to a follow-up since the design lists it as "off by default" and not blocking
- §2.4 Module structure → Tasks 4-7

**Placeholders:** none.

**Type consistency:** `Config.tracked_paths` is `list[dict]` everywhere; `SummaryEntry` shape is identical across summarizers; `get_summarizer` returns `Summarizer | None` consistently.
