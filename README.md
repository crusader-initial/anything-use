# anything-use

A local framework that connects your AI coding agents (Claude Code, OpenAI Codex)
to **three execution surfaces** via independent MCP servers:

| Surface | What | Backend |
|---|---|---|
| **Browser** | The agent can navigate, click, type on real web pages | [`@playwright/mcp`](https://github.com/microsoft/playwright-mcp) |
| **Mobile** | The agent can operate an Android phone (or iOS) | [`@mobilenext/mobile-mcp`](https://github.com/mobile-next/mobile-mcp) |
| **Computer** | The agent can drive a sandboxed Linux desktop | Anthropic computer-use container + custom MCP wrapper |

The motivation: agents are powerful, but blind to anything that lives only in a phone
app, a desktop GUI, or a site without a public API. This framework hands them eyes
and hands for those surfaces — using one dedicated AI account, isolated from your
personal devices and data.

> Status: **Phase 1-4 done** (all three surfaces wired up). Phase 5-6 (polish + runbook) remaining.
> Full design and roadmap: [`PLAN.md`](./PLAN.md).

## Quick start — Mobile (the most-asked use case)

You have an idle Android phone? Plug it in and read [`docs/mobile-setup.md`](./docs/mobile-setup.md).
Short version:

```bash
# 1. Install adb on Mac
brew install --cask android-platform-tools

# 2. On the phone: factory reset, sign in with a dedicated Google account,
#    enable Developer Options + USB Debugging, plug in via USB
adb devices    # should show your phone

# 3. Clone this repo and register with your AI CLI
git clone https://github.com/<your>/anything-use.git
cd anything-use
bash scripts/install-claude-code.sh    # for Claude Code
bash scripts/install-codex.sh          # for Codex

# 4. In a new claude-code / codex session
mobile_list_available_devices    # should list your phone
mobile_take_screenshot           # should return a PNG of the phone screen
```

## Quick start — Browser

```bash
bash scripts/install-claude-code.sh
# Then in a new claude-code session, use:
browser_navigate https://...
browser_snapshot              # accessibility tree
browser_take_screenshot       # PNG
```

The Chrome profile lives in `servers/browser/profiles/ai-default/` (gitignored). First
time you need to log in to a site, do it manually with a real human session — cookies
will persist across server restarts.

## Quick start — Computer

Sandboxed Linux desktop in a Docker container. Full walkthrough:
[`docs/computer-setup.md`](./docs/computer-setup.md). Short version:

```bash
# 1. Install deps for the host-side MCP wrapper
python3 -m pip install --user -r servers/computer/wrapper/requirements.txt

# 2. Build + start the container (~5 min first time)
bash servers/computer/run.sh up

# 3. Watch the desktop (optional)
open http://localhost:6080/vnc.html

# 4. Register and use
bash scripts/install-claude-code.sh
# in a new claude-code session:
#   computer_health
#   computer_open_url https://example.com
#   computer_screenshot
```

Container architecture: extends Anthropic's official computer-use image
(`ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest`) with a
~150-line FastAPI sidecar (`agentd`) that exposes `xdotool` / `scrot` / `bash` as
REST. A stdio MCP server on the host (`servers/computer/wrapper/mcp_server.py`)
proxies tool calls to it.

## Architecture

```
┌─────────────────────┐    ┌──────────────────────────┐
│  Claude Code / Codex │───▶│  ~/.claude.json          │
│       (host)         │    │  ~/.codex/config.toml    │
└─────────────────────┘    └──────────────┬───────────┘
                                           │ stdio
                            ┌──────────────┼──────────────┐
                            ▼              ▼              ▼
                       ┌─────────┐   ┌─────────┐   ┌──────────┐
                       │ browser │   │ mobile  │   │ computer │
                       │ MCP     │   │ MCP     │   │ MCP wrap │
                       └────┬────┘   └────┬────┘   └────┬─────┘
                            │             │             │ HTTP
                            ▼             ▼             ▼
                       ┌────────┐   ┌──────────┐   ┌──────────┐
                       │ Chrome │   │ Android  │   │ Docker   │
                       │ profile│   │  phone   │   │ desktop  │
                       └────────┘   └──────────┘   └──────────┘
```

Three servers, three processes, one shared dedicated identity. Each can be
started/stopped/swapped without touching the others.

## Why a dedicated AI account

Your agent will eventually log in to Google, GitHub, banking, etc. on the phone and
in the browser. **Don't reuse your personal account.** Set up a clean Google account
and a clean phone — see [`docs/ai-account.md`](./docs/ai-account.md). The agent
operates only what you've explicitly given it; the dedicated account makes that
boundary visible and recoverable.

## Repository layout

```
.
├── PLAN.md                    Full design + 6-phase roadmap
├── docs/
│   ├── ai-account.md          How to set up the dedicated Google account
│   └── mobile-setup.md        How to prep an Android phone end-to-end
├── servers/
│   ├── browser/run.sh         Launches Playwright MCP with persistent profile
│   ├── mobile/run.sh          Launches mobile-mcp
│   └── computer/              Docker container + agentd sidecar + MCP wrapper
│       ├── Dockerfile.wrapper Extends Anthropic's computer-use image
│       ├── docker-compose.yml Container orchestration (localhost-only ports)
│       ├── agentd/            Tiny FastAPI sidecar that lives in the container
│       ├── wrapper/           Host-side stdio MCP server (Python)
│       └── run.sh             Convenience: ./run.sh {up|down|logs|shell|status}
├── scripts/
│   ├── install-claude-code.sh Register all servers with Claude Code (user scope)
│   └── install-codex.sh       Register all servers with Codex (~/.codex/config.toml)
└── logs/                      JSONL audit logs (gitignored, runtime-only)
```

## Contributing / forking

This repo is built to be cloned and tweaked. The install scripts auto-detect the
repo root, so they work from any clone path. PRs welcome — especially:

- iOS path for `servers/mobile/` (mobile-mcp supports it; we just haven't written
  the setup doc)
- Lighter-weight computer-use alternatives (host-side `nut.js` instead of Docker)
- Additional surfaces (e.g. a Tailscale-attached spare laptop, an e-reader)

## License

TBD — currently unlicensed. Will pick before first public release.
