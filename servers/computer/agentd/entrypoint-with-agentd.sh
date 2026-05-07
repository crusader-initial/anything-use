#!/usr/bin/env bash
# Wrapper entrypoint: starts the original anthropic-quickstarts entrypoint in a
# detached session (it brings up Xvfb / mutter / x11vnc / noVNC / Streamlit),
# waits for the X display to appear, then execs agentd as the foreground
# process so docker tracks its lifecycle.
#
# We keep the upstream Streamlit + noVNC stack running because:
#   - noVNC at :6080 is how a human watches what the agent is doing
#   - leaving the upstream demo running costs ~nothing and aids debugging

set -e

ORIG_ENTRYPOINT="${ORIG_ENTRYPOINT:-/home/computeruse/entrypoint.sh}"

# Detach the original entrypoint into its own session so it doesn't share our
# controlling terminal or signals.
setsid bash "$ORIG_ENTRYPOINT" </dev/null >/var/log/orig-entrypoint.log 2>&1 &

# Wait for X to be ready (up to 60s).
for _ in $(seq 1 60); do
  if xdpyinfo -display "${DISPLAY:-:1}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! xdpyinfo -display "${DISPLAY:-:1}" >/dev/null 2>&1; then
  echo "[agentd] X display ${DISPLAY:-:1} did not come up within 60s" >&2
  echo "[agentd] dumping orig-entrypoint.log:" >&2
  tail -50 /var/log/orig-entrypoint.log >&2 || true
  exit 1
fi

echo "[agentd] X is ready on ${DISPLAY:-:1}; starting agentd on 127.0.0.1:9222"
exec env DISPLAY="${DISPLAY:-:1}" python3 /opt/agentd/agentd.py
