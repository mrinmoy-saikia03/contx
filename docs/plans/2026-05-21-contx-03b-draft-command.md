# contx — Plan 3b: Interactive Draft Command

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** When the pre-commit hook (Plan 3) detects drift, give the user a one-shot way to fix it: `contx draft` opens an editor with a templated entry per drifted file. On save, entries are appended to `.contx/` sidecars and re-staged so the next `git commit` succeeds.

**Stretch goal (Task 4):** `contx draft --from-transcript` heuristically mines the most recent Claude Code session transcript at `~/.claude/projects/<sanitized-cwd>/*.jsonl` for likely rationales and pre-fills the template. Pure heuristics — no LLM API call. (Full LLM-based extraction is deferred to a later plan.)

**Architecture:**
- `contx/drafting.py` — pure-Python template build/parse.
- `contx/transcript.py` — Claude transcript discovery + heuristic mining (best-effort).
- `contx draft` CLI command — orchestrates: drift → template → editor → parse → append → restage.
- Hook prints a hint pointing at `contx draft` when blocking.

**Tech Stack:** Python 3.11+, existing storage layer. Editor invocation via `$VISUAL` or `$EDITOR` (matching git's convention).

---

## File Structure

```
~/Desktop/xeno/contx/
├── contx/
│   ├── drafting.py          # NEW: build_template + parse_template
│   ├── transcript.py        # NEW: find Claude session + heuristic mining
│   └── cli.py               # MODIFY: `contx draft` command + hook hint
└── tests/
    ├── test_drafting.py     # NEW
    ├── test_transcript.py   # NEW
    └── test_cli.py          # MODIFY: tests for draft command
```

---

## Task 1: `drafting.py` — template build + parse (TDD)

**Files:**
- Create: `contx/drafting.py`
- Create: `tests/test_drafting.py`

- [ ] **Step 1: Write tests**

```python
from contx.drafting import DraftedEntry, build_template, parse_template


def test_build_template_one_file():
    text = build_template(["src/foo.py"], prefilled={})
    assert "src/foo.py" in text
    assert "event: modified" in text
    assert "rationale:" in text


def test_build_template_uses_prefilled_rationale():
    text = build_template(["src/foo.py"], prefilled={"src/foo.py": "bumped retry to linear"})
    assert "bumped retry to linear" in text


def test_parse_template_extracts_one_entry():
    text = """\
# contx draft — fill in a rationale for each file, then save & exit.

## src/foo.py
event: modified
rationale: switched to linear retry
tags: incident
"""
    entries = parse_template(text)
    assert len(entries) == 1
    e = entries[0]
    assert e.file == "src/foo.py"
    assert e.event == "modified"
    assert e.rationale == "switched to linear retry"
    assert e.tags == ["incident"]
    assert e.skip is False


def test_parse_template_skips_empty_rationale():
    text = """\
## src/foo.py
event: modified
rationale:
tags:
"""
    entries = parse_template(text)
    assert len(entries) == 1
    assert entries[0].skip is True


def test_parse_template_handles_multiple_files():
    text = """\
## src/a.py
event: modified
rationale: A reason
tags: tag-a

## src/b.py
event: created
rationale: B reason
tags: tag-b1, tag-b2
"""
    entries = parse_template(text)
    assert {e.file for e in entries} == {"src/a.py", "src/b.py"}
    b = next(e for e in entries if e.file == "src/b.py")
    assert b.event == "created"
    assert b.tags == ["tag-b1", "tag-b2"]


def test_parse_template_ignores_comments():
    text = """\
# top-level comment
## src/foo.py
# inline comment
event: modified
rationale: x
tags:
"""
    entries = parse_template(text)
    assert entries[0].rationale == "x"


def test_parse_template_supports_symbol_in_filename_header():
    text = """\
## src/foo.py::Class.method
event: modified
rationale: bar
tags:
"""
    entries = parse_template(text)
    assert entries[0].file == "src/foo.py"
    assert entries[0].symbol == "Class.method"
```

- [ ] **Step 2: Run, verify failure** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `contx/drafting.py`**

```python
"""Template format for `contx draft` — build + parse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DraftedEntry:
    file: str
    symbol: str | None
    event: str
    rationale: str
    tags: list[str]
    skip: bool


TEMPLATE_HEADER = "# contx draft — fill in a rationale for each file, then save & exit.\n# Lines starting with # are ignored. Blank rationales are skipped.\n\n"


def build_template(missing_files: list[str], *, prefilled: dict[str, str] | None = None) -> str:
    """Render an editor template for the given files.

    `prefilled` maps file → rationale (optionally seeded from --from-transcript).
    """
    prefilled = prefilled or {}
    parts: list[str] = [TEMPLATE_HEADER]
    for f in missing_files:
        rationale = prefilled.get(f, "")
        parts.append(f"## {f}\n")
        parts.append("event: modified\n")
        parts.append(f"rationale: {rationale}\n")
        parts.append("tags:\n\n")
    return "".join(parts)


def _parse_tags(line: str) -> list[str]:
    raw = line.split(":", 1)[1].strip() if ":" in line else ""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def parse_template(text: str) -> list[DraftedEntry]:
    """Parse a filled-in template back to DraftedEntry objects.

    Skips comment lines (`#` at column 0 inside section bodies AND the header).
    A section ends at the next `## ` header or EOF.
    """
    entries: list[DraftedEntry] = []
    current_header: str | None = None
    current: dict[str, object] = {}

    def _flush() -> None:
        if current_header is None:
            return
        file, _, symbol_part = current_header.partition("::")
        rationale = str(current.get("rationale", "")).strip()
        entries.append(
            DraftedEntry(
                file=file,
                symbol=symbol_part or None,
                event=str(current.get("event", "modified")).strip() or "modified",
                rationale=rationale,
                tags=list(current.get("tags", [])),  # type: ignore[arg-type]
                skip=not rationale,
            )
        )

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            _flush()
            current_header = line[3:].strip()
            current = {}
            continue
        if current_header is None:
            continue
        # Inside a section
        if line.lstrip().startswith("#") or not line.strip():
            continue
        if line.lower().startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("rationale:"):
            current["rationale"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("tags:"):
            current["tags"] = _parse_tags(line)
    _flush()
    return entries
```

- [ ] **Step 4: Verify 7 tests pass.**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/drafting.py tests/test_drafting.py && git commit -m "feat(drafting): add template build + parse for contx draft

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `transcript.py` — find Claude session + heuristic mining (TDD)

**Files:**
- Create: `contx/transcript.py`
- Create: `tests/test_transcript.py`

- [ ] **Step 1: Write tests**

```python
import json
from pathlib import Path

from contx.transcript import (
    extract_rationales_for_files,
    find_recent_transcript,
    sanitize_cwd_for_project_dir,
)


def test_sanitize_cwd_replaces_slashes():
    assert sanitize_cwd_for_project_dir("/Users/me/code/repo") == "-Users-me-code-repo"


def test_find_recent_transcript_returns_none_when_dir_missing(tmp_path: Path):
    assert find_recent_transcript(tmp_path, claude_home=tmp_path / "nope") is None


def test_find_recent_transcript_picks_most_recent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    claude_home = tmp_path / "claude"
    project_dir = claude_home / "projects" / sanitize_cwd_for_project_dir(str(repo))
    project_dir.mkdir(parents=True)
    older = project_dir / "old.jsonl"
    newer = project_dir / "new.jsonl"
    older.write_text("{}\n")
    newer.write_text("{}\n")
    import os, time
    os.utime(older, (time.time() - 1000, time.time() - 1000))
    found = find_recent_transcript(repo, claude_home=claude_home)
    assert found == newer


def test_extract_rationales_finds_file_mentions(tmp_path: Path):
    transcript = tmp_path / "session.jsonl"
    lines = [
        {"type": "user", "message": {"content": "let's change src/foo.py to use linear retry because Auth0 rate-limited us"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/abs/repo/src/foo.py"}}]}},
    ]
    transcript.write_text("\n".join(json.dumps(x) for x in lines))
    rationales = extract_rationales_for_files(transcript, ["src/foo.py"])
    assert "src/foo.py" in rationales
    assert "linear retry" in rationales["src/foo.py"].lower()


def test_extract_rationales_returns_empty_for_unmatched(tmp_path: Path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {"content": "unrelated"}}) + "\n")
    rationales = extract_rationales_for_files(transcript, ["src/foo.py"])
    assert rationales == {}
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement `contx/transcript.py`**

```python
"""Best-effort discovery + heuristic mining of Claude Code session transcripts.

Heuristic, not LLM-based: scans user/assistant messages for sentences that
mention each file path and returns the closest preceding sentence as a
candidate rationale. Conservative — when in doubt, returns no match.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def sanitize_cwd_for_project_dir(cwd: str) -> str:
    """Claude Code stores projects under ~/.claude/projects/<sanitized-cwd>/.

    The sanitization replaces `/` with `-`. Matches Claude Code's own scheme.
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
    """Pull out human-readable text from a Claude message regardless of shape."""
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
                    # Include the tool input as a hint (often contains file paths)
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
        # Split into sentences crudely.
        for s in re.split(r"(?<=[.!?])\s+|\n+", text):
            s = s.strip()
            if s:
                sentences.append(s)

    out: dict[str, str] = {}
    for f in files:
        basename = Path(f).name
        for s in reversed(sentences):
            if f in s or basename in s:
                # Avoid sentences that are pure JSON tool-use dumps
                if s.startswith("{") and s.endswith("}"):
                    continue
                # Strip trailing punctuation noise; truncate to 200 chars
                out[f] = s[:200]
                break
    return out
```

- [ ] **Step 4: Verify 5 tests pass.**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/transcript.py tests/test_transcript.py && git commit -m "feat(transcript): heuristic mining of Claude Code session transcripts

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `contx draft` CLI command (TDD)

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

Editor invocation is testable by overriding `CONTX_EDITOR` env var with a small Python script the test writes; the script reads the template, fills in answers, writes back.

- [ ] **Step 1: Append tests to `tests/test_cli.py`**

```python
def test_draft_appends_entries_for_drifted_files(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)

    # Editor script that fills in a rationale and writes back
    editor = tmp_path / "fake_editor.sh"
    editor.write_text(
        '#!/bin/sh\n'
        'python3 -c "'
        'import sys\n'
        'p=sys.argv[1]\n'
        'open(p).read()\n'
        't=open(p).read().replace(\'rationale: \', \'rationale: filled-by-test \')\n'
        'open(p,\'w\').write(t)\n'
        '" "$1"\n'
    )
    editor.chmod(0o755)
    monkeypatch.setenv("CONTX_EDITOR", str(editor))

    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0, result.output

    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert sidecar.is_file()
    assert "filled-by-test" in sidecar.read_text()


def test_draft_no_drift_is_noop(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0
    assert "no drift" in result.output.lower() or "nothing to draft" in result.output.lower()


def test_draft_skips_blank_rationale(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import subprocess
    monkeypatch.chdir(tmp_repo)
    runner.invoke(app, ["init"])
    (tmp_repo / "src").mkdir()
    (tmp_repo / "src" / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "src/foo.py"], cwd=tmp_repo, check=True)

    # Editor that does nothing — leaves rationale blank
    editor = tmp_path / "noop.sh"
    editor.write_text('#!/bin/sh\nexit 0\n')
    editor.chmod(0o755)
    monkeypatch.setenv("CONTX_EDITOR", str(editor))

    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 0
    sidecar = tmp_repo / ".contx" / "src" / "foo.py.jsonl"
    assert not sidecar.is_file()  # nothing appended
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement the `draft` command in `cli.py`**

Add near the other imports:
```python
import os
import subprocess
import tempfile

from contx.drafting import build_template, parse_template
```

Add the command:
```python
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
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=False)
        with open(tmp_path) as f:
            filled = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    entries = parse_template(filled)
    written = 0
    for d in entries:
        if d.skip:
            continue
        ref = f"{d.file}::{d.symbol}" if d.symbol else d.file
        args = ["append", "--ref", ref, "--event", d.event, "--rationale", d.rationale]
        for t in d.tags:
            args += ["--tag", t]
        ret = runner_invoke_self(args) if False else None  # see note below
        # Use typer's CliRunner-style invocation isn't ideal here. Just call the helpers directly.
        from contx.entry import Entry
        from contx.paths import parse_symbol_ref
        from contx.store import append_entry
        from ulid import ULID
        from datetime import datetime, timezone
        file_path, sym = parse_symbol_ref(ref)
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

    # Re-stage .contx/ so the next git commit picks up the new entries
    subprocess.run(["git", "-C", str(repo), "add", ".contx"], check=False)
    typer.echo(f"appended {written} entries and staged .contx/. Run `git commit` again.")
```

Note: remove the `runner_invoke_self` line — it's a placeholder; the inline append-via-store logic is the real implementation. (Self-review should catch any lingering placeholder.)

- [ ] **Step 4: Verify tests pass.**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): add 'contx draft' interactive command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Hook hint points at `contx draft`

**Files:**
- Modify: `contx/cli.py` (just the `_precommit_check` command's message)

- [ ] **Step 1: Update `_precommit_check`**

Find the `_precommit_check` command in `contx/cli.py`. Update the helpful message to prefer `contx draft` over the long `contx append ...` example. Replace this block:

```python
        typer.echo("Fix: add a contx entry for each file, then re-stage and re-commit.")
        typer.echo("Example:")
        typer.echo(f"  contx append --ref {drift.missing[0]} --event modified --rationale 'why this changed'")
        typer.echo("  git add .contx/")
        typer.echo("  git commit")
```

with:

```python
        typer.echo("Fix interactively:")
        typer.echo("  contx draft        # opens editor for each file")
        typer.echo("  contx draft --from-transcript    # pre-fill from recent Claude session")
        typer.echo("  git commit         # re-run after .contx is auto-staged")
        typer.echo("")
        typer.echo("Or by hand:")
        typer.echo(f"  contx append --ref {drift.missing[0]} --event modified --rationale 'why this changed'")
        typer.echo("  git add .contx/ && git commit")
```

- [ ] **Step 2: Verify existing tests still pass** (the assertions for `"src/foo.py"` and `"context"` still match).

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py && git commit -m "feat(cli): pre-commit hint points at 'contx draft'

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: README + Plan 3b doc

- [ ] **Step 1: Append a "Fixing drift with `contx draft`" subsection to README** under the pre-commit hook section. Two paragraphs + example.
- [ ] **Step 2: Commit** README + this plan file.

---

## What ships after Plan 3b

`contx draft` closes the gap in Plan 3: when the hook blocks a commit, you don't have to hand-type a `contx append` for each file — you fix everything in one editor session. With `--from-transcript`, the editor opens with the most relevant sentence from your recent Claude conversation pre-filled per file, so you usually just need to tweak rather than write from scratch.

Combined with Plan 4 (skill that makes Claude call `contx_append` proactively), the gap should be small to start with — `draft` is the safety net.
