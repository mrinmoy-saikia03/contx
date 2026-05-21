"""Sidecar path resolution: source files <-> .contx/ mirror tree."""

from __future__ import annotations

from pathlib import Path

CTX_DIR = ".contx"
SIDECAR_SUFFIX = ".jsonl"


def sidecar_path_for_source(repo_root: Path, source: Path) -> Path:
    """Map a source file path to its sidecar path inside .contx/.

    `source` may be absolute (must live inside `repo_root`) or relative
    (taken as relative-to-repo-root as-is).
    """
    if source.is_absolute():
        try:
            rel = source.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"source {source} is outside the repo {repo_root}") from exc
    else:
        rel = source
    return repo_root / CTX_DIR / (str(rel) + SIDECAR_SUFFIX)


def source_path_for_sidecar(repo_root: Path, sidecar: Path) -> Path:
    """Reverse of sidecar_path_for_source. Raises if path isn't a sidecar."""
    if sidecar.is_absolute():
        try:
            rel = sidecar.relative_to(repo_root / CTX_DIR)
        except ValueError as exc:
            raise ValueError(f"{sidecar} is not a contx sidecar inside {repo_root}") from exc
    else:
        parts = sidecar.parts
        if not parts or parts[0] != CTX_DIR:
            raise ValueError(f"{sidecar} is not a contx sidecar")
        rel = Path(*parts[1:])

    name = rel.name
    if not name.endswith(SIDECAR_SUFFIX):
        raise ValueError(f"{sidecar} is not a contx sidecar (missing {SIDECAR_SUFFIX})")
    rel = rel.with_name(name[: -len(SIDECAR_SUFFIX)])
    return repo_root / rel


SYMBOL_SEP = "::"


def parse_symbol_ref(ref: str) -> tuple[str, str | None]:
    """Parse a reference like 'src/foo.py' or 'src/foo.py::Class.method'.

    Returns (file_path, symbol_or_None).
    """
    parts = ref.split(SYMBOL_SEP)
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"symbol ref must contain only one '{SYMBOL_SEP}' separator, got: {ref!r}")
