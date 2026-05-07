#!/usr/bin/env bash
# Convenience wrapper for the computer-use container.
#
#   ./run.sh up        # build + start
#   ./run.sh down      # stop + remove
#   ./run.sh logs      # tail container logs
#   ./run.sh shell     # exec bash inside the container
#   ./run.sh status    # is agentd alive?

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

case "${1:-}" in
  up)
    docker compose up -d --build
    echo
    echo "Waiting for agentd..."
    for i in $(seq 1 30); do
      if curl -sf http://127.0.0.1:9222/healthz >/dev/null 2>&1; then
        echo "agentd is up."
        echo "  Human view: http://localhost:6080/vnc.html"
        echo "  Health:     http://localhost:9222/healthz"
        exit 0
      fi
      sleep 2
    done
    echo "Timed out waiting for agentd. Check 'docker compose logs'."
    exit 1
    ;;
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f --tail=200
    ;;
  shell)
    docker compose exec computer bash
    ;;
  status)
    if curl -sf http://127.0.0.1:9222/healthz; then
      echo
      echo "OK"
    else
      echo "DOWN — try ./run.sh up"
      exit 1
    fi
    ;;
  *)
    echo "usage: $0 {up|down|logs|shell|status}" >&2
    exit 2
    ;;
esac
