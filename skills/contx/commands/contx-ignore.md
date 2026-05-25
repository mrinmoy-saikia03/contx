---
description: Append a gitignore-style pattern to .contxignore
---

# /contx-ignore <pattern>

1. Find the repo root via `git rev-parse --show-toplevel`.
2. Read `<repo>/.contxignore` if it exists.
3. If the pattern is already present (exact match, ignoring leading/trailing whitespace), tell the user "already present" and stop.
4. Otherwise append the pattern (with a leading newline if the file doesn't end in one) and tell the user the pattern was added.
