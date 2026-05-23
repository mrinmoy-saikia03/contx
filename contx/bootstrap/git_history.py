"""Walk `git log` and yield commits with their file lists + diff line counts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

_SEP = "\x1e"              # record separator (within the header line)
_START = "\n---COMMIT---\n"  # record-start marker injected by --pretty


@dataclass(frozen=True)
class GitCommit:
    sha: str
    author: str            # author email
    timestamp: str         # ISO8601
    subject: str
    body: str
    files: list[str] = field(default_factory=list)
    diff_lines_by_file: dict[str, int] = field(default_factory=dict)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def iter_commits_with_files(
    repo_root: Path,
    *,
    max_commits: int | None = None,
    since: str | None = None,
) -> Iterator[GitCommit]:
    """Yield each commit (oldest first) with its changed file list + diff stats.

    Resilient to empty repos (returns no commits).
    """
    fmt = _START + _SEP.join(["%H", "%ae", "%aI", "%s", "%b"])
    args = ["log", "--reverse", "--all", f"--pretty=format:{fmt}", "--numstat"]
    if since:
        args.append(f"{since}..HEAD")
    try:
        raw = _git(repo_root, *args)
    except subprocess.CalledProcessError:
        return

    # Split on the record-start marker; first element is always empty.
    chunks = raw.split(_START)
    count = 0
    for chunk in chunks:
        if not chunk.strip():
            continue

        # Each chunk: "SHA\x1eemail\x1eiso\x1esubject\x1ebody\nnumstat_lines..."
        # The header is everything up to the first \n; numstat follows.
        nl_pos = chunk.find("\n")
        if nl_pos == -1:
            header_line = chunk
            numstat_text = ""
        else:
            header_line = chunk[:nl_pos]
            numstat_text = chunk[nl_pos + 1:]

        head_parts = header_line.split(_SEP)
        if len(head_parts) < 4:
            continue
        sha = head_parts[0]
        author = head_parts[1]
        ts = head_parts[2]
        subject = head_parts[3]
        body = head_parts[4].strip() if len(head_parts) >= 5 else ""

        files: list[str] = []
        diffs: dict[str, int] = {}
        for line in numstat_text.splitlines():
            # numstat line: "added\tdeleted\tpath" or "-\t-\tpath" (binary)
            parts = line.split("\t")
            if len(parts) == 3 and (parts[0].isdigit() or parts[0] == "-"):
                path = parts[2]
                added = int(parts[0]) if parts[0].isdigit() else 0
                deleted = int(parts[1]) if parts[1].isdigit() else 0
                files.append(path)
                diffs[path] = added + deleted

        yield GitCommit(
            sha=sha,
            author=author,
            timestamp=ts,
            subject=subject,
            body=body,
            files=files,
            diff_lines_by_file=diffs,
        )
        count += 1
        if max_commits is not None and count >= max_commits:
            return


def iter_commits_for_file(
    repo_root: Path,
    rel_path: str,
    *,
    max_commits: int | None = None,
) -> Iterator[GitCommit]:
    """Same as iter_commits_with_files but filtered to commits that touched rel_path."""
    for commit in iter_commits_with_files(repo_root, max_commits=max_commits):
        if rel_path in commit.files:
            yield commit
