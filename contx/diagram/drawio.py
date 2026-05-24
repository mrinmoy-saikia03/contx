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
