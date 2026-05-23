# contx — Design: Bootstrap, Deployment Awareness, Diagrams

**Date:** 2026-05-23
**Status:** Design — awaiting user approval before implementation planning

This spec covers **three independent sub-projects** that together address one user complaint: `contx init` is too thin. Today it just creates a directory; running it on a brownfield repo leaves you at zero context, and nothing in contx yet visualizes how a system fits together. The three sub-projects:

1. **Bootstrap** — `contx init` seeds entries from existing git history + source-code AST.
2. **Deployment-manifest awareness** — YAML manifests (k8s, GitHub Actions, docker-compose) participate in tracking and get auto-summarized.
3. **Diagrams** — render the intent graph as draw.io files committed alongside the entries.

Each sub-project ships independently as its own Plan (B2, B3, B4). Order matters: bootstrap fills the entries, deployment awareness enriches them, diagrams visualize what's there.

---

## 1. Bootstrap (Plan B2)

### Problem

On a brownfield repo, `contx init` writes one config file and walks away. Hundreds of existing functions have no context. Users either type entries by hand for weeks or never bother — and contx fails to bootstrap network effects in repos that need it most.

### Solution

`contx init` (and a new standalone `contx bootstrap` for already-initialized repos) writes a baseline of entries derived from two sources, all tagged `agent="audit"` so they're clearly auto-generated and downstream users know to refine them:

**Source A — Source-code AST (the "what exists today" baseline):**
- Walk every file matching `cfg.languages` and not ignored by `.contxignore`.
- For each language, use a minimal parser to extract top-level functions and classes:
  - **Python (MVP)**: `ast.parse()` → walk `FunctionDef`, `AsyncFunctionDef`, `ClassDef` at module top level and at class top level (for methods). Pull the docstring if present.
  - **TypeScript / JavaScript / Go / Java / Rust / etc.**: stub now, real implementation deferred. Emit one file-level "TODO: language not yet supported" entry per file so the gap is visible.
- For each symbol, write one entry: `event=created`, `kind=symbol`, `symbol=<dotted path>`, `rationale=<docstring or "auto-bootstrapped — please fill in">`, `tags=["bootstrap"]`, `agent="audit"`.
- For each tracked file, write one file-level entry: `rationale="<first paragraph of module docstring or 'auto-bootstrapped — please fill in'>"`, `tags=["bootstrap"]`, `agent="audit"`.

**Source B — Smart-filtered git history (the "how we got here" log):**
- Walk `git log --all --reverse --name-only --pretty=format:'%H%n%an%n%aI%n%s%n%b%n---END---'` and parse it.
- For each commit, group the changed files. For each tracked file:
  - Skip commits matching the noise heuristic (see §1.3 below).
  - Skip files where the commit's `name-only` line indicates a delete (already handled by `contx_delete` semantically).
  - Write one entry per (file, commit): `event=modified`, `kind=file`, `rationale="<commit subject>: <commit body first paragraph>"`, `tags=["bootstrap", "git-history"]`, `agent="audit"`, `author=<commit author email>`, `timestamp=<commit author date>`, `related=[]`.
  - The ULID is generated from the commit timestamp so entries sort chronologically across runs.
- The first commit touching each file gets `event=created` instead of `event=modified`.

### 1.3 Noise heuristic

Skip the commit if **any** of these match:
- Commit subject (case-insensitive) starts with: `wip`, `fix typo`, `typo`, `format`, `fmt`, `lint`, `merge`, `bump`, `chore(deps)`, `version`.
- Commit subject is exactly `init` or `initial commit` (handled separately — every file's first appearance becomes its `created` entry regardless of message).
- Commit changes fewer than `cfg.bootstrap_min_diff_lines` lines (default 5) in the file. Computed via `git log --numstat`.
- Commit is a merge commit with no diff against either parent.

The heuristic lives in `contx/bootstrap_filter.py` so it's testable and tunable.

### 1.4 CLI

```
contx init --bootstrap          # init + run full bootstrap (default)
contx init --no-bootstrap       # original behavior — config + .contxignore only
contx init --bootstrap-ast      # init + bootstrap AST only (skip git history)
contx init --bootstrap-git      # init + bootstrap git history only (skip AST)

contx bootstrap [--ast] [--git] [--since <ref>] [--dry-run]   # run on an already-init'd repo
```

`--dry-run` prints what would be written without writing anything. Useful for big repos before committing to a long write.

### 1.5 Output volume control

Big repos can generate tens of thousands of entries. To keep this manageable:
- `cfg.bootstrap_max_commits` (default `1000`) — cap on total commits considered.
- `cfg.bootstrap_min_diff_lines` (default `5`) — see noise heuristic.
- `--since <ref>` lets the user start the history walk at a specific tag/commit (e.g. `--since v1.0.0`) so they can ignore deep history.

If a bootstrap would produce more than `bootstrap_max_commits * 5` entries the CLI confirms before writing (or proceeds without confirmation under `--yes`).

### 1.6 Idempotence

`contx bootstrap` is **not** idempotent in the strict sense (re-running would double-write entries). Two guardrails:
- The CLI refuses to run if any sidecar already contains entries with `tags=["bootstrap"]` unless `--force` is passed.
- `--force` first appends one synthetic entry `event=modified, rationale="re-bootstrap; previous bootstrap entries superseded", agent="audit"` so the audit trail is preserved, then proceeds.

### 1.7 Module structure

```
contx/
├── bootstrap/
│   ├── __init__.py
│   ├── ast_python.py         # Python AST walker → entries
│   ├── ast_dispatch.py       # Language → walker dispatch (stubs for non-Python)
│   ├── git_history.py        # git log walker → entries (uses bootstrap_filter)
│   └── bootstrap_filter.py   # noise heuristic
└── cli.py                    # MODIFY: --bootstrap flags + standalone command
```

---

## 2. Deployment-manifest awareness (Plan B3)

### Problem

The contx data model only cares about source files. But every real deploy is governed by YAML — k8s manifests, GitHub Actions workflows, docker-compose, Helm values, Terraform HCL. Today these:
- Are not tracked by the pre-commit hook (no enforcement on deploy changes).
- Are not summarized for new devs (you read raw YAML to understand prod).
- Don't enrich diagrams (no service topology data).

### Solution

#### 2.1 Track manifests in the hook (Source A behavior)

Extend `cfg.languages` to a richer `cfg.tracked_paths` model — backward compatible with existing extension lists. New schema:

```json
{
  "languages": ["py", "ts", ...],
  "tracked_paths": [
    {"glob": "**/*.py", "kind": "source"},
    {"glob": ".github/workflows/*.{yml,yaml}", "kind": "deploy", "summarizer": "github_actions"},
    {"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": "kubernetes"},
    {"glob": "docker-compose*.{yml,yaml}", "kind": "deploy", "summarizer": "docker_compose"}
  ]
}
```

For backward compat: at load time, `cfg.languages` is automatically projected into `tracked_paths` entries with `kind="source"` and `summarizer=null`.

`contx_audit` and the pre-commit hook treat every tracked path identically for drift purposes — a changed `k8s/auth.yaml` requires a paired sidecar entry just like a changed `src/auth.py`.

#### 2.2 Auto-summarize known manifests (Source B behavior)

A new `contx/summarizers/` package contains per-format summarizer functions. Each one:
- Takes a parsed YAML/HCL object.
- Returns one or more `Entry`-shaped dicts (file-level and/or symbol-level).

MVP summarizers (real implementations):
- **`kubernetes`**: emit one file-level entry summarizing each top-level resource (Deployment, Service, Ingress, etc.). Fields surfaced: `kind`, `metadata.name`, `metadata.namespace`, `spec.replicas`, container images, exposed ports.
- **`github_actions`**: file-level entry naming the workflow + on-triggers + job count + secrets referenced.
- **`docker_compose`**: file-level entry listing services, their images, and their `depends_on` links.

Each summarizer entry is tagged `["deploy", "auto-summary", "<summarizer-name>"]` and `agent="audit"` so users know it's machine-derived and can refine or replace it.

#### 2.3 When summarizers run

- **At `contx init --bootstrap`**: as part of the bootstrap pass (Plan B2).
- **At a dedicated `contx bootstrap-deploy` command** for repos that initialized before this feature shipped.
- **Optionally at audit time**: `contx_audit --summarize-new` writes summaries for any tracked deploy file that has no sidecar yet. Off by default — drift detection is enough for the hot path.

#### 2.4 Module structure

```
contx/
├── summarizers/
│   ├── __init__.py
│   ├── registry.py           # name → summarizer function
│   ├── kubernetes.py
│   ├── github_actions.py
│   └── docker_compose.py
├── config.py                 # MODIFY: tracked_paths schema + backward-compat shim
└── cli.py                    # MODIFY: bootstrap-deploy subcommand
```

---

## 3. Diagrams (Plan B4)

### Problem

You can read `contx show` for one file at a time, but there's no way to see the whole intent map at a glance. Engineers want a picture they can paste into a PR review or hand to a new team member.

### Solution

A new `contx diagram` command that renders the intent graph to draw.io XML, stored in `.contx/diagrams/<name>.drawio` so the diagram is committed to git and travels with the repo.

#### 3.1 Diagram type for MVP: file-map

Each tracked file is a node. Edges come from `related` backlinks in entries (set by `contx_rename`, `contx_move`, or manual `--related` flags). Node annotations:
- File path (as the label).
- Folded `file_intent` truncated to ~80 chars (as the tooltip / sub-label).
- Color band by top-level directory (`src/`, `tests/`, `k8s/`, etc.) so visual clustering is automatic.

#### 3.2 Output format

draw.io XML (`.drawio` file). The format is well-documented mxGraph XML and supported by:
- Web app at https://app.diagrams.net (paste-and-go).
- VS Code Draw.io Integration extension.
- The macOS/Windows desktop app.

We emit a single `<mxfile>` with one `<diagram>` page containing the graph. Layout: a simple force-directed coordinate algorithm in pure Python (no external graphviz dependency), good enough for graphs up to a few hundred nodes.

#### 3.3 CLI

```
contx diagram                              # type=files, out=.contx/diagrams/files.drawio
contx diagram --type files
contx diagram --type files --out custom.drawio
contx diagram --type symbols   # placeholder — emits "not implemented in MVP" error
contx diagram --type deploy    # placeholder — same
```

`--type symbols` and `--type deploy` are deferred to future plans (B4b, B4c). Reserving the CLI flags now keeps backward compat when we add them.

#### 3.4 What's in scope for B4 MVP

| In scope | Out of scope |
|---|---|
| `contx diagram --type files` | Symbol call graphs |
| draw.io XML output | Mermaid / Graphviz output |
| Pure-Python force-directed layout | LLM-suggested layouts |
| Color by top-level directory | Custom theming / user CSS |
| Tooltip = folded file intent | Click-through to web UI (later if web UI runs concurrently) |
| `.contx/diagrams/files.drawio` | Auto-regenerate on every commit (manual command for MVP) |

#### 3.5 Module structure

```
contx/
├── diagram/
│   ├── __init__.py
│   ├── graph.py              # build node/edge graph from sidecars
│   ├── layout.py             # simple force-directed positioning
│   └── drawio.py             # emit mxGraph XML
└── cli.py                    # MODIFY: `contx diagram` command
```

---

## Cross-cutting concerns

### Backward compatibility

- Existing `.contx/config.json` files load unchanged (the new `tracked_paths` field is optional; `languages` projects into it automatically).
- Existing sidecars remain valid — Plan B2 adds new entries with `agent="audit"`, `tags=["bootstrap"]`. They never modify existing entries.
- Existing CLI flags continue to work. `contx init` gains `--bootstrap` (defaulted on) and `--no-bootstrap` (opt-out).

### Testing

- Each summarizer (Plan B3) has unit tests against canonical YAML fixtures.
- Python AST walker (Plan B2) is tested against a small fixture project.
- Git history walker is tested against an ephemeral repo fixture (uses the existing `tmp_repo` conftest fixture, populated with synthetic commits).
- Diagram emitter (Plan B4) is tested by parsing its own output and asserting node/edge counts (without invoking draw.io).
- All three sub-projects target the same 80%+ coverage bar as Plans 1-5.

### Performance

- Bootstrap on a 1000-commit, 500-file repo should finish in under 30 seconds end-to-end (rough budget: 20s git log walk, 5s AST parse, 5s sidecar writes).
- Diagram render on a 200-node graph should finish in under 2 seconds.

If we hit these bounds, both subsystems should report progress (e.g., "bootstrap: 312/1000 commits processed…") so users don't think it hung.

### Out of scope (deferred, but possible later)

- LLM-based rationale extraction during bootstrap. The smart-filter heuristic is the MVP; an LLM pass could replace `"<commit subject>"` with a paragraph synthesizing what changed and why. Add when there's a budget for it.
- Cross-repo links in diagrams. A future `contx diagram --multi-repo` could read multiple `.contx/` trees and draw inter-repo dependencies. Not in MVP.
- Web-UI integration of diagrams (rendering the `.drawio` inline in `contx serve`). Easy to add later — the file is already in the repo, so a route `/diagram/<name>.drawio` can serve it.

---

## Plan ordering

- **Plan B2** (Bootstrap) ships first — independently useful, no dependency on others.
- **Plan B3** (Deployment awareness) ships second — depends on B2's bootstrap framework only for the auto-summarize hook; the tracked-paths config and pre-commit integration are independent and could ship first.
- **Plan B4** (Diagrams) ships third — once entries are populated by B2+B3, the diagram has real data to render. Could be done before B3 if needed.

---

## Open questions for the user

None blocking. Defaults chosen for everything. If anything in the design surprises you, flag it before the plan files are written.
