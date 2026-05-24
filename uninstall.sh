#!/usr/bin/env bash
#
# uninstall.sh — remove contx from this machine.
#
# Reverses what install.sh did:
#   - Uninstalls the pipx (or venv) install
#   - Removes the Claude skill at ~/.claude/skills/contx/
#   - Removes the contx-* slash commands from ~/.claude/commands/
#   - Removes the 'contx' entry from ~/.claude/settings.json mcpServers
#
# Leaves alone on purpose:
#   - .contx/ directories in your repos (your context history)
#   - .contxignore files (your per-repo config)
#   - .git/hooks/pre-commit in your repos (run `contx uninstall-hook` per repo first
#     if you want to remove the hook block)
#
# Options:
#   --keep-skill   Don't remove the Claude skill / slash commands
#   --keep-mcp     Don't touch ~/.claude/settings.json
#   --keep-package Don't uninstall the contx Python package
#   -y, --yes      Skip confirmation prompts
#   -h, --help     Print this help and exit
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP_SKILL=0
KEEP_MCP=0
KEEP_PACKAGE=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --keep-skill) KEEP_SKILL=1 ;;
    --keep-mcp) KEEP_MCP=1 ;;
    --keep-package) KEEP_PACKAGE=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      echo "       run with --help for usage" >&2
      exit 2
      ;;
  esac
done

say()  { printf '\033[1;36m→\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

confirm() {
  if [ "$ASSUME_YES" -eq 1 ]; then return 0; fi
  printf '\033[1;33m?\033[0m %s [y/N] ' "$*"
  read -r reply
  case "$reply" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

# 1. Locate Python 3.11+ (used to edit settings.json safely)
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

# 2. Remove the Claude skill + slash commands
if [ "$KEEP_SKILL" -eq 0 ]; then
  HAS_SKILL=0
  if [ -d "$HOME/.claude/skills/contx" ]; then HAS_SKILL=1; fi
  if compgen -G "$HOME/.claude/commands/contx-*.md" >/dev/null 2>&1; then HAS_SKILL=1; fi

  if [ "$HAS_SKILL" -eq 1 ]; then
    if confirm "remove Claude skill + contx-* slash commands from ~/.claude/?"; then
      if command -v contx >/dev/null 2>&1; then
        contx uninstall-skill >/dev/null || true
      else
        # Fallback: contx binary already gone — do it directly
        rm -rf "$HOME/.claude/skills/contx"
        for f in "$HOME"/.claude/commands/contx-*.md; do
          [ -e "$f" ] && rm -f "$f"
        done
      fi
      ok "removed skill + slash commands"
    fi
  else
    say "no Claude skill installed — skipping"
  fi
fi

# 3. Remove the MCP entry from ~/.claude/settings.json
if [ "$KEEP_MCP" -eq 0 ]; then
  SETTINGS="$HOME/.claude/settings.json"
  if [ -f "$SETTINGS" ]; then
    # Check whether 'contx' is actually in there before asking
    if grep -q '"contx"' "$SETTINGS" 2>/dev/null; then
      if confirm "remove the 'contx' mcpServers entry from $SETTINGS?"; then
        [ -n "$PYTHON" ] || die "Python 3.11+ required to edit settings.json"
        BACKUP="$SETTINGS.contx-uninstall-backup-$(date +%s)"
        cp "$SETTINGS" "$BACKUP"
        say "backup of existing settings: $BACKUP"
        "$PYTHON" - <<'PY'
import json
import os
import sys
from pathlib import Path

p = Path(os.environ['HOME']) / '.claude' / 'settings.json'
if not p.is_file():
    sys.exit(0)
raw = p.read_text().strip()
if not raw:
    sys.exit(0)
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"error: existing settings.json is not valid JSON ({exc}). Aborting.", file=sys.stderr)
    sys.exit(1)
servers = data.get('mcpServers')
if isinstance(servers, dict) and 'contx' in servers:
    del servers['contx']
    if not servers:
        data.pop('mcpServers', None)
    p.write_text(json.dumps(data, indent=2) + '\n')
    print(f"  removed 'contx' from mcpServers in {p}")
else:
    print("  no 'contx' entry found in mcpServers")
PY
        ok "settings.json updated"
      fi
    else
      say "no contx entry in $SETTINGS — skipping"
    fi
  else
    say "no $SETTINGS file — skipping"
  fi
fi

# 4. Uninstall the package
if [ "$KEEP_PACKAGE" -eq 0 ]; then
  REMOVED=0

  # 4a. Try pipx first
  if command -v pipx >/dev/null 2>&1; then
    if pipx list 2>/dev/null | grep -q 'package contx '; then
      if confirm "uninstall contx via pipx?"; then
        pipx uninstall contx >/dev/null
        ok "pipx uninstalled contx"
        REMOVED=1
      fi
    fi
  fi

  # 4b. Otherwise the local venv at <repo>/.venv (install.sh's fallback)
  if [ "$REMOVED" -eq 0 ] && [ -d "$REPO_ROOT/.venv" ]; then
    if confirm "remove the local venv at $REPO_ROOT/.venv?"; then
      rm -rf "$REPO_ROOT/.venv"
      ok "removed $REPO_ROOT/.venv"
      REMOVED=1
    fi
  fi

  if [ "$REMOVED" -eq 0 ]; then
    warn "contx is not installed via pipx and no local .venv was found here."
    warn "If you installed contx into another venv with 'pip install -e .',"
    warn "  activate that venv and run: pip uninstall contx"
  fi
fi

# 5. Final message
cat <<EOF

$(ok 'contx uninstalled.')

Left alone on purpose:
  - .contx/ directories in your repos        (your context history)
  - .contxignore files                        (your per-repo config)
  - .git/hooks/pre-commit blocks in repos     (run 'contx uninstall-hook' per repo before this)

To wipe a repo's contx state too:
  cd /your/repo
  contx uninstall-hook        # (would have needed to run before this script)
  rm -rf .contx/ .contxignore # deletes all stored intent — irreversible

EOF
