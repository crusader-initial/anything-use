#!/usr/bin/env bash
# Launch Playwright MCP server with a persistent profile rooted in this repo.
# Path-portable: works from any clone location.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PROFILE="$HERE/profiles/ai-default"
LOG_DIR="$ROOT/logs/browser"
mkdir -p "$PROFILE" "$LOG_DIR/artifacts"

# Optional: source repo-local .env for --secrets
SECRETS_FLAG=()
if [[ -f "$ROOT/.env" ]]; then
  SECRETS_FLAG=(--secrets "$ROOT/.env")
fi

# --user-data-dir gives us a long-lived logged-in profile.
# Do NOT add --isolated; that would discard cookies on close.
# --caps vision: pixel-coordinate mouse fallback when selectors fail.
# --caps storage: cookie/localStorage tools (rarely needed but cheap).
exec npx -y @playwright/mcp@latest \
  --browser chrome \
  --user-data-dir "$PROFILE" \
  --caps vision,storage \
  --output-dir "$LOG_DIR/artifacts" \
  --save-session \
  "${SECRETS_FLAG[@]}" \
  "$@"
