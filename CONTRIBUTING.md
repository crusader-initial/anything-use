# Contributing to anything-use

Thanks for taking interest. The framework is designed to be small and forkable,
so the contribution surface is intentionally narrow.

## Repo conventions

- Three independent MCP servers, each in `servers/<name>/`. They do **not**
  share code at runtime. If two of them need the same helper, copy it.
- Every shell script resolves its own location:
  ```bash
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT="$(cd "$HERE/../.." && pwd)"
  ```
  No hardcoded paths. Test by cloning into a path with spaces.
- Per-server docs live in `docs/<surface>-setup.md` and are written for someone
  who has never used this repo.
- `PLAN.md` is the source of truth for design; if you change the architecture,
  update PLAN.md in the same PR.

## Local checks

Before opening a PR, run:

```bash
# Shell
shellcheck servers/**/*.sh scripts/*.sh

# Python (no real test suite yet — just syntax + import check)
python3 -m py_compile servers/computer/agentd/agentd.py
python3 -m py_compile servers/computer/wrapper/mcp_server.py

# Docker compose validity
docker compose -f servers/computer/docker-compose.yml config >/dev/null
```

CI runs these on every PR. See `.github/workflows/lint.yml`.

## Adding a new MCP server (a new surface)

1. Create `servers/<name>/` with at minimum a `run.sh` that execs the server
   on stdio.
2. If you wrap a third-party MCP server (recommended where one exists), keep
   your `run.sh` thin — the value is in the env / flag wiring, not the impl.
3. Add registration in `scripts/install-claude-code.sh` and
   `scripts/install-codex.sh`. Make it conditional on the script/file existing
   so partial installs don't break.
4. Add `docs/<name>-setup.md` covering:
   - hardware/software prereqs
   - one-time setup steps
   - validation commands
   - a troubleshooting table
5. Update `README.md` table + Quick start section.

## Adding a tool to the computer-use wrapper

Two parts:
1. Add a route in `servers/computer/agentd/agentd.py` (request model + handler).
2. Add the matching `@mcp.tool()` in `servers/computer/wrapper/mcp_server.py`.

Keep the agentd surface narrow — it's the trust boundary inside the container.
Anything that doesn't need X can go through `computer_bash` instead.

## What we won't merge

- Adding a fourth surface "just in case". If you have a real use case for
  e.g. a Tailscale-attached laptop, open an issue first.
- Premature abstractions ("a generic GUI framework on top of all three"). The
  three surfaces are deliberately separate — that's the whole point of the
  design.
- Bundled credentials. Never commit cookies, profiles, ADB keys, or API keys.
- Disabling the localhost-only port binding on the computer container without
  also adding auth.

## Licensing

By contributing, you agree your code is published under the MIT License (see
[`LICENSE`](./LICENSE)).
