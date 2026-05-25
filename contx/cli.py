"""contx CLI entry point — minimal surface: version, serve, _precommit-check.

All user-facing workflows (init, append, show, log, draft, ignore, export,
bootstrap, diagram, hook/skill management) live in Claude Code slash
commands at `skills/contx/commands/`. The Python CLI is intentionally tiny.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from contx import __version__
from contx.repo import NotInRepoError, find_repo_root, is_initialized

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
def serve(
    port: int = typer.Option(4242, "--port", "-p", help="Port to bind (default 4242)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (default 127.0.0.1)"),
    strict_port: bool = typer.Option(False, "--strict-port", help="Fail if --port is occupied"),
) -> None:
    """Launch the read-only local web UI."""
    import uvicorn
    from contx.web.app import create_app, find_open_port

    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run /contx-init in Claude Code.", err=True)
        raise typer.Exit(code=2)

    actual_port = port
    if not strict_port:
        try:
            actual_port = find_open_port(port, host=host, attempts=10)
        except OSError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        if actual_port != port:
            typer.echo(f"port {port} is in use; using {actual_port} instead (pass --strict-port to fail loudly)")

    web_app = create_app(repo_root=repo)
    typer.echo(f"contx serving on http://{host}:{actual_port}")
    uvicorn.run(web_app, host=host, port=actual_port, log_level="warning")


@app.command(name="_precommit-check", hidden=True)
def _precommit_check() -> None:
    """Internal: invoked by the git pre-commit hook.

    Exits 0 if staged changes have paired context (or contx is not
    initialized, or enforcement is disabled). Exits 1 with a helpful
    message if drift is detected and `require_context_on_commit` is True.
    """
    from contx.config import load_config
    from contx.staging import compute_drift

    repo = _resolve_repo()
    drift = compute_drift(repo)

    if drift.uninitialized or not drift.missing:
        return

    cfg = load_config(repo)

    if cfg.require_context_on_commit:
        typer.echo("error: contx drift — the following files changed without a matching .contx/ entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        typer.echo("")
        typer.echo("Fix it from Claude Code:")
        typer.echo("  /contx-draft        # propose entries from the staged diff + conversation")
        typer.echo("  git commit          # re-run after .contx is auto-staged")
        typer.echo("")
        typer.echo("Bypass once:    git commit --no-verify")
        typer.echo("Disable entirely:  set 'require_context_on_commit': false in .contx/config.json")
        raise typer.Exit(code=1)
    else:
        typer.echo("warning: contx drift — these files changed without a context entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        return
