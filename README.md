# contx

Git for context. Append-only logs of *why* each file and function exists, written by AI coding agents as they edit and read by AI agents when explaining code to humans.

See `docs/specs/2026-05-21-contx-design.md` for the full design.

## Install

### TL;DR (if you already have Python 3.11+ and `pipx`)

```bash
git clone <this-repo>
cd contx
./install.sh --all     # CLI binaries + Claude Code skill + MCP registration
```

Done. Skip to **Quickstart**.

---

### Step-by-step (for fresh machines)

#### 1. Python 3.11 or newer

Check what you have:

```bash
python3 --version    # need 3.11+
```

If you're below 3.11 or it's missing, install it:

| OS | Install command |
|---|---|
| **macOS** (Homebrew) | `brew install python@3.12` |
| **macOS** (no Homebrew yet) | install Homebrew from <https://brew.sh>, then `brew install python@3.12` |
| **Ubuntu / Debian** | `sudo apt update && sudo apt install python3.12 python3.12-venv` |
| **Fedora / RHEL** | `sudo dnf install python3.12` |
| **Arch** | `sudo pacman -S python` |
| **Windows** | install from <https://www.python.org/downloads/> (tick "Add Python to PATH" during setup) |

Verify:

```bash
python3.12 --version    # or python3.11
```

#### 2. (Recommended) install `pipx`

`pipx` puts CLI tools on your `PATH` in isolated environments so they don't clash with system Python. `contx`'s installer prefers it.

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath       # adds ~/.local/bin to PATH
# Restart your shell or `source ~/.bashrc` / `source ~/.zshrc`
pipx --version                    # confirm it's on PATH
```

If you skip this step the installer falls back to a local virtualenv inside the cloned repo — works fine, but `contx` won't be globally on `PATH` until you add `<repo>/.venv/bin` to it yourself.

#### 3. Clone and install

```bash
git clone <this-repo>
cd contx
./install.sh --all
```

Flags:

| Flag | What it does |
|---|---|
| `./install.sh` | Install just the `contx` and `contx-mcp` CLI binaries. |
| `./install.sh --skill` | Also copy the Claude Code skill + `contx-*` slash commands to `~/.claude/`. |
| `./install.sh --mcp` | Also register `contx-mcp` in `~/.claude/settings.json` (with a timestamped backup of any existing file). |
| `./install.sh --all` | All of the above. **Recommended for first-time setup.** |
| `./install.sh --help` | Show the full help. |

#### 4. Verify

```bash
contx version           # prints "0.1.0"
contx --help            # lists all subcommands
```

If `contx: command not found`, your shell hasn't picked up the new PATH entry yet — open a new terminal or `source ~/.zshrc` (or `~/.bashrc`).

---

### Development install (editable)

If you're hacking on contx itself, skip the installer:

```bash
git clone <this-repo>
cd contx
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest                  # run the suite
```

### Uninstall

```bash
./uninstall.sh           # interactive: confirms each step
./uninstall.sh --yes     # non-interactive (skip confirmations)
```

Reverses `install.sh`: removes the package (pipx or local venv), the Claude skill at `~/.claude/skills/contx/`, the `contx-*` slash commands at `~/.claude/commands/`, and the `contx` entry from `~/.claude/settings.json` (with a timestamped backup). `--keep-skill`, `--keep-mcp`, `--keep-package` opt out of individual steps.

**Left alone on purpose:** your repos' `.contx/` directories, `.contxignore` files, and pre-commit hooks. Run `contx uninstall-hook` per repo first if you want those cleaned up too.

## Quickstart

In Claude Code, type:

```
/contx-init
```

This walks you through four prompts (hook? enforcement? granularity? deploy manifests?) and creates `.contx/`, `.contxignore`, and optionally the pre-commit hook.

Then use the other slash commands to interact with contx — type `/contx-` in Claude Code to discover them all.

## CLI commands

| Command | Purpose |
|---|---|
| `contx serve [--port 4242] [--host 127.0.0.1] [--strict-port]` | Launch the read-only local web UI. |
| `contx version` | Print version. |

Every other workflow — init, append, show, log, draft, ignore, export, bootstrap, diagram, hook management — lives in a Claude Code slash command at `~/.claude/commands/contx-*.md`. Type `/contx-` in Claude Code to discover them.

## Using with Claude Code (MCP)

contx ships an MCP server (`contx-mcp`) so AI coding agents can read and write context entries directly during a session.

### Add to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp"
    }
  }
}
```

By default the server uses `os.getcwd()` to find the repo root (walks up looking for `.git`). To point at a specific repo, set `CONTX_REPO_ROOT`:

```json
{
  "mcpServers": {
    "contx": {
      "command": "contx-mcp",
      "env": { "CONTX_REPO_ROOT": "/path/to/repo" }
    }
  }
}
```

### MCP tools exposed

| Tool | Purpose |
|---|---|
| `contx_query` | Read folded intent + raw log for a file or symbol. |
| `contx_append` | Add a context entry (created / modified / deleted / etc.). |
| `contx_search` | Substring search across all entries (rationale + tags). |
| `contx_rename` | Refactor bookkeeping for renames and moves. |
| `contx_delete` | Append a deletion entry (history preserved). |
| `contx_audit` | Find orphan sidecars and untracked source files. |

The intended workflow: AI agents call `contx_query` before editing to learn existing context, then call `contx_append` (or `contx_rename` / `contx_delete`) in the same turn as their `Edit` / `Write` tool calls. The CLI is for humans.

## Claude Code skill

contx ships a Claude Code skill that enforces the workflow rules: query existing context before editing, append context in the same turn as code edits, handle renames/deletes through the MCP tools.

### Install

```bash
./install.sh --skill
```

This copies `skills/contx/SKILL.md` to `~/.claude/skills/contx/` and all `skills/contx/commands/contx-*.md` to `~/.claude/commands/`. Re-running the command updates to the latest version (overwrites).

### What the skill enforces

When working in a repo with `.contx/`, Claude will:
- Call `contx_query` before editing a tracked file (to learn existing intent).
- Call `contx_append` in the same turn as any `Edit`/`Write` on a tracked file.
- Call `contx_rename` *before* applying a code rename.
- Call `contx_delete` with a rationale when removing code.
- Ask the user for the *why* if it isn't already clear in the conversation (never invent a rationale).

The skill activates on the user's `/contx` invocation, or you can wire a SessionStart hook to load it automatically when `.contx/` is detected.

### Uninstall

```bash
./uninstall.sh
```

Removes `~/.claude/skills/contx/` and `~/.claude/commands/contx-*.md` (other skills and commands untouched).

## Pre-commit hook

`/contx-init` installs a `pre-commit` hook in `.git/hooks/pre-commit` (choose "No" at the hook prompt to skip). The hook blocks any commit where a tracked source file changed but its `.contx/` sidecar didn't.

Example:

```
$ git commit -m "fix the bug"
error: contx drift — the following files changed without a matching .contx/ entry:
  - src/auth/login.py

Fix it from Claude Code:
  /contx-draft        # propose entries from the staged diff + conversation
  git commit          # re-run after .contx is auto-staged

Bypass once:    git commit --no-verify
Disable entirely:  set 'require_context_on_commit': false in .contx/config.json
```

### Fixing drift with `/contx-draft`

When the hook blocks, run `/contx-draft` in Claude Code. It reads the staged diff and your recent conversation, proposes a rationale for each drifted file, and lets you accept / edit / skip. On accept, it calls `contx_append` and stages `.contx/`. Then re-run `git commit`.

### Bypass

- **One commit:** `git commit --no-verify`
- **Whole repo:** set `"require_context_on_commit": false` in `.contx/config.json` to convert the block into a soft warning.

### Manage the hook

- `/contx-install-hook` — install (or top up) the hook on a repo that wasn't initialized with it.
- `/contx-uninstall-hook` — remove the contx block (preserves other content in the hook).

## Web UI

```bash
contx serve              # localhost:4242
contx serve --port 8080  # any port
```

If the port is already in use, contx tries the next 9 ports automatically. Pass `--strict-port` to fail instead.

Opens a read-only web viewer. Routes:

- `/` — file tree (every source file with contx entries).
- `/file/<path>` — file-level intent, list of symbols, full log.
- `/symbol/<path>::<symbol>` — symbol's current intent + complete log.
- `/search?q=` — full-text search across all rationales and tags.
- `/timeline` — recent entries across the whole repo, sorted newest first.

No auth, no edits, no JS bundle — server-rendered HTML with a sprinkle of htmx. The intent map travels with git: anyone who clones the repo can `contx serve` and see why every function is the way it is.

## `.contxignore`

`contx init` creates a `.contxignore` at the repo root (gitignore-style syntax) with sensible defaults: `**/node_modules/**`, `**/__tests__/**`, `**/.venv/**`, `**/venv/**`, `**/dist/**`, `**/build/**`, `**/.contx/**`. Add to it whatever your team wants contx to skip.

Patterns from `.contxignore` are **additive** to the `ignore` field in `.contx/config.json`. The effective ignore set is the union of both. config.json holds the per-init defaults; `.contxignore` is where you put ongoing per-repo exclusions next to `.gitignore`.

Supported syntax (subset of gitignore):
- `*` — match any single path segment
- `**` — match any number of segments
- `dir/file.py` — exact path
- `# comment` — ignored
- Negation (`!`) is not yet supported.

Affects: drift detection (pre-commit hook), `contx_audit`, and any future tooling that walks the source tree.

## Slash commands (Claude Code)

`./install.sh --skill` installs all slash commands at `~/.claude/commands/`. Each delegates to Claude — Claude reads the actual code and writes meaningful entries via the MCP tools. Type `/contx-` in Claude Code to discover them.

| Command | What it does |
|---|---|
| `/contx-init` | Interactive setup: prompts for hook, enforcement, granularity, and deploy manifests. Creates `.contx/`, `.contxignore`, and optionally the pre-commit hook. |
| `/contx-show <ref>` | Print the folded current intent for a file or symbol. |
| `/contx-log <ref>` | Print the full append-only history for a file or symbol. |
| `/contx-draft` | When the hook blocks, proposes rationales from the staged diff + conversation and calls `contx_append`. |
| `/contx-ignore <pattern>` | Append a gitignore-style pattern to `.contxignore`. |
| `/contx-export [--out PATH]` | Export the repo's intent map as a Markdown document. |
| `/contx-install-hook` | Install (or top up) the pre-commit hook on an already-initialized repo. |
| `/contx-uninstall-hook` | Remove the contx hook block (preserves other content in the hook). |
| `/contx-bootstrap [glob]` | Walk the repo, decide which files/symbols warrant a v0 entry, and write meaningful rationales. Skips boilerplate. Marks files Claude couldn't infer with `pending-rationale`. |
| `/contx-explain <ref>` | Improve or create the entry for `<file>` or `<file>::symbol`. Lifts the rationale from "what" to "why" — incident-anchored when possible. Asks you for business context when it can't infer. |
| `/contx-diagram <type>` | Read the code, reason about architecture, generate a `.drawio` file directly. Types: `architecture`, `components`, `dataflow`, `deploy`. |
| `/contx-deploy-summary` | Read all deployment manifests (k8s, GH Actions, docker-compose, terraform, helm) and write meaningful summaries — what each thing actually deploys, what it connects to, which secrets it consumes. |

## Storage layout

contx stores entries in JSONL sidecars under `.contx/`, mirroring the source tree:

```
your-repo/
├── src/auth/login.py
└── .contx/
    ├── config.json
    └── src/auth/login.py.jsonl
```

Each line of the sidecar is one entry: `{id, kind, symbol, event, rationale, tags, author, timestamp, agent, related}`. Append-only. All files are committed to git so context travels with the code.

## Deployment-manifest awareness

contx tracks deployment manifests (Kubernetes, GitHub Actions, docker-compose) as first-class citizens alongside source files.

### `tracked_paths`

`config.json` has a `tracked_paths` field — a list of `{glob, kind, summarizer}` records:

```json
{
  "tracked_paths": [
    {"glob": "**/*.py", "kind": "source", "summarizer": null},
    {"glob": "k8s/**/*.yaml", "kind": "deploy", "summarizer": null},
    {"glob": ".github/workflows/*.yml", "kind": "deploy", "summarizer": null},
    {"glob": "docker-compose*.yml", "kind": "deploy", "summarizer": null}
  ]
}
```

The pre-commit hook and `contx audit` use these globs to detect drift on any tracked path, not just source files. Use the `/contx-deploy-summary` slash command to write meaningful context entries for deployment manifests.

## Status

Plans 1–5, B1–B4, and C1 shipped: storage + MCP server + pre-commit hook + Claude Code skill + local web UI + per-repo ignore file + full slash-command surface. The Python CLI is intentionally minimal (`serve` + `version`). All user-facing workflows live as Claude Code slash commands at `~/.claude/commands/contx-*.md`. See `docs/plans/` and `docs/BACKLOG.md`.

