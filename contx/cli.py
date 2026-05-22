"""contx CLI entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer

from contx import __version__
from contx.config import default_config, save_config
from contx.entry import Entry
from contx.paths import parse_symbol_ref
from contx.repo import (
    NotInRepoError,
    find_repo_root,
    is_initialized,
)
from contx.store import append_entry, fold_entries, read_entries

app = typer.Typer(help="contx — git for context", no_args_is_help=True)


def _resolve_repo() -> Path:
    try:
        return find_repo_root(Path.cwd())
    except NotInRepoError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)


@app.command()
def version() -> None:
    """Print contx version."""
    typer.echo(__version__)


@app.command()
def init() -> None:
    """Initialize contx for the current git repo."""
    repo = _resolve_repo()
    if is_initialized(repo):
        typer.echo(f"contx already initialized at {repo / '.contx'}")
        return
    save_config(repo, default_config())
    typer.echo(f"initialized contx at {repo / '.contx'}")


def _git_author(repo: Path) -> str:
    """Read the user.email from git config, falling back to 'unknown'."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "config", "user.email"],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip() or "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


@app.command()
def append(
    ref: str = typer.Option(..., "--ref", help="file path, e.g. src/foo.py or src/foo.py::Class.method"),
    event: str = typer.Option(..., "--event", help="created|modified|renamed_in|renamed_out|moved_in|moved_out|deleted"),
    rationale: str = typer.Option(..., "--rationale", help="The *why* — free text"),
    tag: list[str] = typer.Option(None, "--tag", help="Optional tag (repeatable)"),
    related: list[str] = typer.Option(None, "--related", help="Related symbol refs (repeatable)"),
    agent: str = typer.Option("human-cli", "--agent", help="Source: claude-code|cursor|human-cli|audit"),
) -> None:
    """Append a context entry for a file or symbol."""
    from ulid import ULID

    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    try:
        file_path, symbol = parse_symbol_ref(ref)
        entry = Entry(
            id=str(ULID()),
            kind="symbol" if symbol else "file",
            symbol=symbol,
            event=event,
            rationale=rationale,
            tags=list(tag or []),
            author=_git_author(repo),
            timestamp=datetime.now(timezone.utc),
            agent=agent,  # type: ignore[arg-type]
            related=list(related or []),
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)
    sidecar = append_entry(repo, file_path, entry)
    typer.echo(f"appended entry {entry.id} → {sidecar.relative_to(repo)}")


@app.command()
def show(ref: str = typer.Argument(..., help="file path, or file::symbol")) -> None:
    """Print the folded current intent for a file or symbol."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    try:
        file_path, symbol = parse_symbol_ref(ref)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)
    entries = read_entries(repo, file_path)
    folded = fold_entries(entries)

    if symbol is None:
        if folded.file_intent is None:
            typer.echo(f"no context for {file_path}")
            return
        typer.echo(f"# {file_path}")
        typer.echo(folded.file_intent)
        if folded.symbols:
            typer.echo("")
            typer.echo(f"## symbols ({len(folded.symbols)})")
            for sym in sorted(folded.symbols):
                typer.echo(f"- {sym}")
        return

    if symbol not in folded.symbols:
        typer.echo(f"no context for {file_path}::{symbol}")
        return
    typer.echo(f"# {file_path}::{symbol}")
    typer.echo(folded.symbols[symbol])


@app.command(name="log")
def log_cmd(ref: str = typer.Argument(..., help="file path, or file::symbol")) -> None:
    """Print the full append-only log for a file or symbol."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    try:
        file_path, symbol = parse_symbol_ref(ref)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2)
    entries = read_entries(repo, file_path)
    if symbol is not None:
        entries = [e for e in entries if e.symbol == symbol]

    if not entries:
        typer.echo(f"no entries for {ref}")
        return

    for e in entries:
        sym = f"::{e.symbol}" if e.symbol else ""
        typer.echo(f"--- {e.timestamp.isoformat()} | {e.event} | {e.author} | {file_path}{sym}")
        if e.tags:
            typer.echo(f"tags: {', '.join(e.tags)}")
        typer.echo(e.rationale)
        typer.echo("")


from contx.staging import compute_drift


@app.command(name="_precommit-check", hidden=True)
def _precommit_check() -> None:
    """Internal: invoked by the pre-commit hook.

    Exits 0 if staged changes have paired context (or contx is not
    initialized, or enforcement is disabled). Exits 1 with a helpful
    message if drift is detected and `require_context_on_commit` is True.
    """
    repo = _resolve_repo()
    drift = compute_drift(repo)

    if drift.uninitialized:
        return

    if not drift.missing:
        return

    from contx.config import load_config
    cfg = load_config(repo)

    if cfg.require_context_on_commit:
        typer.echo("error: contx drift — the following files changed without a matching .contx/ entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        typer.echo("")
        typer.echo("Fix: add a contx entry for each file, then re-stage and re-commit.")
        typer.echo("Example:")
        typer.echo(f"  contx append --ref {drift.missing[0]} --event modified --rationale 'why this changed'")
        typer.echo("  git add .contx/")
        typer.echo("  git commit")
        typer.echo("")
        typer.echo("To bypass once: git commit --no-verify")
        typer.echo("To disable enforcement: set 'require_context_on_commit': false in .contx/config.json")
        raise typer.Exit(code=1)
    else:
        typer.echo("warning: contx drift — these files changed without a context entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        return
