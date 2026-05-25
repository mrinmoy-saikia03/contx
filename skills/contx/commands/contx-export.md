---
description: Export the repo's intent map as a human-readable Markdown document
---

# /contx-export [--out PATH]

Default output: `<repo>/.contx/INTENT.md`.

1. Find the repo root.
2. Walk `<repo>/.contx/` looking for `*.jsonl` files (skip `config.json`).
3. For each sidecar, call `contx_query` for the corresponding source file.
4. Build a Markdown document:
   ```
   # contx intent map

   ## <source path>
   <file_intent if present>

   ### <symbol>
   <symbol intent>

   ### <symbol>
   <symbol intent>

   ## <next source path>
   ...
   ```
5. Write to the output path. Print "wrote <path>".

Only include sidecars that actually have entries. Skip empty ones.
