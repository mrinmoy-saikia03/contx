---
description: Initialize contx in the current git repo (interactive setup)
---

# /contx-init

You are setting up contx in the user's current git repository. Walk the user through these four questions in order, then perform the setup actions. Use `AskUserQuestion` for each.

## Question 1 — Pre-commit hook

Ask: "Install a pre-commit hook that blocks commits without paired context entries?"

Options:
- **Yes (recommended)** — every commit must include either a sidecar update or `--no-verify`
- **No** — track context but don't enforce at commit time

If the user picks **No**, skip Question 2 and use `require_context_on_commit = False`.

## Question 2 — Drift enforcement (only if hook is installed)

Ask: "When code is staged without a paired context entry, should the hook block the commit or just warn?"

Options:
- **Block (recommended)** — commit fails until context is added (or `--no-verify` is passed)
- **Warn-only** — commit succeeds, prints a warning

Save as `require_context_on_commit` (`True` for block, `False` for warn).

## Question 3 — Granularity

Ask: "What level of context do you want to track?"

Options:
- **Both file and symbol (recommended)** — file-level intent + per-function/class rationale
- **File only** — coarser, less to maintain
- **Symbol only** — finer, more entries

Save as `granularity` (`"both"` / `"file"` / `"symbol"`).

## Question 4 — Deployment manifests (multi-select)

Ask: "Which deployment manifests should contx track for drift?" (multiSelect: true)

Options:
- **Kubernetes** — adds `k8s/**/*.yaml` and `k8s/**/*.yml` with summarizer="kubernetes"
- **GitHub Actions** — adds `.github/workflows/*.yml` and `.github/workflows/*.yaml` with summarizer="github_actions"
- **docker-compose** — adds `docker-compose.yml`, `docker-compose.yaml`, `docker-compose.*.yml` with summarizer="docker_compose"
- **None** — track only source files

For each picked option, add the corresponding entries to the config's `tracked_paths` list.

## Perform the setup

Once all four answers are collected:

1. **Verify the repo is a git repo.** Run `git rev-parse --show-toplevel` to find the root. If it fails, tell the user this command needs a git repo and stop.

2. **Check if already initialized.** If `<repo>/.contx/config.json` exists, tell the user contx is already set up and ask whether to overwrite (default: no). On "no", exit. On "yes", proceed.

3. **Create `.contx/` and `config.json`.** Build the config dict with the user's answers. Defaults that don't come from prompts:
   - `languages`: `["py", "ts", "tsx", "js", "jsx", "go", "java", "kt", "rs", "rb", "php", "swift"]`
   - `ignore`: `["**/node_modules/**", "**/__tests__/**", "**/.venv/**", "**/venv/**", "**/dist/**", "**/build/**"]`
   - `require_rationale_on_create`: `true`
   - `extract_rationale_on_modify`: `true`
   - `tracked_paths`: derived from `languages` (one `{"glob": "**/*.<ext>", "kind": "source", "summarizer": null}` per language) plus any deploy entries from Question 4.

   Write JSON with `indent=2` plus trailing newline.

4. **Install the pre-commit hook** (only if Question 1 = Yes). Append the contx block to `<repo>/.git/hooks/pre-commit`, creating the file with `#!/bin/sh` shebang if it doesn't exist, marked between `# >>> contx pre-commit hook >>>` and `# <<< contx pre-commit hook <<<` sentinels. Make the hook executable (`chmod +x`). The block body:

   ```sh
   # Managed by contx — to remove, run /contx-uninstall-hook.
   if command -v contx >/dev/null 2>&1; then
       contx _precommit-check || exit 1
   fi
   ```

   Idempotence: if the sentinel is already in the file, don't append again.

5. **Write `.contxignore`** at the repo root if missing:

   ```
   # contx — paths to skip when tracking context.
   # Same syntax as .gitignore (subset).

   **/node_modules/**
   **/__tests__/**
   **/.venv/**
   **/venv/**
   **/dist/**
   **/build/**
   **/.contx/**
   ```

6. **Print a summary** of the choices:

   ```
   ✓ initialized contx at <repo>/.contx
   Settings:
     hook:        installed (block|warn) | skipped
     granularity: both | file | symbol
     deploy:      kubernetes, github-actions  (or "none")
   ```

7. **Suggest next step:** "Run `/contx-bootstrap` to generate v0 entries for the existing codebase, or just start editing — every change will pair with a contx_append from now on."

## Notes

- Do all file operations with the standard Write/Edit tools — no need to shell out except for `git rev-parse`.
- If any step fails, print the error and stop. Don't try to clean up partial state.
- Don't run `/contx-bootstrap` automatically — let the user choose.
