---
description: Improve, expand, or create a contx entry for a specific file or symbol
argument-hint: <file-or-symbol-ref>
---

# /contx-explain $ARGUMENTS

Refine the contx entry for `$ARGUMENTS` (e.g. `src/auth.py` or `src/auth.py::login`).

## Steps

1. Parse `$ARGUMENTS` into a file path and optional symbol.
2. Call `contx_query` (MCP) to see the existing entries.
3. Read the actual source file.
4. Compare what's stored vs what the code reveals:
   - **No entry yet** → write a fresh `created` entry.
   - **Shallow rationale** (auto-bootstrap, just a docstring, generic noun phrase) → write a `modified` entry that adds the missing *why*.
   - **Already solid** → ask the user what to add (a specific incident? a new constraint?).
5. If business context is unclear and you cannot infer it, ASK the user. Never fabricate.
6. Append via `contx_append` with `tags=["claude-generated"]` plus any contextual tags (compliance, gdpr, performance, incident, etc.).

## The meaning ladder

Move the rationale up:

- **L1**: "Function that does X" — *what*
- **L2**: "Function X is needed because the system requires X" — *circular*
- **L3**: "Function X handles edge case Y because Z" — *concrete cause*
- **L4**: "Function X exists because incident Y on date Z taught us we needed Z" — *incident-anchored*

Aim for L3 minimum. Reach L4 when you can.

## Output

Briefly: what was there before, what you added, and whether you needed user input for any part.
