# LinkedIn post — contx

---

Spent the weekend building something I've wanted for a while: **git, but for context**.

`git blame` tells you *who* and *when*. Code-review graphs tell you *what depends on what*. Neither tells you the actual **why** — why retry is linear instead of exponential, why SSO got split out of auth, why that try/except exists at all.

That knowledge usually lives in Slack threads, half-updated decision docs, and the heads of two senior engineers. It walks out the door when they do. And AI coding agents today have to re-derive it every single time they touch a file.

I built **contx** — an append-only log of *why* each file and function exists, version-controlled in a `.contx/` directory alongside the code. Same way every dev who clones the repo has the same code, they now share the same context.

The interesting bit: the entries aren't typed by humans. They're written by AI coding agents (Claude, Cursor, anything MCP-capable) at the moment they make a change — paired with the edit, capturing the rationale from the conversation. A pre-commit hook keeps the pairing honest.

The architecture is deliberately tiny: only two pieces of Python in the whole project. An **MCP server** that exposes read/write tools to the agent, and **`contx serve`**, a local web viewer over the JSONL store. Everything else — repo init, brownfield bootstrap, deployment-YAML summaries, architecture diagrams, drift fixing — is a Claude Code slash command. The logic that needs *intelligence* lives in Claude. The two binaries just handle what slash commands fundamentally can't: serving an agent protocol, and serving a web page.

The web viewer is `contx serve` → `localhost:4242`: file tree, per-symbol intent + full history, full-text search across every rationale and tag, and a "git log for intent" timeline view across the whole repo. Server-rendered HTML + htmx, no JS bundle, no build step, no auth. Great for onboarding, post-mortems, "find every entry tagged `incident` in this subsystem."

The bigger idea: once intent is a first-class versioned artifact, you can feed it into any AI agent — code review, onboarding, refactoring, runbooks — as the canonical source of "what we meant." Today every agent re-derives intent from scratch. With this, intent becomes shared infrastructure.

**Big disclaimer:** this is a vibe-coded weekend project. ~75 commits, ~240 tests on the primitives, end-to-end working — but not production-tested. It also leans hard on Claude Code: without an MCP-capable agent running, most of the workflow doesn't exist. That's a deliberate trade — I'd rather have one good integration than five bad ones — but it's a real constraint.

Next phases I'm planning:
- Team mode — conflict resolution when two devs append different rationales on different branches
- Rationale auto-summarization once a file has 50+ entries
- VS Code / JetBrains plugins with inline "why is this here?" hovers
- Cursor / Windsurf / Codex slash-command equivalents (the MCP server already speaks the standard)
- Plugin ecosystem — linters / security scanners / dependency bots dropping their own entries

If this resonates with anyone wrestling with the same problem — onboarding, lost institutional knowledge, AI agents undoing decisions they don't understand — I'd love to hear what you'd want from it.

Code: <repo link>

---

**Character count notes:** LinkedIn limit is 3000 chars; this draft is ~2050. Trim aggressively if you want it tighter.

**Shorter version (~700 chars, for if you want to keep it punchy):**

> Built **contx** this weekend — git, but for context.
>
> `git blame` tells you *who* and *when*. It never tells you *why*. That knowledge lives in Slack and senior engineers' heads, and AI coding agents have to re-derive it every time they touch a file.
>
> contx is an append-only log of *why* each function exists, version-controlled in `.contx/` alongside the code. AI agents write the entries as they edit — paired with every change, captured from the conversation. The architecture is intentionally tiny: an MCP server, a local web viewer (`contx serve`), and a set of Claude Code slash commands that handle every workflow (init, bootstrap, diagram, deploy summaries, drift fixing). New devs clone the repo and get the whole intent map for free.
>
> Big caveat: weekend project, leans on Claude Code. Works end-to-end but rough. Next up: team-mode conflict resolution, rationale summarization, IDE plugins.
>
> Code: <repo link>
