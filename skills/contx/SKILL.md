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

A:
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

A:
(ask user) "What should the SSO callback do, and why does it live here vs in src/sso/?"
user: "...explains..."
1. (call contx_append file="src/auth.py" symbol="sso_callback" event="created"
       rationale="...captured from user explanation...")
2. (call Edit / Write ...)
```

### Renaming

```
user: rename `login_user` to `authenticate_user`

A:
1. (call contx_rename old_file="src/auth.py" old_symbol="login_user"
                     new_file="src/auth.py" new_symbol="authenticate_user"
                     rationale="renamed for clarity — login is overloaded across auth/session contexts")
2. (call Edit ... to apply the actual code rename)
```

## When the pre-commit hook blocks

The user's repo has a pre-commit hook (installed by `/contx-init`) that blocks commits when staged code lacks paired context. If they hit this, run `/contx-draft` right here in Claude Code.

`/contx-draft` reads the staged diff and your recent conversation, proposes a rationale for each drifted file, calls `contx_append` on accept, stages `.contx/`, and tells the user to re-run `git commit`.

## When NOT to call contx tools

- Pure formatting changes (whitespace, import sort) — no context entry needed.
- Edits inside `.contx/` itself.
- Edits in directories matched by `.contx/config.json`'s `ignore` field (`node_modules/**`, `__tests__/**`, etc.).
- Test files following the project's test conventions (the `ignore` field usually handles this).

## Trust the user

If the user says "skip context for this one" or "don't write contx for this fix," respect that. Tell them they can bypass the hook once with `git commit --no-verify`, or set `"require_context_on_commit": false` in `.contx/config.json` for a global soft-warn mode. To remove the hook entirely, run `/contx-uninstall-hook`.

The point of contx is to capture intent at the moment it exists — not to slow the user down. If they're certain it's not worth recording, that's their call.
