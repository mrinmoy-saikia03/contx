---
description: Generate meaningful v0 context entries by reading the repo (uses Claude's understanding, not mechanical AST)
argument-hint: [path-glob, default: tracked-language files]
---

# /contx-bootstrap $ARGUMENTS

You are bootstrapping contx for this repo. Your job: walk the codebase and write **meaningful** v0 context entries that explain *why* each significant file/symbol exists — not what it does.

## Steps

1. Call the MCP tool `contx_audit` to find untracked files.
2. If `$ARGUMENTS` is given, restrict the file list to that glob; otherwise use all untracked tracked-language files.
3. For each candidate file:
   a. Read the file.
   b. Decide if it's interesting — business logic, glue, integration points, decision-bearing. Skip pure boilerplate, generated code, vendored deps.
   c. If interesting, call `contx_append`:
      - `file=<path>`, `event=created`
      - `rationale=`: 1–2 sentences explaining the *purpose* in business or architectural terms
      - `tags=["bootstrap", "claude-generated"]`
   d. For top-level functions or classes that embody a clear decision (auth, validation, integrations, business rules), also append a symbol-level entry.
4. Skip files that already have contx entries.
5. Every 20 files, summarize progress to the user and ask whether to continue.

## What makes a rationale "meaningful"

- ✅ Good: "Owns the OAuth callback flow because we need to handle Google-specific edge cases that the auth0 SDK doesn't cover."
- ❌ Bad: "Module for authentication." *(what, not why)*
- ❌ Bad: "Auto-bootstrapped — please fill in." *(surrender)*

If you genuinely cannot infer the *why* from code + structure, tag the entry with `pending-rationale` and write what you *can* infer. Do not pretend.

## Constraints

- Never invent business context (GDPR, specific incidents, names of people) — only state what's evident from the code or surrounding files.
- File-level entries only for files with a unique role. Skip config files, lock files, style files.
- Symbol-level entries only for decision-bearing symbols — not every getter, setter, or trivial helper.
- Pause after every 20 entries to let the user steer.

## Output

A final report:
- Files entered, files skipped (and why for the skipped).
- 3–5 sample rationales.
- A list of files tagged `pending-rationale` so the user knows what needs human input.
