# contx — why I built this

## The problem

Code answers *what*, never *why*.

`git blame` tells me who touched a line and when. A code-review graph tells me what function calls what. Neither tells me **why** the retry is linear instead of exponential, **why** SSO got split out of `auth.py` in March, or **why** that defensive `try/except` exists at all.

That kind of context lives in Slack threads, in decision docs nobody updates, and mostly in the heads of senior engineers. It evaporates when people leave. New hires re-litigate decisions from scratch. AI coding agents read the code and confidently change it — without knowing the May incident that put that exact line there.

### Three real examples

**1. The workflow change three weeks ago.** Last sprint the deployment workflow changed from a single-stage rollout to a canary → wait → full-rollout sequence. The reason — a bad config push took down checkout for 12 minutes on a Tuesday — is in a Slack thread that scrolled away two weeks ago. Anyone reading `.github/workflows/deploy.yml` today sees the new shape but not the incident that forced it. A junior dev "simplifying" the workflow next month will undo the canary stage and re-enable the same failure mode.

**2. The retry policy nobody touches.** The retry on the Auth0 client was switched from exponential to linear last quarter. The reason: exponential amplified a rate-limit storm into a 40-minute outage. Six months from now an engineer doing a "clean up the retry helpers" PR will revert it to exponential because every guide on the internet says exponential is better — and re-create the original outage.

**3. The split table.** The `user_settings` table was broken up into per-feature tables in March because the JSONB blob was hitting PostgreSQL TOAST limits and tail latency on the settings page got bad. Without that context, the obvious "consolidate these scattered tables back into one" refactor next year reintroduces the same problem.

In every case the *code* is correct. The *intent* is what gets lost — and the cost of losing it is paying for the same lesson twice.

### Why now

Engineers have always tried to capture this — RFCs, design docs, "WHY.md" files, spec-driven development, comments. Those help, but they all share the same fragility: nothing forces them to stay current with the code. They live one layer away from the line that changed, and they drift the moment the deadline pressure hits.

AI coding agents change the calculus. They're already in the conversation where the rationale is being spoken aloud. They're already calling `Edit` and `Write`. Pairing every code change with a one-line "why" is now a tool call away — if the agent is told to do it.

## What I built

contx is "git for context." Every file and every function gets an append-only log of *why* it exists, version-controlled alongside the code in a `.contx/` directory. Same idea as `.github/` or `__tests__/` — it travels with the repo.

The interesting bit: the entries aren't written by humans typing into a markdown file. They're written by **AI coding agents** as they edit, through an MCP server. When Claude (or Cursor, or any MCP-capable agent) is told "switch the retry to linear," it calls `contx_append` in the same turn as its `Edit`, with a rationale captured from the conversation. A pre-commit hook blocks the commit if code changed without a paired context entry, so the pairing stays honest.

When a new developer clones the repo, they get the code *and* the intent map. They can `contx serve` to browse it locally, or just ask Claude "why does `User.authenticate` exist?" and get a real answer pulled from the recorded entries — not a guess based on reading the code.

## The slash commands (where the intelligence lives)

The MCP tools (`contx_append`, `contx_query`, etc.) are low-level — they're how the agent writes to the store. The *interesting* workflows are four Claude Code slash commands that orchestrate the agent's intelligence:

| Command | What it does | Why it matters |
|---|---|---|
| `/contx-bootstrap` | Reads the whole codebase, reasons about why each file/function exists, and writes meaningful v0 entries via `contx_append`. | Brownfield repos get an instant baseline. Without this, every entry has to be earned through future edits — onboarding takes years. |
| `/contx-explain <path>` | Improves or expands an existing entry's rationale by re-reading the code and the conversation. Good when the v0 was thin and you've since learned more. | Context refines over time the way the code does. Entries get sharper, not staler. |
| `/contx-diagram <type>` | Reads + reasons about the architecture and generates a real `.drawio` file (files / symbols / deployment topology). | A force-directed graph algorithm gives you a noise hairball. Claude gives you "here's what actually matters and how the pieces connect," because it understands the code, not just the import graph. |
| `/contx-deploy-summary` | Reads deployment YAMLs (k8s, GH Actions, docker-compose, Terraform) and writes *meaningful* context for them — not a structural dump of `kind:` and `name:`. | "Why is replicas=3? Why does this workflow only run on tags? What does this Helm value control?" — the things the YAML itself can't tell you. |

### The token-cost shape

`/contx-bootstrap` on a real repo is **the only expensive call** — it reads many files and writes one entry per non-trivial symbol. Expect 100k–500k tokens for a medium repo. **You pay this once.**

Every edit after that is cheap: the rationale is already in the conversation, the agent calls `contx_append` once with a one-line entry. Marginal cost per code change is negligible.

Compare that to the alternative: every onboarding-driven re-derivation of intent, every "wait why is this here" Slack thread, every refactor that re-creates an old bug — repeated forever, across every engineer who touches the codebase. The first-run bootstrap pays itself back inside the first sprint.

## The web viewer (`contx serve`)

Slash commands are how the agent writes context. **The web viewer is how humans read it.**

```bash
contx serve              # localhost:4242
contx serve --port 8080  # any port (auto-falls-back to the next 9 if 4242 is taken)
```

A local, read-only, server-rendered web UI over the `.contx/` tree. No login, no edits, no JS bundle, no build step — just plain HTML with a sprinkle of htmx so search feels live. Page weight is a few KB.

### What's in it

| View | What it shows |
|---|---|
| `/` — **file tree** | Every source file that has at least one context entry. Click any file to drill in. Grouped by top-level directory so it stays readable on big repos. |
| `/file/<path>` — **file view** | The folded "current" file-level intent at the top, followed by a list of every symbol in the file with its one-line rationale. Then the full append-only log of every entry on that file, in order — author, timestamp, event type (`created` / `modified` / `renamed_in` / `moved_out` / `deleted` / …), tags, and rationale. Each entry visually distinct so you can scan history quickly. |
| `/symbol/<file>::<symbol>` — **symbol view** | Same shape as the file view but zoomed to one function/class. Latest rationale is the headline; everything that came before it is the timeline. Renames and moves show their backlinks so you can follow a symbol across files when it was refactored. |
| `/search?q=…` — **full-text search** | Substring search across every rationale and every tag in the repo. Live-updates via htmx as you type. Tag any entry with `incident`, `compliance`, `gdpr`, `performance` and you can pull every related decision out in one query. |
| `/timeline` — **timeline** | The most recent entries across the entire repo, newest first. Like a `git log` for *intent* — see what was decided this week, who decided it, and why. Great for sprint retros and "what changed in this area lately." |

### Why a web view instead of a CLI-only tool

The CLI (`contx show`, `contx log`) is fine for one symbol at a time. The web viewer is for **navigation and discovery** — the cases where you don't yet know what you're looking for. Browsing a fresh codebase, prepping for an architecture review, doing an incident post-mortem and wanting to find every entry tagged `incident` for that subsystem, onboarding a new hire and just letting them poke around. The page weight is small enough you could ship it to a tablet on a kanban board if you wanted.

It's deliberately **read-only**. Writes happen one way: through AI agents (via MCP) or through the CLI. The viewer just renders. That separation means there's no auth layer to build, no audit trail to maintain, and no risk of a stale browser tab silently corrupting state.

### Why this isn't already a thing

A few teams already do something like this: spec-first development, RFCs, "WHY.md" in critical directories. They work for the things they cover. The reason that approach hasn't generalized: it costs human discipline. The doc lives one layer away from the line. There's no enforcement. Two refactors later it's wrong.

contx puts the rationale on the same commit as the code that needs it, written by the agent that's making the change, blocked by a hook if you skip. The discipline is enforced by tooling, not by a person remembering.

## The bigger play

The same way every dev who clones the repo has the same code, they now have the same **context**. That's a unified source of truth for *intent* that's been missing from version control.

Once that exists, you can pipe it into anything: smarter code-review bots, onboarding generators, refactoring agents that won't undo decisions made for incidents you weren't there for, deployment runbooks that know *why* the rate limit is 30/min not 60. Today's AI agents have to re-derive intent every time. With contx, intent becomes a first-class artifact alongside source.

## How to install

```bash
git clone <repo>
cd contx
./install.sh --all
contx init
```

That's it. Full step-by-step (Python prereqs, pipx, OS-specific) is in the README.

Once installed:
- `contx init` in any repo — interactive setup, installs the pre-commit hook, asks what deployment manifests to track.
- Open the repo in Claude Code — the skill activates, MCP tools are available, the agent starts pairing every edit with a context entry.
- `contx serve` to browse the intent map at `localhost:4242`.

## Honest disclaimer

This is a vibe-coded weekend project. ~75 commits, ~240 tests, end-to-end working — but rough at the edges and **not production-tested**. The transcript miner (used only as a fallback when Claude isn't running) is a sentence-proximity heuristic, not great. The Python AST walker that ships in the package only handles Python. There's no team mode, no rationale conflict resolution, no rationale auto-summarization, no IDE plugin.

The architecture also has a real open question: today there are two layers doing similar work — slash commands (Claude-driven, smart) and a small Python CLI/MCP layer (deterministic, mechanical). The slash commands are clearly the right place for the intelligence; the CLI is the right place for `serve` and the pre-commit hook. The middle is up for debate — see "next phases" below.

## What's next (rough order)

1. **Collapse the Python layer into slash commands.** Today there's a CLI (`init`, `append`, `show`, `log`, `draft`, …) and an MCP server alongside the slash commands. A lot of that duplicates work the agent could do directly. The plan is to keep only what *has* to be Python (`contx serve` for the web UI, the pre-commit hook as a tiny shell script) and move everything else into slash commands. `/contx-init` would create the dir + hook + config by running shell from inside Claude. Smaller surface, less to install, more honest about where the intelligence lives.
2. **Team mode** — when two devs append conflicting rationales for the same symbol on different branches, surface the conflict at merge time instead of silently concatenating.
3. **Rationale summarization** — after 50+ entries on one file, the fold view gets noisy. Have Claude periodically distill the log into a clean summary (with the raw history still preserved for audit).
4. **Better diagrams** — `/contx-diagram` already delegates to Claude, but the outputs would benefit from a richer template (grouped clusters, deployment swimlanes, color by entry-tag).
5. **IDE plugins** — VS Code and JetBrains: inline "why is this here?" hover tooltips backed by the sidecar. Closes the loop for devs who aren't in Claude Code all day.
6. **Other MCP hosts** — Cursor, Windsurf, Codex. The MCP server already speaks the standard protocol; mostly a docs+testing pass.
7. **Plugin ecosystem** — once collapse (#1) lands, the entry-write API is stable enough for other tools (linters, security scanners, dependency bots) to drop their own context entries.

If you try it and it breaks or feels wrong, let me know.
