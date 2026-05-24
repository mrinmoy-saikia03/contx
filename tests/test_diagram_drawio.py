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
