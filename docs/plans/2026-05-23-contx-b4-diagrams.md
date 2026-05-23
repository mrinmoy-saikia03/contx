# contx — Plan B4: Diagrams (file-map → draw.io)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Ship `contx diagram --type files` — renders the repo's intent graph as draw.io XML, saved to `.contx/diagrams/files.drawio` and committed alongside the entries.

**Architecture:** Three units. `graph.py` walks `.contx/` and builds nodes/edges. `layout.py` assigns positions via a simple force-directed algorithm (pure Python). `drawio.py` emits mxGraph XML. CLI plugs them together.

**Tech Stack:** Python 3.11+, stdlib only. No new deps. Reuses Plan 1's storage layer and Plan B1's ignore patterns.

**Companion spec:** `docs/specs/2026-05-23-contx-bootstrap-deploy-diagrams-design.md` §3.

---

## Task 1: graph.py — build node/edge graph from sidecars (TDD)

**Files:**
- Create: `contx/diagram/__init__.py`
- Create: `contx/diagram/graph.py`
- Create: `tests/test_diagram_graph.py`

- [ ] **Step 1: Tests**

`tests/test_diagram_graph.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from contx.config import default_config, save_config
from contx.diagram.graph import FileNode, build_file_graph
from contx.entry import Entry
from contx.store import append_entry


def _entry(symbol: str | None, rationale: str, related: list[str] | None = None) -> Entry:
    return Entry(
        id="01H" + rationale[:4].upper().ljust(23, "0"),
        kind="symbol" if symbol else "file",
        symbol=symbol,
        event="created",
        rationale=rationale,
        tags=[],
        author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli",
        related=related or [],
    )


def test_build_graph_collects_nodes_per_file(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "auth module"))
    append_entry(tmp_repo, "src/util.py", _entry(None, "util module"))
    graph = build_file_graph(tmp_repo)
    paths = {n.file for n in graph.nodes}
    assert "src/auth.py" in paths
    assert "src/util.py" in paths


def test_node_label_and_intent(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry(None, "auth module purpose"))
    graph = build_file_graph(tmp_repo)
    node = next(n for n in graph.nodes if n.file == "src/auth.py")
    assert node.file_intent == "auth module purpose"


def test_edges_from_related_backlinks(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth.py", _entry("login", "x", related=["src/sso.py::route_eu"]))
    append_entry(tmp_repo, "src/sso.py", _entry("route_eu", "y"))
    graph = build_file_graph(tmp_repo)
    files_in_edges = {(e.src_file, e.dst_file) for e in graph.edges}
    assert ("src/auth.py", "src/sso.py") in files_in_edges


def test_edges_deduplicated(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/a.py", _entry("x", "r", related=["src/b.py::y"]))
    append_entry(tmp_repo, "src/a.py", _entry("z", "r", related=["src/b.py::y"]))
    append_entry(tmp_repo, "src/b.py", _entry(None, "module b"))
    graph = build_file_graph(tmp_repo)
    edges = [(e.src_file, e.dst_file) for e in graph.edges]
    assert edges.count(("src/a.py", "src/b.py")) == 1


def test_node_directory_grouping(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    append_entry(tmp_repo, "src/auth/login.py", _entry(None, "x"))
    append_entry(tmp_repo, "tests/test_login.py", _entry(None, "y"))
    graph = build_file_graph(tmp_repo)
    groups = {n.group for n in graph.nodes}
    assert "src" in groups
    assert "tests" in groups


def test_empty_repo_returns_empty_graph(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    graph = build_file_graph(tmp_repo)
    assert graph.nodes == []
    assert graph.edges == []
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

`~/Desktop/xeno/contx/contx/diagram/__init__.py`:

```python
"""contx diagram — render the intent graph to draw.io XML."""

from __future__ import annotations
```

`~/Desktop/xeno/contx/contx/diagram/graph.py`:

```python
"""Build a file-level node/edge graph from contx sidecars."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from contx.paths import CTX_DIR, SIDECAR_SUFFIX, parse_symbol_ref, source_path_for_sidecar
from contx.store import fold_entries, read_entries


@dataclass(frozen=True)
class FileNode:
    file: str                 # relative path
    file_intent: str | None
    group: str                # top-level directory (e.g. "src", "tests", "k8s")


@dataclass(frozen=True)
class FileEdge:
    src_file: str
    dst_file: str


@dataclass(frozen=True)
class FileGraph:
    nodes: list[FileNode] = field(default_factory=list)
    edges: list[FileEdge] = field(default_factory=list)


def _top_dir(rel: str) -> str:
    head = rel.split("/", 1)[0]
    return head if head else "."


def build_file_graph(repo_root: Path) -> FileGraph:
    """Walk .contx/ and produce a FileGraph of file-level nodes + related-backlink edges."""
    ctx_dir = repo_root / CTX_DIR
    if not ctx_dir.is_dir():
        return FileGraph(nodes=[], edges=[])

    nodes: list[FileNode] = []
    seen_files: set[str] = set()
    edge_set: set[tuple[str, str]] = set()

    for sidecar in sorted(ctx_dir.rglob(f"*{SIDECAR_SUFFIX}")):
        try:
            src = source_path_for_sidecar(repo_root, sidecar)
        except ValueError:
            continue
        rel = str(src.relative_to(repo_root))
        if rel in seen_files:
            continue
        seen_files.add(rel)

        entries = read_entries(repo_root, rel)
        folded = fold_entries(entries)
        nodes.append(FileNode(
            file=rel,
            file_intent=folded.file_intent,
            group=_top_dir(rel),
        ))

        # Collect edges from `related` backlinks
        for e in entries:
            for ref in e.related:
                try:
                    target_file, _sym = parse_symbol_ref(ref)
                except ValueError:
                    continue
                if target_file and target_file != rel:
                    edge_set.add((rel, target_file))

    edges = [FileEdge(src_file=a, dst_file=b) for a, b in sorted(edge_set)]
    return FileGraph(nodes=nodes, edges=edges)
```

- [ ] **Step 4: Verify 6 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/diagram/ tests/test_diagram_graph.py && git commit -m "feat(diagram): build file-level node/edge graph from sidecars

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: layout.py — force-directed positioning (TDD)

**Files:**
- Create: `contx/diagram/layout.py`
- Create: `tests/test_diagram_layout.py`

- [ ] **Step 1: Tests**

`tests/test_diagram_layout.py`:

```python
from contx.diagram.graph import FileEdge, FileGraph, FileNode
from contx.diagram.layout import compute_positions


def test_compute_positions_returns_one_per_node():
    graph = FileGraph(
        nodes=[
            FileNode(file="a.py", file_intent=None, group="src"),
            FileNode(file="b.py", file_intent=None, group="src"),
        ],
        edges=[FileEdge(src_file="a.py", dst_file="b.py")],
    )
    pos = compute_positions(graph)
    assert set(pos.keys()) == {"a.py", "b.py"}


def test_compute_positions_two_nodes_separated():
    graph = FileGraph(
        nodes=[
            FileNode(file="a.py", file_intent=None, group="src"),
            FileNode(file="b.py", file_intent=None, group="src"),
        ],
        edges=[],
    )
    pos = compute_positions(graph)
    a = pos["a.py"]
    b = pos["b.py"]
    # Disconnected nodes should not be at the same coordinate
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    assert (dx * dx + dy * dy) > 1.0


def test_compute_positions_empty_graph_returns_empty():
    graph = FileGraph(nodes=[], edges=[])
    assert compute_positions(graph) == {}


def test_compute_positions_is_deterministic_with_seed():
    graph = FileGraph(
        nodes=[
            FileNode(file=f"f{i}.py", file_intent=None, group="src") for i in range(5)
        ],
        edges=[FileEdge(src_file="f0.py", dst_file="f1.py")],
    )
    a = compute_positions(graph, seed=42)
    b = compute_positions(graph, seed=42)
    assert a == b


def test_compute_positions_bounded():
    # All positions should fit roughly within the layout canvas
    graph = FileGraph(
        nodes=[FileNode(file=f"f{i}.py", file_intent=None, group="src") for i in range(20)],
        edges=[],
    )
    pos = compute_positions(graph, width=1000.0, height=1000.0)
    for x, y in pos.values():
        # Positions are within an expanded bounding box (force-directed can push beyond)
        assert -2000.0 < x < 3000.0
        assert -2000.0 < y < 3000.0
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

`~/Desktop/xeno/contx/contx/diagram/layout.py`:

```python
"""Simple force-directed layout for the file graph.

Pure Python — no NumPy or graphviz. Good enough for graphs up to a few hundred nodes.
Implements Fruchterman-Reingold with linear cooling, deterministic given a seed.
"""

from __future__ import annotations

import math
import random

from contx.diagram.graph import FileGraph

ITERATIONS = 100
DEFAULT_WIDTH = 1200.0
DEFAULT_HEIGHT = 800.0


def compute_positions(
    graph: FileGraph,
    *,
    width: float = DEFAULT_WIDTH,
    height: float = DEFAULT_HEIGHT,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """Return {file → (x, y)} via Fruchterman-Reingold force-directed layout."""
    if not graph.nodes:
        return {}

    rng = random.Random(seed)
    n = len(graph.nodes)
    # Initial random positions inside the canvas
    pos: dict[str, list[float]] = {
        node.file: [rng.uniform(0.0, width), rng.uniform(0.0, height)]
        for node in graph.nodes
    }

    area = width * height
    k = math.sqrt(area / max(n, 1))  # ideal edge length

    # Build adjacency for edge attractive forces
    edges = [(e.src_file, e.dst_file) for e in graph.edges]

    temperature = max(width, height) / 10.0
    cooling = temperature / max(ITERATIONS, 1)

    for _ in range(ITERATIONS):
        disp: dict[str, list[float]] = {node.file: [0.0, 0.0] for node in graph.nodes}

        # Repulsive forces between every pair of nodes
        files = list(pos.keys())
        for i, u in enumerate(files):
            for v in files[i + 1:]:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                dist = math.sqrt(dx * dx + dy * dy) or 0.01
                force = (k * k) / dist
                disp[u][0] += (dx / dist) * force
                disp[u][1] += (dy / dist) * force
                disp[v][0] -= (dx / dist) * force
                disp[v][1] -= (dy / dist) * force

        # Attractive forces along edges
        for a, b in edges:
            if a not in pos or b not in pos:
                continue
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = math.sqrt(dx * dx + dy * dy) or 0.01
            force = (dist * dist) / k
            disp[a][0] -= (dx / dist) * force
            disp[a][1] -= (dy / dist) * force
            disp[b][0] += (dx / dist) * force
            disp[b][1] += (dy / dist) * force

        # Apply displacement, clamped by temperature
        for node in graph.nodes:
            d = disp[node.file]
            length = math.sqrt(d[0] * d[0] + d[1] * d[1]) or 0.01
            limited = min(length, temperature)
            pos[node.file][0] += (d[0] / length) * limited
            pos[node.file][1] += (d[1] / length) * limited

        temperature = max(temperature - cooling, 0.01)

    return {f: (xy[0], xy[1]) for f, xy in pos.items()}
```

- [ ] **Step 4: Verify 5 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/diagram/layout.py tests/test_diagram_layout.py && git commit -m "feat(diagram): add Fruchterman-Reingold layout in pure Python

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: drawio.py — emit mxGraph XML (TDD)

**Files:**
- Create: `contx/diagram/drawio.py`
- Create: `tests/test_diagram_drawio.py`

- [ ] **Step 1: Tests**

`tests/test_diagram_drawio.py`:

```python
from xml.etree import ElementTree as ET

from contx.diagram.drawio import emit_drawio
from contx.diagram.graph import FileEdge, FileGraph, FileNode


def test_emit_returns_valid_xml():
    graph = FileGraph(
        nodes=[FileNode(file="a.py", file_intent="hi", group="src")],
        edges=[],
    )
    xml_text = emit_drawio(graph, positions={"a.py": (10.0, 20.0)})
    root = ET.fromstring(xml_text)
    assert root.tag == "mxfile"


def test_emit_includes_one_cell_per_node():
    graph = FileGraph(
        nodes=[
            FileNode(file="a.py", file_intent="a", group="src"),
            FileNode(file="b.py", file_intent="b", group="src"),
        ],
        edges=[],
    )
    positions = {"a.py": (10.0, 20.0), "b.py": (110.0, 20.0)}
    xml_text = emit_drawio(graph, positions=positions)
    root = ET.fromstring(xml_text)
    cells = root.findall(".//mxCell")
    # 2 nodes + parent cells (root + layer)
    node_cells = [c for c in cells if c.get("vertex") == "1"]
    assert len(node_cells) == 2


def test_emit_includes_edges():
    graph = FileGraph(
        nodes=[
            FileNode(file="a.py", file_intent="a", group="src"),
            FileNode(file="b.py", file_intent="b", group="src"),
        ],
        edges=[FileEdge(src_file="a.py", dst_file="b.py")],
    )
    positions = {"a.py": (10.0, 20.0), "b.py": (110.0, 20.0)}
    xml_text = emit_drawio(graph, positions=positions)
    root = ET.fromstring(xml_text)
    edge_cells = [c for c in root.findall(".//mxCell") if c.get("edge") == "1"]
    assert len(edge_cells) == 1


def test_emit_node_labels_use_file_path():
    graph = FileGraph(
        nodes=[FileNode(file="src/auth/login.py", file_intent=None, group="src")],
        edges=[],
    )
    xml_text = emit_drawio(graph, positions={"src/auth/login.py": (0.0, 0.0)})
    assert "src/auth/login.py" in xml_text


def test_emit_tooltip_uses_intent_when_present():
    graph = FileGraph(
        nodes=[FileNode(file="a.py", file_intent="auth module purpose XXX", group="src")],
        edges=[],
    )
    xml_text = emit_drawio(graph, positions={"a.py": (0.0, 0.0)})
    assert "auth module purpose XXX" in xml_text
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

`~/Desktop/xeno/contx/contx/diagram/drawio.py`:

```python
"""Emit mxGraph / draw.io XML from a FileGraph + positions."""

from __future__ import annotations

import html
from xml.etree import ElementTree as ET

from contx.diagram.graph import FileGraph

NODE_WIDTH = 160
NODE_HEIGHT = 50

# A simple palette indexed by group name (hashed); enough variety for typical repos.
_PALETTE = [
    "#E3F2FD", "#FFF3E0", "#F3E5F5", "#E8F5E9",
    "#FFFDE7", "#FCE4EC", "#E0F7FA", "#FFEBEE",
]


def _color_for_group(group: str) -> str:
    return _PALETTE[hash(group) % len(_PALETTE)]


def emit_drawio(graph: FileGraph, *, positions: dict[str, tuple[float, float]]) -> str:
    """Render the graph as mxGraph XML (the contents of a .drawio file)."""
    mxfile = ET.Element("mxfile", attrib={
        "host": "contx",
        "type": "device",
        "version": "1",
    })
    diagram = ET.SubElement(mxfile, "diagram", attrib={"name": "contx file-map"})
    graph_model = ET.SubElement(diagram, "mxGraphModel", attrib={
        "dx": "1200", "dy": "800",
        "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1",
        "connect": "1", "arrows": "1",
        "fold": "1", "page": "1",
        "pageScale": "1", "pageWidth": "1200", "pageHeight": "800",
    })
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", attrib={"id": "0"})
    ET.SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

    file_to_id: dict[str, str] = {}
    for i, node in enumerate(graph.nodes):
        cell_id = f"n{i}"
        file_to_id[node.file] = cell_id
        x, y = positions.get(node.file, (0.0, 0.0))
        color = _color_for_group(node.group)
        style = (
            f"rounded=1;whiteSpace=wrap;html=1;"
            f"fillColor={color};strokeColor=#666666;"
            f"fontSize=11;"
        )
        tooltip = node.file_intent or ""
        cell = ET.SubElement(root, "mxCell", attrib={
            "id": cell_id,
            "value": html.escape(node.file),
            "style": style,
            "vertex": "1",
            "parent": "1",
        })
        if tooltip:
            # draw.io renders the `tooltip` attribute on hover
            cell.set("tooltip", html.escape(tooltip))
        ET.SubElement(cell, "mxGeometry", attrib={
            "x": f"{int(x)}",
            "y": f"{int(y)}",
            "width": str(NODE_WIDTH),
            "height": str(NODE_HEIGHT),
            "as": "geometry",
        })

    for i, edge in enumerate(graph.edges):
        src_id = file_to_id.get(edge.src_file)
        dst_id = file_to_id.get(edge.dst_file)
        if not src_id or not dst_id:
            continue
        cell = ET.SubElement(root, "mxCell", attrib={
            "id": f"e{i}",
            "edge": "1",
            "source": src_id,
            "target": dst_id,
            "parent": "1",
            "style": "endArrow=classic;html=1;rounded=1;strokeColor=#999999;",
        })
        ET.SubElement(cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)
```

- [ ] **Step 4: Verify 5 tests pass**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/diagram/drawio.py tests/test_diagram_drawio.py && git commit -m "feat(diagram): emit draw.io mxGraph XML for the file graph

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `contx diagram` CLI command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Tests** — append to `tests/test_cli.py`:

```python
def test_diagram_files_writes_drawio(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone
    from contx.entry import Entry
    from contx.store import append_entry

    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    entry = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file", symbol=None, event="created", rationale="auth module",
        tags=[], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli", related=[],
    )
    append_entry(tmp_repo, "src/auth.py", entry)
    result = runner.invoke(app, ["diagram"])
    assert result.exit_code == 0, result.output
    out_path = tmp_repo / ".contx" / "diagrams" / "files.drawio"
    assert out_path.is_file()
    content = out_path.read_text()
    assert "<mxfile" in content
    assert "src/auth.py" in content


def test_diagram_with_custom_out(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from datetime import datetime, timezone
    from contx.entry import Entry
    from contx.store import append_entry

    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    entry = Entry(
        id="01HXYZ0000000000000000000K",
        kind="file", symbol=None, event="created", rationale="x",
        tags=[], author="t@x",
        timestamp=datetime(2026, 5, 21, tzinfo=timezone.utc),
        agent="human-cli", related=[],
    )
    append_entry(tmp_repo, "src/a.py", entry)
    out = tmp_path / "custom.drawio"
    result = runner.invoke(app, ["diagram", "--out", str(out)])
    assert result.exit_code == 0
    assert out.is_file()


def test_diagram_unsupported_type_errors(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init", "--no-bootstrap"])
    result = runner.invoke(app, ["diagram", "--type", "symbols"])
    assert result.exit_code != 0
    assert "not implemented" in result.output.lower() or "not yet" in result.output.lower()
```

- [ ] **Step 2: Add the command to `contx/cli.py`**

```python
@app.command()
def diagram(
    type_: str = typer.Option("files", "--type", help="files | symbols | deploy"),
    out: Path | None = typer.Option(None, "--out", help="Output path (defaults to .contx/diagrams/<type>.drawio)"),
) -> None:
    """Render the intent graph as a draw.io XML file."""
    from contx.diagram.drawio import emit_drawio
    from contx.diagram.graph import build_file_graph
    from contx.diagram.layout import compute_positions

    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    if type_ == "files":
        graph = build_file_graph(repo)
    elif type_ in ("symbols", "deploy"):
        typer.echo(f"error: --type {type_} not yet implemented (only 'files' is available in MVP)", err=True)
        raise typer.Exit(code=2)
    else:
        typer.echo(f"error: unknown --type {type_!r}; expected files|symbols|deploy", err=True)
        raise typer.Exit(code=2)

    positions = compute_positions(graph)
    xml = emit_drawio(graph, positions=positions)

    if out is None:
        out = repo / ".contx" / "diagrams" / f"{type_}.drawio"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml)
    typer.echo(f"wrote {out} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")
```

- [ ] **Step 3: Verify tests pass + full suite green**

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): add 'contx diagram' command (files type for MVP)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: README + plan doc

Append a "Diagrams" section to README explaining `contx diagram`, the output location (`.contx/diagrams/files.drawio`), and how to open the file (https://app.diagrams.net or VS Code extension). Note that `--type symbols` and `--type deploy` are reserved for future work. Commit:

```bash
cd ~/Desktop/xeno/contx && git add README.md docs/plans/2026-05-23-contx-b4-diagrams.md && git commit -m "docs: diagrams + Plan B4 file

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §3.1 file-map diagram type → Tasks 1, 4
- §3.2 draw.io XML output → Task 3
- §3.3 CLI → Task 4 (all 3 type flags reserved; only `files` implemented)
- §3.4 in/out scope items → covered (color by group via _PALETTE; tooltip = file_intent; pure-Python layout; no auto-regen)
- §3.5 module structure → Tasks 1-3

**Placeholders:** none. `--type symbols` and `--type deploy` deliberately raise a clear error pointing at MVP scope.

**Type consistency:** `FileNode`, `FileEdge`, `FileGraph` used identically across `graph.py`, `layout.py`, `drawio.py`, and `cli.py`.
