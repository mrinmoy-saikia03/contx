# contx — Plan 4: Claude Code Skill

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Ship a Claude Code skill (`contx`) that activates when the agent is working in a repo with `.contx/` and enforces the workflow rules from the design spec §9: query existing context before editing, append context in the same turn as code edits, handle renames/deletes through the MCP tools.

**Architecture:** The skill is a single Markdown file (`SKILL.md`) following Claude Code's skill format (frontmatter + body). It lives in the contx repo at `skills/contx/SKILL.md` and is *distributed* via a new CLI command `contx install-skill` that copies it to `~/.claude/skills/contx/`. No SessionStart auto-detection is implemented in this plan — the user can invoke the skill manually (`/contx` per Claude Code's skill convention) or wire SessionStart themselves. SessionStart auto-load is deferred to a follow-up plan because it requires modifying user-level settings, which we want to leave opt-in.

**Tech Stack:** Just file shuffling. Plain Python `shutil.copyfile`.

---

## File Structure

```
~/Desktop/xeno/contx/
├── skills/
│   └── contx/
│       └── SKILL.md          # NEW
├── contx/
│   ├── skill_install.py      # NEW: pure install/uninstall logic
│   └── cli.py                # MODIFY: add install-skill / uninstall-skill
└── tests/
    ├── test_skill_install.py # NEW
    └── test_cli.py           # MODIFY: 2 tests for new commands
```

---

## Task 1: Author the SKILL.md content

**Files:**
- Create: `skills/contx/SKILL.md`

- [ ] **Step 1: Write the skill file**

`~/Desktop/xeno/contx/skills/contx/SKILL.md`:

```markdown
---
name: contx
description: Use when editing code in any repo that has a .contx/ directory at the root. contx is "git for context" — every code change must be paired with a context entry explaining the WHY. This skill enforces the pairing: query before edit, append/rename/delete after.
---

# contx — git for context

You are working in a repo that uses `contx` to track *why* each file and function exists. When you edit code, you MUST also write a context entry describing the rationale.

## The contract

- **Before** editing any tracked source file, call `contx_query` to learn the existing intent.
- **Whenever** you call `Edit` or `Write` on a tracked source file, ALSO call `contx_append` in the same turn. No exceptions.
- **Whenever** you rename or move a symbol, call `contx_rename` *before* the `Edit` that performs the rename.
- **Whenever** you delete code, call `contx_delete` with a rationale.

The MCP tools (`contx_query`, `contx_append`, `contx_rename`, `contx_delete`, `contx_search`, `contx_audit`) are provided by the `contx-mcp` server. If they're not registered, tell the user to add this to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "contx": { "command": "contx-mcp" }
  }
}
```

## What to capture

Context entries record the **why**, never the **what**. The code itself shows what; the rationale captures decisions, constraints, business reasons, and incident links.

**Good rationales:**
- "Email-only login because Legal said phone OTP doesn't meet GDPR (ticket COMPLIANCE-412)."
- "Switched retry from exponential to linear — Auth0 rate-limited us during the May 12 incident."
- "Split SSO from auth.py because the file crossed 800 lines and ownership was unclear."

**Bad rationales (do not write these):**
- "This function authenticates the user." (That's WHAT the code does, not WHY.)
- "Refactored for clarity." (Too vague — what was unclear, and what does this fix?)
- "Added a try/except." (No reason given.)

If you don't know the rationale for a change, **ask the user** before writing the code. Never invent a rationale.

## Event types

| Event | When to use |
|---|---|
| `created` | First time a file or symbol exists. |
| `modified` | Behavior or contract changed. Skip for pure formatting/rename. |
| `renamed_in` / `renamed_out` | Symbol renamed in the same file (use `contx_rename` which writes both). |
| `moved_in` / `moved_out` | Symbol moved across files (use `contx_rename`). |
| `deleted` | Symbol/file removed (use `contx_delete`). |

## Tags

Use lowercase, hyphen-free or hyphenated tags. Suggested vocabulary:
`compliance`, `gdpr`, `security`, `performance`, `incident`, `refactor`, `business-decision`, `tech-debt`, `experiment`, `deprecation`.

## Workflow examples

### Editing an existing function

```
user: change the auth retry to be linear instead of exponential

assistant:
1. (call contx_query file="src/auth.py" symbol="retry")
   → existing intent: "exponential retry — picked for transient network errors"
2. (ask user) "I'd like to capture WHY linear is better here. What changed?"
   user: "Auth0 rate-limited us during the May incident — exponential made it worse."
3. (call contx_append file="src/auth.py" symbol="retry" event="modified"
       rationale="Switched to linear retry — Auth0 rate-limited us during the May incident; exponential amplified the burst."
       tags=["incident", "performance"])
4. (call Edit ...)
```

### Creating a new symbol

```
user: add a function to handle SSO callback

assistant:
(ask user) "What should the SSO callback do, and why does it live here vs in src/sso/?"
user: "...explains..."
1. (call contx_append file="src/auth.py" symbol="sso_callback" event="created"
       rationale="...captured from user explanation...")
2. (call Edit / Write ...)
```

### Renaming

```
user: rename `login_user` to `authenticate_user`

assistant:
1. (call contx_rename old_file="src/auth.py" old_symbol="login_user"
                     new_file="src/auth.py" new_symbol="authenticate_user"
                     rationale="renamed for clarity — login is overloaded across auth/session contexts")
2. (call Edit ... to apply the actual code rename)
```

## When the pre-commit hook blocks

The user's repo has a pre-commit hook (installed by `contx init`) that blocks commits when staged code lacks paired context. If they hit this, tell them to run:

```
contx draft --from-transcript
```

This opens an editor with rationales heuristically pre-filled from your recent conversation. They edit/save, and re-run `git commit`.

## When NOT to call contx tools

- Pure formatting changes (whitespace, import sort) — no context entry needed.
- Edits inside `.contx/` itself.
- Edits in directories matched by `.contx/config.json`'s `ignore` field (`node_modules/**`, `__tests__/**`, etc.).
- Test files following the project's test conventions (the `ignore` field usually handles this).

## Trust the user

If the user says "skip context for this one" or "don't write contx for this fix," respect that. Tell them they can bypass the hook once with `git commit --no-verify`, or set `"require_context_on_commit": false` in `.contx/config.json` for a global soft-warn mode.

The point of contx is to capture intent at the moment it exists — not to slow the user down. If they're certain it's not worth recording, that's their call.
```

- [ ] **Step 2: Commit**

```bash
cd ~/Desktop/xeno/contx && git add skills/contx/SKILL.md && git commit -m "feat(skill): author contx SKILL.md for Claude Code

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `skill_install.py` install/uninstall logic (TDD)

**Files:**
- Create: `contx/skill_install.py`
- Create: `tests/test_skill_install.py`

- [ ] **Step 1: Write tests**

```python
from pathlib import Path

from contx.skill_install import (
    install_skill,
    is_skill_installed,
    uninstall_skill,
)


def test_install_copies_skill_md(tmp_path: Path):
    # Source skill in a fake contx repo
    src_repo = tmp_path / "contx_repo"
    (src_repo / "skills" / "contx").mkdir(parents=True)
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("# fake skill\n")

    claude_home = tmp_path / "fake_claude"
    install_skill(src_repo=src_repo, claude_home=claude_home)

    dest = claude_home / "skills" / "contx" / "SKILL.md"
    assert dest.is_file()
    assert "# fake skill" in dest.read_text()


def test_install_is_idempotent(tmp_path: Path):
    src_repo = tmp_path / "contx_repo"
    (src_repo / "skills" / "contx").mkdir(parents=True)
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("v1\n")

    claude_home = tmp_path / "fake_claude"
    install_skill(src_repo=src_repo, claude_home=claude_home)

    # Update source and re-install
    (src_repo / "skills" / "contx" / "SKILL.md").write_text("v2\n")
    install_skill(src_repo=src_repo, claude_home=claude_home)

    dest = claude_home / "skills" / "contx" / "SKILL.md"
    assert dest.read_text() == "v2\n"


def test_is_skill_installed_reports_correctly(tmp_path: Path):
    claude_home = tmp_path / "fake_claude"
    assert is_skill_installed(claude_home=claude_home) is False
    (claude_home / "skills" / "contx").mkdir(parents=True)
    (claude_home / "skills" / "contx" / "SKILL.md").write_text("x")
    assert is_skill_installed(claude_home=claude_home) is True


def test_uninstall_removes_skill_dir(tmp_path: Path):
    claude_home = tmp_path / "fake_claude"
    (claude_home / "skills" / "contx").mkdir(parents=True)
    (claude_home / "skills" / "contx" / "SKILL.md").write_text("x")
    uninstall_skill(claude_home=claude_home)
    assert not (claude_home / "skills" / "contx").exists()


def test_install_missing_source_raises(tmp_path: Path):
    import pytest
    src_repo = tmp_path / "nope"
    claude_home = tmp_path / "fake_claude"
    with pytest.raises(FileNotFoundError):
        install_skill(src_repo=src_repo, claude_home=claude_home)
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement `contx/skill_install.py`**

```python
"""Install/uninstall the contx skill into a Claude Code skills directory."""

from __future__ import annotations

import shutil
from pathlib import Path

SKILL_NAME = "contx"
SKILL_FILE = "SKILL.md"


def _default_claude_home() -> Path:
    return Path.home() / ".claude"


def _source_skill_path(src_repo: Path) -> Path:
    return src_repo / "skills" / SKILL_NAME / SKILL_FILE


def _dest_skill_dir(claude_home: Path) -> Path:
    return claude_home / "skills" / SKILL_NAME


def install_skill(*, src_repo: Path, claude_home: Path | None = None) -> Path:
    """Copy skills/contx/SKILL.md from this repo to ~/.claude/skills/contx/.

    Overwrites any existing file (so re-running picks up updates).
    Returns the destination path.
    """
    claude_home = claude_home or _default_claude_home()
    src = _source_skill_path(src_repo)
    if not src.is_file():
        raise FileNotFoundError(f"Source skill not found: {src}")
    dest_dir = _dest_skill_dir(claude_home)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / SKILL_FILE
    shutil.copyfile(src, dest)
    return dest


def is_skill_installed(*, claude_home: Path | None = None) -> bool:
    claude_home = claude_home or _default_claude_home()
    return (_dest_skill_dir(claude_home) / SKILL_FILE).is_file()


def uninstall_skill(*, claude_home: Path | None = None) -> None:
    claude_home = claude_home or _default_claude_home()
    d = _dest_skill_dir(claude_home)
    if d.is_dir():
        shutil.rmtree(d)
```

- [ ] **Step 4: Verify 5 tests pass.**

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/skill_install.py tests/test_skill_install.py && git commit -m "feat(skill): add install/uninstall helpers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `contx install-skill` / `contx uninstall-skill` CLI

**Files:**
- Modify: `contx/cli.py`
- Modify: `tests/test_cli.py`

The tricky bit: the CLI needs to know where the source `skills/contx/SKILL.md` lives. Two options:
1. Locate it relative to the installed contx package (`Path(contx.__file__).parent.parent / "skills"`).
2. Ship the file inside the package and load via `importlib.resources`.

Option 1 works for editable installs (`pip install -e`); option 2 is more robust for `pip install` from a wheel but requires adding the skill to `package_data`. We use option 1 for MVP — `pip install -e` is what the project actually uses today. Add a note that wheel installs need a small adjustment (deferred).

- [ ] **Step 1: Append tests to tests/test_cli.py**

```python
def test_install_skill_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setenv("CONTX_CLAUDE_HOME", str(tmp_path / "fake_claude"))
    result = runner.invoke(app, ["install-skill"])
    assert result.exit_code == 0, result.output
    dest = tmp_path / "fake_claude" / "skills" / "contx" / "SKILL.md"
    assert dest.is_file()
    assert "contx — git for context" in dest.read_text()


def test_uninstall_skill_command(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_repo)
    monkeypatch.setenv("CONTX_CLAUDE_HOME", str(tmp_path / "fake_claude"))
    runner.invoke(app, ["install-skill"])
    result = runner.invoke(app, ["uninstall-skill"])
    assert result.exit_code == 0
    assert not (tmp_path / "fake_claude" / "skills" / "contx").exists()
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Add commands to contx/cli.py**

Add imports:
```python
from contx.skill_install import install_skill, uninstall_skill
```

Add commands:

```python
def _source_repo_root() -> Path:
    """Find the source repo root (containing skills/contx/SKILL.md).

    Strategy: walk up from contx/__file__ until we find a `skills/contx/SKILL.md`.
    Works for editable installs (`pip install -e .`).
    """
    import contx as _contx_pkg
    pkg_dir = Path(_contx_pkg.__file__).resolve().parent  # .../contx/contx/
    candidates = [pkg_dir.parent, pkg_dir.parent.parent]
    for c in candidates:
        if (c / "skills" / "contx" / "SKILL.md").is_file():
            return c
    raise FileNotFoundError(
        "Could not locate skills/contx/SKILL.md relative to the installed contx package. "
        "Re-install contx in editable mode (`pip install -e .`) from a checkout that includes skills/."
    )


def _claude_home() -> Path:
    override = os.environ.get("CONTX_CLAUDE_HOME")
    return Path(override) if override else Path.home() / ".claude"


@app.command(name="install-skill")
def install_skill_cmd() -> None:
    """Install the contx Claude Code skill into ~/.claude/skills/contx/."""
    src = _source_repo_root()
    home = _claude_home()
    dest = install_skill(src_repo=src, claude_home=home)
    typer.echo(f"installed contx skill to {dest}")


@app.command(name="uninstall-skill")
def uninstall_skill_cmd() -> None:
    """Remove the contx Claude Code skill from ~/.claude/skills/contx/."""
    home = _claude_home()
    uninstall_skill(claude_home=home)
    typer.echo(f"removed contx skill from {home / 'skills' / 'contx'}")
```

- [ ] **Step 4: Verify tests pass + full suite**

```bash
cd ~/Desktop/xeno/contx && source .venv/bin/activate && pytest -q
```

Expected: 129 PASS (122 + 5 from Task 2 + 2 from Task 3).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/xeno/contx && git add contx/cli.py tests/test_cli.py && git commit -m "feat(cli): add install-skill and uninstall-skill commands

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: README + Plan 4 docs

- [ ] **Step 1: Append "Claude Code skill" section to README** (right after the MCP section). Cover: what the skill does, how to install (`contx install-skill`), what the prompt rules enforce, how to uninstall.

- [ ] **Step 2: Commit** the README change and this plan file.

---

## What ships after Plan 4

- A `contx` Claude Code skill that the user installs once with `contx install-skill`.
- The skill prompts Claude to call `contx_query` before edits and `contx_append`/`contx_rename`/`contx_delete` after, paired with every `Edit`/`Write`.
- Combined with Plan 2's MCP server and Plan 3's hook, this is the complete enforcement loop: Claude knows what to do (Plan 4 skill), has the tools to do it (Plan 2 MCP), and git itself blocks if it doesn't (Plan 3 hook).

## Backlog item not in this plan

- **SessionStart auto-load**: detect `.contx/` in the project root via a SessionStart hook and auto-invoke the skill. Requires modifying user-level Claude Code settings, which we want to leave explicit for now.
