---
description: Print the full append-only log for a file or symbol
---

# /contx-log <ref>

1. Parse `<ref>` into file path + optional symbol.
2. Call `contx_query` to get the raw log.
3. For each entry in order, print:
   ```
   --- <timestamp> | <event> | <author> | <file>[::<symbol>]
   tags: <tags>     (only if non-empty)
   <rationale>
   <blank line>
   ```
4. If filtered by symbol, only show entries matching that symbol.
5. If no entries, print "no entries for <ref>".
