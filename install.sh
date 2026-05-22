#!/usr/bin/env bash
#
# install.sh — install contx on this machine.
#
# Default: installs the `contx` and `contx-mcp` binaries via pipx (preferred)
# or a local venv (fallback). Re-running is safe.
#
# Options:
#   --skill       Also install the Claude Code skill at ~/.claude/skills/contx/
#   --mcp         Also register contx-mcp in ~/.claude/settings.json
#   --all         Shorthand for --skill --mcp
#   -h, --help    Print this help and exit
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WANT_SKILL=0
WANT_MCP=0

for arg in "$@"; do
  case "$arg" in
    --skill) WANT_SKILL=1 ;;
    --mcp) WANT_MCP=1 ;;
    --all) WANT_SKILL=1; WANT_MCP=1 ;;
    -h|--help)
      sed -n '2,13p' "$0"
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      echo "       run with --help for usage" >&2
      exit 2
      ;;
  esac
done

say() { printf '\033[1;36m→\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Locate Python 3.11+
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) || continue
    major=${ver%.*}
    minor=${ver#*.}
    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }; then
      PYTHON="$candidate"
      break
    fi
  fi
done
[ -n "$PYTHON" ] || die "Python 3.11+ not found on PATH"
say "using $PYTHON ($("$PYTHON" --version 2>&1))"

# 2. Install via pipx (preferred) or venv (fallback)
if command -v pipx >/dev/null 2>&1; then
  say "installing contx with pipx (editable from $REPO_ROOT)"
  # --force makes re-runs upgrade in place
  pipx install --force --python "$PYTHON" --editable "$REPO_ROOT" >/dev/null
  # Resolve the resulting binary path
  CONTX_BIN="$(command -v contx || true)"
  if [ -z "$CONTX_BIN" ]; then
    # pipx bin dir may not be on PATH yet
    PIPX_BIN="$($PYTHON -m pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
    CONTX_BIN="$PIPX_BIN/contx"
    warn "$PIPX_BIN is not on PATH — add this to your shell rc:"
    warn "  export PATH=\"$PIPX_BIN:\$PATH\""
  fi
else
  say "pipx not found; installing into a venv at $REPO_ROOT/.venv"
  if [ ! -d "$REPO_ROOT/.venv" ]; then
    "$PYTHON" -m venv "$REPO_ROOT/.venv"
  fi
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
  pip install --quiet --upgrade pip
  pip install --quiet --editable "$REPO_ROOT"
  CONTX_BIN="$REPO_ROOT/.venv/bin/contx"
  warn "contx is in $REPO_ROOT/.venv/bin/ but pipx is not installed."
  warn "Either install pipx (https://pipx.pypa.io/) and re-run, or add"
  warn "  export PATH=\"$REPO_ROOT/.venv/bin:\$PATH\""
  warn "to your shell rc for a system-wide \`contx\` command."
fi

# 3. Verify
if ! "$CONTX_BIN" version >/dev/null 2>&1; then
  die "contx install seems broken — '$CONTX_BIN version' failed"
fi
ok "contx $("$CONTX_BIN" version) installed at $CONTX_BIN"

# 4. Optional: Claude Code skill
if [ "$WANT_SKILL" -eq 1 ]; then
  say "installing Claude Code skill"
  "$CONTX_BIN" install-skill
fi

# 5. Optional: MCP config registration
if [ "$WANT_MCP" -eq 1 ]; then
  SETTINGS="$HOME/.claude/settings.json"
  say "registering contx-mcp in $SETTINGS"
  mkdir -p "$HOME/.claude"
  if [ -f "$SETTINGS" ]; then
    BACKUP="$SETTINGS.contx-backup-$(date +%s)"
    cp "$SETTINGS" "$BACKUP"
    say "backup of existing settings: $BACKUP"
  fi
  "$PYTHON" - <<'PY'
import json
import os
import sys
from pathlib import Path

p = Path(os.environ['HOME']) / '.claude' / 'settings.json'
data = {}
if p.is_file():
    raw = p.read_text().strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: existing settings.json is not valid JSON ({exc}). Aborting.", file=sys.stderr)
            sys.exit(1)
servers = data.setdefault('mcpServers', {})
if servers.get('contx', {}).get('command') == 'contx-mcp':
    print(f"  contx already registered in {p}")
else:
    servers['contx'] = {'command': 'contx-mcp'}
    p.write_text(json.dumps(data, indent=2) + '\n')
    print(f"  added 'contx' to mcpServers in {p}")
PY
fi

# 6. Final message
cat <<EOF

$(ok 'contx installed.')

Next steps in any git repo:
  contx init       # creates .contx/, .contxignore, pre-commit hook
  contx draft      # add context entries interactively
  contx serve      # localhost:4242 — browse the intent map

EOF

if [ "$WANT_SKILL" -eq 0 ] || [ "$WANT_MCP" -eq 0 ]; then
  cat <<EOF
For full Claude Code integration (skill + MCP server), re-run with:
  ./install.sh --all

EOF
fi
