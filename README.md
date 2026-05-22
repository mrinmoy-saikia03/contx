# contx

Git for context. Append-only logs of *why* each file and function exists, written by AI coding agents as they edit and read by AI agents when explaining code to humans.

See `docs/specs/2026-05-21-contx-design.md` for the full design.

## Quickstart

```bash
pip install -e .[dev]
contx init
contx append --ref src/foo.py::bar --event created --rationale "why this exists"
contx show src/foo.py::bar
contx log src/foo.py
```

## CLI commands

| Command | Purpose |
|---|---|
| `contx init` | Initialize contx for the current git repo (creates `.contx/config.json`). |
| `contx append --ref X --event Y --rationale Z` | Add a context entry. `--event` is one of `created`, `modified`, `renamed_in`, `renamed_out`, `moved_in`, `moved_out`, `deleted`. Repeatable `--tag` and `--related`. |
| `contx show <ref>` | Print the folded current intent for a file or symbol. |
| `contx log <ref>` | Print the full append-only history. |
| `contx version` | Print version. |

`<ref>` is either `path/to/file.py` (file-level) or `path/to/file.py::Class.method` (symbol-level).

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

## Status

Plan 1 (storage core + CLI) and Plan 2 (MCP server) shipped. Plans 3-5 (commit-time extraction hook, Claude Code skill, web UI) pending. See `docs/plans/` and `docs/BACKLOG.md`.

