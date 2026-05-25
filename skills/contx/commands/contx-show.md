---
description: Print the folded current intent for a file or symbol
---

# /contx-show <ref>

`<ref>` is either `path/to/file.py` (file-level) or `path/to/file.py::Class.method` (symbol-level).

1. Call `contx_query` with the parsed file and optional symbol.
2. If the result has `file_intent` (file-level query): print the file path as a header, then the intent, then the list of symbols (each with its current rationale).
3. If the result has `symbol_intent` (symbol query): print `<file>::<symbol>` as the header, then the symbol's current rationale.
4. If nothing is recorded for the ref, print "no context for <ref>".

Keep the output compact. Use plain text, not markdown formatting (no `#` headers in the output — the user wants to read it in a terminal).
