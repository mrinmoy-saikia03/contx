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
