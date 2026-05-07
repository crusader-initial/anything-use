#!/usr/bin/env bash
# Register anything-use MCP servers with claude-code at user scope.
# Idempotent: removes any existing registration with the same name first.
# Skips servers whose run script doesn't yet exist (e.g. computer/ before Phase 4).
#
# claude-code CLI requires all options to come BEFORE the server name, then `--`
# separates name from the launch command. See https://code.claude.com/docs/en/mcp

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found. Install: https://docs.claude.com/en/docs/claude-code/setup" >&2
  exit 1
fi

remove_if_exists() {
  claude mcp remove "$1" --scope user 2>/dev/null || true
}

# --- Browser ---
if [[ -x "$ROOT/servers/browser/run.sh" ]]; then
  echo "==> browser"
  remove_if_exists browser
  claude mcp add --scope user --transport stdio \
    browser -- bash "$ROOT/servers/browser/run.sh"
else
  echo "skip browser (servers/browser/run.sh missing or not executable)"
fi

# --- Mobile (mobile-mcp invoked directly — no wrapper script needed) ---
echo "==> mobile"
remove_if_exists mobile
claude mcp add --scope user --transport stdio \
  --env MOBILEMCP_DISABLE_TELEMETRY=1 \
  mobile -- npx -y @mobilenext/mobile-mcp@latest

# --- Computer (Phase 4 — only if wrapper exists) ---
# Use ${PYTHON} to point at a venv, e.g.:
#   PYTHON=/path/to/anything-use/.venv/bin/python3 bash scripts/install-claude-code.sh
if [[ -f "$ROOT/servers/computer/wrapper/mcp_server.py" ]]; then
  echo "==> computer"
  remove_if_exists computer
  claude mcp add --scope user --transport stdio \
    computer -- "${PYTHON:-python3}" "$ROOT/servers/computer/wrapper/mcp_server.py"
else
  echo "skip computer (Phase 4 not yet built)"
fi

echo
echo "Done. List with: claude mcp list"
