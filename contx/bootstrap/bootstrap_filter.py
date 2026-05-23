"""Heuristic for skipping low-signal commits during bootstrap."""

from __future__ import annotations

# Prefixes that mark a commit as low-signal. Matched case-insensitively against
# the commit subject after stripping leading whitespace.
NOISY_PREFIXES: tuple[str, ...] = (
    "wip",
    "typo",
    "fix typo",
    "format",
    "fmt",
    "lint",
    "merge",
    "bump",
    "chore(deps)",
    "version",
)

DEFAULT_MIN_DIFF_LINES = 5


def is_noisy_commit(
    subject: str,
    *,
    diff_lines: int,
    min_diff_lines: int = DEFAULT_MIN_DIFF_LINES,
) -> bool:
    """True if the commit should be skipped during bootstrap.

    Args:
        subject: Commit subject line.
        diff_lines: Total lines added+removed by this commit for the file under
            consideration.
        min_diff_lines: Threshold below which the commit is considered noise.
    """
    if diff_lines < min_diff_lines:
        return True
    s = subject.strip().lower()
    return any(s.startswith(prefix) for prefix in NOISY_PREFIXES)
