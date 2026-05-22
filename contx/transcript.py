"""Best-effort discovery + heuristic mining of Claude Code session transcripts.

Heuristic, not LLM-based: scans user/assistant messages for sentences that
mention each file path and returns the closest matching sentence as a
candidate rationale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def sanitize_cwd_for_project_dir(cwd: str) -> str:
    """Claude Code stores projects under ~/.claude/projects/<sanitized-cwd>/.

    The sanitization replaces ``/`` with ``-``.
    """
    return cwd.replace("/", "-")


def _default_claude_home() -> Path:
    return Path.home() / ".claude"


def find_recent_transcript(repo_root: Path, *, claude_home: Path | None = None) -> Path | None:
    """Locate the most recently modified .jsonl transcript for this repo, or None."""
    claude_home = claude_home or _default_claude_home()
    project_dir = claude_home / "projects" / sanitize_cwd_for_project_dir(str(repo_root))
    if not project_dir.is_dir():
        return None
    candidates = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _flatten_message_content(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                t = part.get("type")
                if t == "text":
                    parts.append(str(part.get("text", "")))
                elif t == "tool_use":
                    parts.append(json.dumps(part.get("input", {})))
        return "\n".join(parts)
    return ""


def extract_rationales_for_files(transcript: Path, files: list[str]) -> dict[str, str]:
    """Heuristic: for each file, find the most recent sentence in the transcript
    that mentions it, and return that sentence as the candidate rationale.

    Returns a dict of file → rationale-snippet (only for files we found).
    """
    if not transcript.is_file():
        return {}

    sentences: list[str] = []
    for raw in transcript.read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message", {})
        text = _flatten_message_content(msg if isinstance(msg, dict) else {})
        for s in re.split(r"(?<=[.!?])\s+|\n+", text):
            s = s.strip()
            if s:
                sentences.append(s)

    out: dict[str, str] = {}
    for f in files:
        basename = Path(f).name
        for s in reversed(sentences):
            if f in s or basename in s:
                if s.startswith("{") and s.endswith("}"):
                    continue
                out[f] = s[:200]
                break
    return out
