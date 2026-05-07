# Runbook

Operational handbook for keeping anything-use working day-to-day. Per-surface
setup lives in [`mobile-setup.md`](./mobile-setup.md),
[`browser-setup`*](./mobile-setup.md), and [`computer-setup.md`](./computer-setup.md);
this doc is the **cross-surface** stuff.

> *Browser doesn't have a dedicated setup doc — see README's "Quick start —
> Browser" + the first-login flow in [`PLAN.md`](../PLAN.md) §2.2.

## Daily ops

### Where logs live

| Source | Path | Notes |
|---|---|---|
| claude-code MCP traffic | `~/.claude.json` keeps server defs; runtime logs are in claude-code's own state dir | run `/mcp` inside claude-code to see live status |
| codex MCP traffic | depends on `~/.codex/log` config | check `codex --help` for log location |
| Browser MCP artifacts | `logs/browser/artifacts/` | enabled by `--save-session` flag |
| Mobile MCP | claude-code/codex transcript only | mobile-mcp doesn't write its own log |
| agentd (inside computer container) | `/var/log/agentd.jsonl` | one JSON line per tool call |
| Container general | `docker compose -f servers/computer/docker-compose.yml logs` | upstream entrypoint logs to /var/log/orig-entrypoint.log |

### Health checks (run all in 30s)

```bash
# 1. Are the CLIs registered?
claude mcp list                                         # expect browser, mobile, computer
sed -n '/anything-use BEGIN/,/anything-use END/p' ~/.codex/config.toml

# 2. Is the phone reachable?
adb devices                                              # expect 1 device, "device" state

# 3. Is the container alive?
bash servers/computer/run.sh status                      # expect OK + display size

# 4. Browser profile not corrupted?
ls servers/browser/profiles/ai-default/Default/Cookies   # file should exist after first login
```

## Common failures

### claude-code shows a server as "failed"

1. `/mcp` inside claude-code → look at the error
2. Most common: the launch command can't start. Re-run the install script:
   ```bash
   bash scripts/install-claude-code.sh
   ```
   This removes and re-adds, surfacing any path issues.
3. If it's the `computer` server: container not running →
   `bash servers/computer/run.sh up`

### `mobile_take_screenshot` returns black or empty

- Phone screen has timed out → enable Stay awake in Developer Options
- Or wake it: `adb shell input keyevent 26`

### Phone disappears from `adb devices` after a while

```bash
adb kill-server && adb start-server
adb connect 192.168.x.x:5555    # if Wi-Fi ADB
```

If repeated, the phone's ADB authorization has timed out. Set "Disable adb
authorization timeout" in Developer Options.

### Browser profile got corrupted (Chrome won't start)

```bash
# Back up and reset — you'll need to re-login
mv servers/browser/profiles/ai-default servers/browser/profiles/ai-default.bak.$(date +%s)
# Restart the browser server; it'll create a fresh profile
```

### Container won't start / OOM during build

- Docker Desktop → Settings → Resources → Memory ≥ 4 GB (8 GB recommended)
- Apple Silicon: Settings → General → "Use Rosetta for x86/amd64 emulation" = on
- Storage low? `docker system prune -a` (warning: removes ALL unused images)

### Container starts but `computer_health` fails

```bash
docker compose -f servers/computer/docker-compose.yml logs --tail=100
docker compose -f servers/computer/docker-compose.yml exec computer bash
# Inside container:
xdpyinfo -display :1                       # X up?
curl -s 127.0.0.1:9222/healthz             # agentd up?
tail /var/log/orig-entrypoint.log          # what failed in the upstream stack?
```

### TOTP code rejected by Google

Time drift on the host:
```bash
sudo sntp -sS time.apple.com   # macOS
# or
sudo timedatectl set-ntp true  # Linux
```

### Google account locked / risk-flagged

- Recover via https://accounts.google.com/signin/recovery using the backup
  codes saved in 1Password (`AI / Google Master`)
- If Google insists on a phone, the original SIM you registered with works best
- After unlock: re-login on every surface that was using cookies (browser
  profile and the phone)

## Updating the framework

```bash
cd /path/to/anything-use
git pull

# 1. Update Python deps if changed
python3 -m pip install --user -r servers/computer/wrapper/requirements.txt --upgrade

# 2. Rebuild the container if Dockerfile/agentd changed
bash servers/computer/run.sh down
bash servers/computer/run.sh up         # rebuilds because of --build flag in run.sh

# 3. Re-register (idempotent)
bash scripts/install-claude-code.sh
bash scripts/install-codex.sh
```

`@playwright/mcp@latest` and `@mobilenext/mobile-mcp@latest` auto-pick up new
versions on next launch — no manual update needed unless they break.

## Resetting everything

If state got weird and you want to start clean **without losing the AI
account**:

```bash
# 1. Stop and remove the container + its data
bash servers/computer/run.sh down
rm -rf servers/computer/data

# 2. Wipe the browser profile (forces re-login everywhere)
rm -rf servers/browser/profiles/ai-default

# 3. Remove MCP registrations
claude mcp remove browser --scope user
claude mcp remove mobile --scope user
claude mcp remove computer --scope user
# Strip the codex managed block
sed -i.bak '/anything-use BEGIN/,/anything-use END/d' ~/.codex/config.toml

# 4. Reinstall
bash scripts/install-claude-code.sh
bash scripts/install-codex.sh
bash servers/computer/run.sh up
```

The phone keeps its state (it's a separate device). Factory-resetting it is
in [`mobile-setup.md`](./mobile-setup.md) §2.

## Cost watch

- **Claude/Codex token spend** — each `*_screenshot` call ships a base64 PNG to
  the model. Big screens = big tokens. Default container size 1280x800 → ~50KB
  PNG → ~70k tokens (vision). On Computer specifically, prefer
  `computer_screen_size` once, then crop with `computer_screenshot` + region
  if you ever extend agentd to take a region.
- **Disk** — `servers/computer/data/` grows with browser cache. Periodic
  `du -sh servers/computer/data` and clean Firefox cache from inside the
  container.
- **Bandwidth** — mobile-mcp screenshots over Wi-Fi ADB are full PNGs each
  call. If you're tethering, that adds up.

## Security recap (read once a quarter)

- ✅ All container ports bound to 127.0.0.1 only
- ✅ Browser profile is per-repo, not your personal Chrome
- ✅ Phone is on a dedicated AI Google account
- ✅ Secrets (password, TOTP) only in 1Password, never in the repo
- ❌ Never copy cookies between surfaces (Google risk-flag)
- ❌ Never bind agentd port 9222 to 0.0.0.0
- ❌ Never `docker run -v $HOME:/host` — that breaks the sandbox

If something feels off, run the **Resetting everything** steps above; the cost
of a fresh state is ~30 minutes (mostly waiting for re-logins).
