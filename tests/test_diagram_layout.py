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
