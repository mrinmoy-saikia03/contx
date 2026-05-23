"""contx bootstrap — seed entries from git history + source AST."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ulid import ULID

from contx.bootstrap.ast_dispatch import bootstrap_file
from contx.bootstrap.bootstrap_filter import is_noisy_commit
from contx.bootstrap.git_history import iter_commits_with_files
from contx.entry import Entry
from contx.ignore import load_effective_ignore_patterns, matches_any_pattern
from contx.paths import CTX_DIR, SIDECAR_SUFFIX
from contx.store import append_entry, read_entries

BOOTSTRAP_TAG = "bootstrap"
GIT_HISTORY_TAG = "git-history"


def _has_bootstrap_entries(repo_root: Path) -> bool:
    ctx_dir = repo_root / CTX_DIR
    if not ctx_dir.is_dir():
        return False
    for sidecar in ctx_dir.rglob(f"*{SIDECAR_SUFFIX}"):
        try:
            inner = sidecar.relative_to(ctx_dir)
            source_rel = str(inner)[:-len(SIDECAR_SUFFIX)]
        except ValueError:
            continue
        for e in read_entries(repo_root, source_rel):
            if BOOTSTRAP_TAG in e.tags:
                return True
    return False


def _iter_source_files(repo_root: Path, ignore_patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(repo_root))
        if rel.startswith(".git/") or rel.startswith(f"{CTX_DIR}/"):
            continue
        if matches_any_pattern(rel, ignore_patterns):
            continue
        out.append(path)
    return out


def _make_entry(
    *,
    kind: str,
    symbol: str | None,
    event: str,
    rationale: str,
    tags: list[str],
    author: str,
    timestamp: datetime,
) -> Entry:
    # Generate a ULID with the entry's timestamp so entries sort chronologically
    # across re-runs.
    ulid = ULID.from_timestamp(timestamp.timestamp())
    return Entry(
        id=str(ulid),
        kind=kind,  # type: ignore[arg-type]
        symbol=symbol,
        event=event,  # type: ignore[arg-type]
        rationale=rationale or "auto-bootstrapped — please fill in",
        tags=list(tags),
        author=author,
        timestamp=timestamp,
        agent="audit",
        related=[],
    )


def bootstrap_repo(
    repo_root: Path,
    *,
    do_ast: bool = True,
    do_git: bool = True,
    max_commits: int = 1000,
    min_diff_lines: int = 1,
    since: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Bootstrap `.contx/` entries for the repo. Returns the number of entries written."""
    if not force and _has_bootstrap_entries(repo_root):
        raise RuntimeError(
            "repo already bootstrapped; pass force=True to re-run (will append a supersede entry)"
        )

    ignore_patterns = load_effective_ignore_patterns(repo_root)
    now = datetime.now(timezone.utc)
    written = 0

    if force and _has_bootstrap_entries(repo_root):
        if not dry_run:
            # Write a marker on each file that already had bootstrap entries.
            ctx_dir = repo_root / CTX_DIR
            for sidecar in ctx_dir.rglob(f"*{SIDECAR_SUFFIX}"):
                inner = str(sidecar.relative_to(ctx_dir))[:-len(SIDECAR_SUFFIX)]
                marker = _make_entry(
                    kind="file",
                    symbol=None,
                    event="modified",
                    rationale="re-bootstrap; previous bootstrap entries superseded",
                    tags=[BOOTSTRAP_TAG, "supersede"],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                append_entry(repo_root, inner, marker)
                written += 1

    if do_ast:
        for path in _iter_source_files(repo_root, ignore_patterns):
            result = bootstrap_file(path)
            if result is None:
                continue
            rel = str(path.relative_to(repo_root))
            if result.file_doc or result.symbols:
                file_entry = _make_entry(
                    kind="file",
                    symbol=None,
                    event="created",
                    rationale=(result.file_doc or ""),
                    tags=[BOOTSTRAP_TAG],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                if not dry_run:
                    append_entry(repo_root, rel, file_entry)
                written += 1
            for sym in result.symbols:
                sym_entry = _make_entry(
                    kind="symbol",
                    symbol=sym.symbol,
                    event="created",
                    rationale=sym.doc or "",
                    tags=[BOOTSTRAP_TAG, sym.kind],
                    author="contx-bootstrap",
                    timestamp=now,
                )
                if not dry_run:
                    append_entry(repo_root, rel, sym_entry)
                written += 1

    if do_git:
        seen_files: set[str] = set()
        for commit in iter_commits_with_files(repo_root, max_commits=max_commits, since=since):
            for f in commit.files:
                if f.startswith(f"{CTX_DIR}/") or f.startswith(".git/"):
                    continue
                if matches_any_pattern(f, ignore_patterns):
                    continue
                diff = commit.diff_lines_by_file.get(f, 0)
                if is_noisy_commit(commit.subject, diff_lines=diff, min_diff_lines=min_diff_lines):
                    continue
                event = "created" if f not in seen_files else "modified"
                seen_files.add(f)
                # Compose rationale: subject + first line of body if present
                rationale = commit.subject
                body_first = commit.body.splitlines()[0] if commit.body.strip() else ""
                if body_first:
                    rationale = f"{commit.subject}\n\n{body_first}"
                try:
                    ts = datetime.fromisoformat(commit.timestamp)
                except ValueError:
                    ts = now
                entry = _make_entry(
                    kind="file",
                    symbol=None,
                    event=event,
                    rationale=rationale,
                    tags=[BOOTSTRAP_TAG, GIT_HISTORY_TAG],
                    author=commit.author,
                    timestamp=ts,
                )
                if not dry_run:
                    append_entry(repo_root, f, entry)
                written += 1

    return written
