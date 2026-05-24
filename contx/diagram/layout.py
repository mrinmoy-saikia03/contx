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

        # Apply displacement, clamped by temperature; also clamp positions to canvas
        for node in graph.nodes:
            d = disp[node.file]
            length = math.sqrt(d[0] * d[0] + d[1] * d[1]) or 0.01
            limited = min(length, temperature)
            pos[node.file][0] += (d[0] / length) * limited
            pos[node.file][1] += (d[1] / length) * limited
            # Soft-clamp to canvas bounds to prevent runaway repulsion
            pos[node.file][0] = max(-0.5 * width, min(1.5 * width, pos[node.file][0]))
            pos[node.file][1] = max(-0.5 * height, min(1.5 * height, pos[node.file][1]))

        temperature = max(temperature - cooling, 0.01)

    return {f: (xy[0], xy[1]) for f, xy in pos.items()}
