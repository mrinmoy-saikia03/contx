---
description: Interactively add context entries for drifted files (when pre-commit hook blocked you)
---

# /contx-draft

When the pre-commit hook blocked a commit, this command helps add the missing entries.

1. Run `contx _precommit-check` and capture its output. If the exit code is 0, tell the user "no drift — nothing to draft" and stop.
2. Parse the list of drifted files from the output (lines starting with `  - `).
3. For each drifted file:
   - Read the staged diff for that file (`git diff --cached -- <file>`).
   - Read what the user has been discussing in this Claude session about that file.
   - Propose a rationale (one or two sentences) that captures the *why* of the change — not the *what*.
   - Ask the user: "For `<file>`: I'll record `<rationale>`. Edit / accept / skip?"
   - On accept, call `contx_append` with `file=<path>`, `event="modified"`, `rationale=<final>`, and any tags that fit (`incident`, `compliance`, `security`, `performance`, etc.).
   - On edit, the user provides the corrected rationale.
   - On skip, move on.
4. After all files are handled, stage `.contx/` (`git add .contx/`) and tell the user to re-run `git commit`.

Tone: terse. Don't lecture. Don't ask "are you sure?" repeatedly. One pass through the files.
