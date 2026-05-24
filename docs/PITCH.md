# contx — why I built this

## The problem

Code answers *what*, never *why*.

`git blame` tells me who touched a line and when. A code-review graph tells me what function calls what. Neither tells me **why** the retry is linear instead of exponential, **why** SSO got split out of `auth.py` in March, or **why** that defensive `try/except` exists at all.

That kind of context lives in Slack threads, in decision docs nobody updates, and mostly in the heads of senior engineers. It evaporates when people leave. New hires re-litigate decisions from scratch. AI coding agents read the code and confidently change it — without knowing the May incident that put that exact line there.

## What I built

contx is "git for context." Every file and every function gets an append-only log of *why* it exists, version-controlled alongside the code in a `.contx/` directory. Same idea as `.github/` or `__tests__/` — it travels with the repo.

The interesting bit: the entries aren't written by humans typing into a markdown file. They're written by **AI coding agents** as they edit, through an MCP server I wrote. When Claude (or Cursor, or any MCP-capable agent) is told "switch the retry to linear," it calls `contx_append` in the same turn as its `Edit`, with a rationale captured from the conversation. A pre-commit hook blocks the commit if code changed without a paired context entry, so the pairing stays honest.

When a new developer clones the repo, they get the code *and* the intent map. They can `contx serve` to browse it locally, or just ask Claude "why does `User.authenticate` exist?" and get a real answer pulled from the recorded entries — not a guess based on reading the code.

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

This is a vibe-coded weekend project. ~70 commits, ~240 tests, end-to-end working — but rough at the edges and **not production-tested**. The Python AST walker only handles Python (TypeScript/Go are stubs). The transcript miner uses sentence-proximity heuristics, not an LLM. Diagram generation is delegated to Claude via slash commands rather than baked into deterministic code. There's no team mode, no rationale conflict resolution, no rationale auto-summarization.

## What's next (rough order)

1. **More language parsers** — TypeScript and Go AST walkers so non-Python repos get a real baseline.
2. **LLM-backed bootstrap** — replace heuristic transcript mining with a proper Claude API call when `ANTHROPIC_API_KEY` is set; the heuristics are okay-not-great.
3. **Team mode** — when two devs append conflicting rationales for the same symbol on different branches, surface the conflict at merge time instead of silently concatenating.
4. **Better diagrams** — symbol-level and deployment-topology types are wired in but produce flat node graphs; want grouped/swimlane layouts.
5. **Rationale summarization** — after 50+ entries on one file, the fold view gets noisy; have Claude periodically distill the log into a clean summary.
6. **IDE plugins** — VS Code and JetBrains: inline "why is this here?" hover tooltips backed by the sidecar.
7. **Plugin ecosystem** — the MCP-tool surface is stable enough that other tools (linters, security scanners, dependency bots) could read/write contx entries too.

If you try it and it breaks or feels wrong, let me know.
