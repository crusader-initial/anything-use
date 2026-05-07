#!/usr/bin/env bash
# Launch mobile-mcp (Android via ADB+UIAutomator, iOS via WebDriverAgent).
# Requires `adb` on PATH for Android. Devices must be paired before starting.

set -euo pipefail

export MOBILEMCP_DISABLE_TELEMETRY=1

# Sanity check: warn if adb isn't reachable. Don't hard-fail — iOS users may
# not need it, and the server itself prints a clearer error.
if ! command -v adb >/dev/null 2>&1; then
  echo "[anything-use/mobile] warning: 'adb' not on PATH. Android control will fail." >&2
  echo "  Install Android Platform Tools: https://developer.android.com/tools/releases/platform-tools" >&2
fi

exec npx -y @mobilenext/mobile-mcp@latest "$@"
