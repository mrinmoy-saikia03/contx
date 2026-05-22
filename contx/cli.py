"""contx CLI entry point."""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import typer

from contx import __version__
from contx.config import default_config, save_config
from contx.drafting import build_template, parse_template
from contx.entry import Entry
from contx.paths import parse_symbol_ref
from contx.hooks import (
    install_pre_commit_hook,
    is_pre_commit_hook_installed,
    uninstall_pre_commit_hook,
)
from contx.repo import (
    NotInRepoError,
    find_repo_root,
    is_initialized,
)
from contx.store import append_entry, fold_entries, read_entries
from contx.skill_install import install_skill, uninstall_skill

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
def init(
    no_hook: bool = typer.Option(False, "--no-hook", help="Skip installing the pre-commit hook"),
) -> None:
    """Initialize contx for the current git repo."""
    repo = _resolve_repo()
    if is_initialized(repo):
        typer.echo(f"contx already initialized at {repo / '.contx'}")
        if not no_hook and not is_pre_commit_hook_installed(repo):
            install_pre_commit_hook(repo)
            typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")
        return
    save_config(repo, default_config())
    typer.echo(f"initialized contx at {repo / '.contx'}")
    if not no_hook:
        install_pre_commit_hook(repo)
        typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")


@app.command(name="install-hook")
def install_hook_cmd() -> None:
    """Install the contx pre-commit hook in the current repo."""
    repo = _resolve_repo()
    install_pre_commit_hook(repo)
    typer.echo(f"installed pre-commit hook at {repo / '.git' / 'hooks' / 'pre-commit'}")


@app.command(name="uninstall-hook")
def uninstall_hook_cmd() -> None:
    """Remove the contx pre-commit hook from the current repo."""
    repo = _resolve_repo()
    uninstall_pre_commit_hook(repo)
    typer.echo("removed contx pre-commit hook")


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


@app.command()
def draft(
    from_transcript: bool = typer.Option(False, "--from-transcript", help="Pre-fill from the most recent Claude transcript"),
) -> None:
    """Open an editor to add context for drifted files, then append + restage."""
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)

    drift = compute_drift(repo)
    if not drift.missing:
        typer.echo("no drift — nothing to draft.")
        return

    prefilled: dict[str, str] = {}
    if from_transcript:
        from contx.transcript import extract_rationales_for_files, find_recent_transcript
        t = find_recent_transcript(repo)
        if t is not None:
            prefilled = extract_rationales_for_files(t, drift.missing)
            if prefilled:
                typer.echo(f"pre-filled {len(prefilled)} rationales from {t.name}")

    template = build_template(drift.missing, prefilled=prefilled)

    editor = os.environ.get("CONTX_EDITOR") or os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"

    with tempfile.NamedTemporaryFile("w+", suffix=".contx-draft.md", delete=False) as f:
        f.write(template)
        tmp_path_str = f.name

    try:
        subprocess.run([editor, tmp_path_str], check=False)
        with open(tmp_path_str) as f:
            filled = f.read()
    finally:
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass

    entries = parse_template(filled)
    written = 0
    from contx.paths import parse_symbol_ref as _parse_symbol_ref
    from ulid import ULID

    for d in entries:
        if d.skip:
            continue
        ref = f"{d.file}::{d.symbol}" if d.symbol else d.file
        file_path, sym = _parse_symbol_ref(ref)
        entry = Entry(
            id=str(ULID()),
            kind="symbol" if sym else "file",
            symbol=sym,
            event=d.event,
            rationale=d.rationale,
            tags=list(d.tags),
            author=_git_author(repo),
            timestamp=datetime.now(timezone.utc),
            agent="human-cli",  # type: ignore[arg-type]
            related=[],
        )
        append_entry(repo, file_path, entry)
        written += 1

    if written == 0:
        typer.echo("no rationales filled in — nothing appended.")
        return

    subprocess.run(["git", "-C", str(repo), "add", ".contx"], check=False)
    typer.echo(f"appended {written} entries and staged .contx/. Run `git commit` again.")


def _source_repo_root() -> Path:
    """Locate the source repo root that holds skills/contx/SKILL.md."""
    import contx as _contx_pkg
    pkg_dir = Path(_contx_pkg.__file__).resolve().parent  # .../contx_repo/contx/
    candidates = [pkg_dir.parent, pkg_dir.parent.parent]
    for c in candidates:
        if (c / "skills" / "contx" / "SKILL.md").is_file():
            return c
    raise FileNotFoundError(
        "Could not locate skills/contx/SKILL.md relative to the installed contx package. "
        "Re-install contx in editable mode (`pip install -e .`) from a checkout that includes skills/."
    )


def _claude_home_path() -> Path:
    override = os.environ.get("CONTX_CLAUDE_HOME")
    return Path(override) if override else Path.home() / ".claude"


@app.command(name="install-skill")
def install_skill_cmd() -> None:
    """Install the contx Claude Code skill into ~/.claude/skills/contx/."""
    src = _source_repo_root()
    home = _claude_home_path()
    dest = install_skill(src_repo=src, claude_home=home)
    typer.echo(f"installed contx skill to {dest}")


@app.command(name="uninstall-skill")
def uninstall_skill_cmd() -> None:
    """Remove the contx Claude Code skill from ~/.claude/skills/contx/."""
    home = _claude_home_path()
    uninstall_skill(claude_home=home)
    typer.echo(f"removed contx skill from {home / 'skills' / 'contx'}")


@app.command()
def serve(
    port: int = typer.Option(4242, "--port", "-p", help="Port to bind (default 4242)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (default 127.0.0.1)"),
) -> None:
    """Launch the local read-only web UI."""
    import uvicorn
    from contx.web.app import create_app
    repo = _resolve_repo()
    if not is_initialized(repo):
        typer.echo("error: contx not initialized for this repo. Run `contx init` first.", err=True)
        raise typer.Exit(code=2)
    web_app = create_app(repo_root=repo)
    typer.echo(f"contx serving on http://{host}:{port}")
    uvicorn.run(web_app, host=host, port=port, log_level="warning")


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
        typer.echo("Fix interactively:")
        typer.echo("  contx draft                       # opens editor for each file")
        typer.echo("  contx draft --from-transcript     # pre-fill from recent Claude session")
        typer.echo("  git commit                         # re-run after .contx is auto-staged")
        typer.echo("")
        typer.echo("Or by hand:")
        typer.echo(f"  contx append --ref {drift.missing[0]} --event modified --rationale 'why this changed'")
        typer.echo("  git add .contx/ && git commit")
        typer.echo("")
        typer.echo("To bypass once: git commit --no-verify")
        typer.echo("To disable enforcement: set 'require_context_on_commit': false in .contx/config.json")
        raise typer.Exit(code=1)
    else:
        typer.echo("warning: contx drift — these files changed without a context entry:")
        for f in drift.missing:
            typer.echo(f"  - {f}")
        return
