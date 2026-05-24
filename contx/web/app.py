"""Read-only web UI for browsing contx entries in a repo."""

from __future__ import annotations

import os
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from contx.paths import CTX_DIR, SIDECAR_SUFFIX, parse_symbol_ref, source_path_for_sidecar
from contx.repo import find_repo_root
from contx.store import fold_entries, read_entries

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def find_open_port(start: int, host: str = "127.0.0.1", *, attempts: int = 10) -> int:
    """Return the first port in [start, start+attempts) that's free to bind on host.

    Raises OSError if none in the range are free.
    """
    for offset in range(attempts):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"no free port in {start}..{start + attempts - 1} on {host}")


def _repo_root() -> Path:
    override = os.environ.get("CONTX_REPO_ROOT")
    return find_repo_root(Path(override) if override else Path.cwd())


def _entry_view(entry) -> dict:  # type: ignore[no-untyped-def]
    return {
        "timestamp": entry.timestamp.isoformat(),
        "event": entry.event,
        "author": entry.author,
        "agent": entry.agent,
        "tags": entry.tags,
        "rationale": entry.rationale,
        "symbol": entry.symbol,
    }


def _list_tracked_files(repo_root: Path) -> list[str]:
    ctx_dir = repo_root / CTX_DIR
    if not ctx_dir.is_dir():
        return []
    out: list[str] = []
    for sidecar in sorted(ctx_dir.rglob(f"*{SIDECAR_SUFFIX}")):
        try:
            src = source_path_for_sidecar(repo_root, sidecar)
            out.append(str(src.relative_to(repo_root)))
        except ValueError:
            continue
    return out


def create_app(repo_root: Path | None = None) -> FastAPI:
    """Construct the FastAPI app. Pass repo_root in tests; defaults to env/cwd."""
    app = FastAPI(title="contx", description="Read-only viewer for contx intent")
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    root = repo_root or _repo_root()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        files = _list_tracked_files(root)
        return templates.TemplateResponse(
            request, "index.html",
            {"files": files, "repo": str(root)},
        )

    @app.get("/file/{file_path:path}", response_class=HTMLResponse)
    def file_view(request: Request, file_path: str) -> HTMLResponse:
        entries = read_entries(root, file_path)
        if not entries:
            raise HTTPException(status_code=404, detail=f"No context for {file_path}")
        folded = fold_entries(entries)
        return templates.TemplateResponse(
            request, "file.html",
            {
                "file": file_path,
                "folded": folded,
                "log": [_entry_view(e) for e in entries],
            },
        )

    @app.get("/symbol/{ref:path}", response_class=HTMLResponse)
    def symbol_view(request: Request, ref: str) -> HTMLResponse:
        try:
            file_path, symbol = parse_symbol_ref(ref.replace("::", "::", 1))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid symbol ref: {ref}")
        if symbol is None:
            raise HTTPException(status_code=400, detail=f"No symbol in ref: {ref!r}")
        # ref arrives as "src/foo.py::symbol" — parse_symbol_ref handles "::"
        entries = read_entries(root, file_path)
        symbol_entries = [e for e in entries if e.symbol == symbol]
        if not symbol_entries:
            raise HTTPException(status_code=404, detail=f"No context for {ref}")
        folded = fold_entries(entries)
        return templates.TemplateResponse(
            request, "symbol.html",
            {
                "file": file_path,
                "symbol": symbol,
                "intent": folded.symbols.get(symbol),
                "log": [_entry_view(e) for e in symbol_entries],
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    def search_view(request: Request, q: str | None = None) -> HTMLResponse:
        from contx.search import search_entries
        hits = search_entries(root, q, limit=100) if q else []
        return templates.TemplateResponse(
            request, "search.html",
            {"q": q or "", "hits": hits},
        )

    @app.get("/timeline", response_class=HTMLResponse)
    def timeline_view(request: Request, limit: int = 50) -> HTMLResponse:
        items: list[dict] = []
        ctx_dir = root / CTX_DIR
        if ctx_dir.is_dir():
            for sidecar in sorted(ctx_dir.rglob(f"*{SIDECAR_SUFFIX}")):
                try:
                    src = source_path_for_sidecar(root, sidecar)
                except ValueError:
                    continue
                rel = str(src.relative_to(root))
                for e in read_entries(root, rel):
                    items.append({"file": rel, **_entry_view(e)})
        items.sort(key=lambda i: i["timestamp"], reverse=True)
        items = items[:limit]
        return templates.TemplateResponse(
            request, "timeline.html",
            {"items": items},
        )

    return app
