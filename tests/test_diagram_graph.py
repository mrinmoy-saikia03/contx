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
