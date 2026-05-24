---
description: Read deployment YAMLs (k8s, GH Actions, docker-compose, terraform, helm) and write meaningful context entries
---

# /contx-deploy-summary

Walk the repo's deployment manifests and write contx entries that explain what each one **actually does for the system** — not just structural field extraction.

## Steps

1. Find deploy files via Glob:
   - `k8s/**/*.yaml`, `k8s/**/*.yml`
   - `.github/workflows/*.yml`, `.github/workflows/*.yaml`
   - `docker-compose*.yml`, `docker-compose*.yaml`
   - `terraform/**/*.tf`
   - `helm/**/values.yaml`, `helm/**/Chart.yaml`
   - `Dockerfile*`
2. For each file, call `contx_query` to check for an existing entry.
3. If missing or structural-only: read the file and write a meaningful entry that explains:
   - **What this deploys/builds/runs** in plain English
   - **Why these specific resource counts** (replicas, secrets, env vars) — infer from sibling files when possible
   - **What it connects to** (other services, external APIs, named secrets)
   - **Non-obvious constraints** (port choices, namespace conventions, image registries, version pins)
4. Call `contx_append`:
   - `kind=file`, `event=created` (or `modified`)
   - `tags=["deploy", "claude-generated", <"kubernetes"|"github-actions"|"docker-compose"|"terraform"|"helm"|"docker">]`
   - `related`: list source files / other deploy files referenced
5. If the YAML uses env vars, secrets, or external services, mention them by name in the rationale.

## What makes a deploy summary "meaningful"

- ✅ Good: "Deploys the auth-api service to prod with 3 replicas to handle EU+US+APAC regions in parallel. Pulls image from internal registry; reads OAUTH_CLIENT_SECRET from the 'auth-secrets' k8s Secret."
- ❌ Bad: "k8s Deployment: auth (ns=prod) — 3 replicas" *(mechanical extraction)*
- ❌ Bad: "Kubernetes deployment file." *(vague)*

## Output

A per-file mapping (file → 1-sentence summary of what was recorded). Final count of new vs updated entries.
