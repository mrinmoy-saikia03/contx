---
description: Remove the contx pre-commit hook block (preserves any other content in the hook)
---

# /contx-uninstall-hook

1. Find `<repo>/.git/hooks/pre-commit`. If missing, print "no hook installed" and stop.
2. Strip the block between `# >>> contx pre-commit hook >>>` and `# <<< contx pre-commit hook <<<` (inclusive of the sentinels).
3. If what remains is empty or just the `#!/bin/sh` shebang, delete the file entirely.
4. Otherwise rewrite the file with the contx block removed.
5. Print "removed contx pre-commit hook block".
