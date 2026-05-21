import typer

app = typer.Typer(help="contx — git for context", no_args_is_help=True)


@app.command("version")
def version() -> None:
    """Print contx version."""
    from contx import __version__
    typer.echo(__version__)


@app.command("init")
def init() -> None:
    """Initialise a contx store in the current repo."""
    typer.echo("not implemented yet")
