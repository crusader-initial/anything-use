# anything-use — 本地 GUI agent 框架 实施 plan

把 codex 和 claude-code 通过 MCP 接到三种执行表面：**Browser / Computer / Mobile**。
三个 server 独立部署、独立鉴权、独立日志，由两个 CLI 共同消费。

---

## Phase 0 — 调研结论（事实基线）

> 这一节是后面所有 phase 的 ground truth。任何动手之前先回到这里核对。

### 0.1 MCP 协议状态（2026-05 当时）

- **当前 spec 修订**：`2025-11-25`（schema.ts 路径 `modelcontextprotocol/specification/schema/2025-11-25/schema.ts`）
- **传输**：`stdio`（本地）和 **Streamable HTTP**（远程）。SSE 在 claude-code docs 中明确标注 `deprecated` —— 不要选它。
- **JSON-RPC 2.0** 消息层；server 在 `initialize` 里声明 `tools / resources / prompts / logging` 等 capability。
- **图片返回**：tool 结果里嵌 `{ type: "image", data: "<base64>", mimeType: "image/png" }`。截图就是这个形状。
- **进度通知**：`notifications/progress`（用于长任务，比如手机 swipe + 等待）。

### 0.2 claude-code 怎么消费 MCP（已读 `code.claude.com/docs/en/mcp`）

- CLI：`claude mcp add [--transport stdio|http|sse] [--scope local|project|user] [--env K=V] [--header "..."] NAME -- COMMAND ARGS...`
- **三个 scope**：
  | Scope | 加载范围 | 文件 |
  |---|---|---|
  | local（默认） | 当前 project，仅自己 | `~/.claude.json` 里 `projects."<path>".mcpServers` |
  | project | 当前 project，团队共享 | repo 根的 `.mcp.json` |
  | user | 所有 project，仅自己 | `~/.claude.json` 顶层 |
- **stdio 条目 schema**：`{ command, args, env, type? }`
- **http 条目 schema**：`{ type: "http", url, headers }`
- **变量展开**在 `.mcp.json`：`${VAR}`、`${VAR:-default}`，可用于 `command/args/env/url/headers`
- 工具数 / 重连：HTTP/SSE 自动指数退避重连，stdio 不重连。MCP_TIMEOUT、MAX_MCP_OUTPUT_TOKENS 是相关 env。

### 0.3 codex 怎么消费 MCP

- 文件：`~/.codex/config.toml`（全局）或 `.codex/config.toml`（项目，需要 trusted）
- TOML section：`[mcp_servers.NAME]`（**必须是下划线**，写成 `mcp-servers` codex 会静默忽略）
- stdio 字段：`command`（必填）、`args`、`env`、`env_vars`、`cwd`
- http 字段：`url`、`bearer_token_env_var`、`http_headers`、`env_http_headers`
- 公共字段：`startup_timeout_sec`、`tool_timeout_sec`、`enabled`、`required`、`enabled_tools`、`disabled_tools`
- CLI：`codex mcp add NAME --env K=V -- COMMAND ARGS`

### 0.4 Playwright MCP（已读官方 README）

- 包：`@playwright/mcp`，跑法：`npx @playwright/mcp@latest`
- 关键 flag：
  - `--browser chrome|firefox|webkit|msedge`
  - `--headless`（默认 headed）
  - `--user-data-dir <path>` —— **持久化 profile 的关键**
  - `--isolated` + `--storage-state <file>` —— 多 client 并发时使用
  - `--caps vision,pdf,devtools,network,storage,config,testing` —— 启用对应 tool 组
  - `--executable-path`、`--proxy-server`、`--ignore-https-errors`、`--device`、`--viewport-size`、`--user-agent`、`--secrets <dotenv>`
- **持久化模式**（来自 README）：默认就持久化（OS 缓存目录 + workspace 哈希）。**同一 profile 同时只能一个浏览器实例用**。要长期登录态：用 `--user-data-dir=/path/to/dedicated`，不要加 `--isolated`。
- Tool 集合（节选，56 个）：
  - 核心：`browser_navigate / navigate_back / click / type / fill_form / press_key / hover / drag / drop / file_upload / select_option / handle_dialog / evaluate / wait_for / resize / close`
  - 捕获：`browser_snapshot`（a11y tree）、`browser_take_screenshot`
  - 标签：`browser_tabs`
  - 网络（--caps=network）：`browser_network_requests / network_request / route / route_list / unroute / network_state_set`
  - 存储（--caps=storage）：`browser_cookie_*`、`browser_localstorage_*`、`browser_sessionstorage_*`、`browser_storage_state`、`browser_set_storage_state`
  - 视觉（--caps=vision）：`browser_mouse_click_xy / mouse_move_xy / mouse_drag_xy / mouse_down / mouse_up / mouse_wheel`
  - 危险：`browser_run_code_unsafe`（执行任意 Playwright JS）

### 0.5 Anthropic computer-use-demo（已读 README + Dockerfile）

- 镜像：`ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest`
- 基础：`ubuntu:22.04` + Xvfb + mutter + tint2 + x11vnc + noVNC + xdotool + scrot + ImageMagick
- 预装：firefox-esr、libreoffice、gedit、xpaint、pcmanfm、galculator…
- 端口：
  | Port | 用途 |
  |---|---|
  | 5900 | 直连 VNC |
  | 6080 | noVNC web (`/vnc.html`) |
  | 8501 | Streamlit 应用 |
  | 8080 | combined chat + desktop UI |
- 默认 `WIDTH=1024 HEIGHT=768 DISPLAY_NUM=1`
- 官方 run 命令：
  ```bash
  docker run \
      -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
      -v $HOME/.anthropic:/home/computeruse/.anthropic \
      -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
      -it ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
  ```
- **关键事实**：这镜像里跑的是 **Streamlit 应用直接调 Anthropic API**，**不是 MCP server**。如果想给 codex / claude-code 用，必须自己写一层 MCP 包装。
- README 没提 arm64 / Apple Silicon —— 在 M 系列 Mac 上要加 `--platform linux/amd64`，会启用 Rosetta 模拟，性能可接受但能感觉到慢。
- VNC / noVNC 默认绑 0.0.0.0、无密码 —— **对外网暴露前必须改**。

### 0.6 mobile-mcp（已读官方 README） ⚠️ **路线变更**

调研发现 `@mobilenext/mobile-mcp` 已经是一个**成熟的 MCP server**，覆盖了 Android（ADB + UI Automator）和 iOS（accessibility + WebDriverAgent）。

- 安装：`npx -y @mobilenext/mobile-mcp@latest`
- 工具表（共 ~20 个）：
  - 设备：`mobile_list_available_devices / get_screen_size / get_orientation / set_orientation`
  - 应用：`mobile_list_apps / launch_app / terminate_app / install_app / uninstall_app`
  - 屏幕：`mobile_take_screenshot / save_screenshot / list_elements_on_screen / click_on_screen_at_coordinates / double_tap_on_screen / long_press_on_screen_at_coordinates / swipe_on_screen`
  - 输入：`mobile_type_keys / press_button / open_url`
- 前置：Android Platform Tools（adb 在 PATH）、设备已配对、Node 22+。
- env：`MOBILEMCP_DISABLE_TELEMETRY=1`（推荐设上）

**重要决策**：原计划"自己写 ADB MCP server" → **改为先复用 mobile-mcp**。它的 tool 集合已经覆盖你 90% 需求。**只有当你发现具体短板时**（例如想要 `dumpsys activity` 输出、想要 logcat 流、想要 ADBKeyBoard 中文输入）才 fork 或写 sidecar server。

如果**确实**要写 sidecar 来补能力，建议只暴露 mobile-mcp 没有的窄子集：
- `mobile_dumpsys` —— 拿 foreground activity / 包名
- `mobile_logcat_tail` —— 抓最近 N 行日志
- `mobile_unicode_text` —— 通过 ADBKeyBoard IME 输入中文/emoji
- `mobile_intent` —— 发任意 Intent（深链跳转）

### 0.7 安全 / 账号 / 隔离 baseline

- **AI Google 账号**：单独建一个，密码和 TOTP 都进 1Password（CLI `op item get NAME --otp` 可以取实时 OTP code）。Google 现在新号几乎都要手机验证 —— 用一张能收短信的实体卡（不要 Google Voice，过去一年命中率很低）。
- **凭据共享原则**：不要在三个 surface 之间复制 cookie，会触发 Google 风控。**让每个 surface 各自登录一次**，靠 password manager + TOTP 完成。
- **手机网络**：推荐 Wi-Fi 一致同网段（adb-over-wifi 直接通），中长期再考虑路由器 guest VLAN。SIM 不必。
- **审计日志**：每个 server 写一条 JSONL：`{ts, server, tool, args_redacted, result_summary, screenshot_path}` → `~/anything-use/logs/<server>/YYYY-MM-DD.jsonl`。

---

## Phase 1 — 仓库骨架 + AI 账号 + secrets

**目标**：项目目录可工作、AI 账号能用、密码和 TOTP 在 1Password 里。

### 1.1 仓库结构

```
/Users/cyrus/project/anything-use/
├── PLAN.md                         # 本文件
├── README.md                       # 入口、快速启动
├── .env.example                    # 列出需要的 env（不含值）
├── .gitignore                      # 排除 logs/、profiles/、.env
├── docs/
│   ├── architecture.md             # 三 server 拓扑图
│   ├── ai-account.md               # 账号建立 / 恢复手册
│   └── runbook.md                  # 常见故障处理
├── servers/
│   ├── browser/                    # Playwright MCP 启动脚本和 profile
│   │   ├── run.sh
│   │   └── profiles/.gitkeep       # 实际 profile 不入库
│   ├── mobile/                     # mobile-mcp 配置 + 可选 sidecar
│   │   └── run.sh
│   └── computer/                   # docker compose + MCP wrapper
│       ├── docker-compose.yml
│       ├── Dockerfile.wrapper      # 在官方 image 之上加一个 HTTP→action bridge
│       ├── wrapper/                # MCP server 源码（Python 或 TS）
│       └── run.sh
├── scripts/
│   ├── install-claude-code.sh      # 把三个 server 注册进 claude-code
│   ├── install-codex.sh            # 同上写进 ~/.codex/config.toml
│   └── secrets-bootstrap.sh        # op signin、确认 vault 存在
└── logs/                           # JSONL 审计，gitignored
    ├── browser/
    ├── mobile/
    └── computer/
```

### 1.2 步骤

1. `cd /Users/cyrus/project/anything-use && git init`
2. 创建上面的目录骨架（空 `.gitkeep` 占位）
3. 写最小 `.gitignore`：`logs/ servers/browser/profiles/ servers/computer/data/ .env *.local.toml`
4. **建 AI Google 账号**：
   - 准备一张能收短信的 SIM
   - 用一台**干净的浏览器**（建议就是即将作为 Browser server profile 的那个 `--user-data-dir`）走注册
   - 立刻打开 2-Step Verification → 加 **Authenticator app**，把 secret 存进 1Password 的 `AI / Google Master` 条目（1Password 支持把 OTP secret 直接存进字段，之后 `op item get "AI / Google Master" --otp` 取 6 位码）
   - 关掉所有"安全提醒邮件给手机"之类的推送（无人值守的账号收不到）
   - 备份恢复码也存进 1Password 同一条目
5. 写 `docs/ai-account.md` 记录上面流程（不要写密码本身）

### 1.3 验收

- `gh` 风格 self-check：`op signin && op item get "AI / Google Master" --otp` 能返回 6 位数字
- 仓库 `git log` 至少一个 commit："chore: scaffold anything-use repo"
- README 第一段说明"这是一个本地 GUI agent 框架"，并指向 `docs/architecture.md`

---

## Phase 2 — Browser MCP（Playwright，复用）

**目标**：claude-code 和 codex 都能调用 `browser_*` 工具，目标浏览器已用 AI 账号登录 Google + 一个测试站。

### 2.1 启动脚本 `servers/browser/run.sh`

参考的事实：见 0.4 的 flag 列表。落到脚本：

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${ROOT}/profiles/ai-default"
mkdir -p "$PROFILE"

exec npx -y @playwright/mcp@latest \
  --browser chrome \
  --user-data-dir "$PROFILE" \
  --caps vision,storage,network \
  --output-dir "$ROOT/../../logs/browser/artifacts" \
  --save-session \
  --secrets "$ROOT/.env" \
  "$@"
```

要点：
- **不**加 `--isolated` —— 我们要 profile 持久
- `--caps vision` 让 agent 在元素 selector 失败时能 click_xy 兜底
- `--caps storage` 给 cookie/storage 工具
- `--secrets` 让 server 能从 dotenv 读敏感值（README 提到的）
- 如果想 headless，附加 `--headless` —— 第一次登录建议**先 headed** 让你人工完成验证码 + 2FA，之后所有会话都从 profile 复用 cookie

### 2.2 首次登录流程

1. 跑 `bash servers/browser/run.sh`（headed 模式）
2. 在另一个 shell `claude mcp add browser -s user -- bash $(pwd)/servers/browser/run.sh`
3. 进 claude-code，让它 `browser_navigate https://accounts.google.com`
4. 当弹出密码 / 2FA 时，**人工**填密码（从 1Password GUI 复制）+ TOTP（`op item get ... --otp`）
5. 关掉 server，cookies 已经在 `profiles/ai-default/Default/Cookies` 里
6. 之后无论 headed 还是 headless，账号都已登录

### 2.3 注册到 CLI

claude-code（user 作用域，跨项目可用）：
```bash
claude mcp add browser \
  --scope user \
  --transport stdio \
  -- bash /Users/cyrus/project/anything-use/servers/browser/run.sh
```

codex（`~/.codex/config.toml`）：
```toml
[mcp_servers.browser]
command = "bash"
args = ["/Users/cyrus/project/anything-use/servers/browser/run.sh"]
startup_timeout_sec = 60
```

### 2.4 验收

- claude-code: `/mcp` 列表里 `browser` 状态 connected，工具数 ≥ 30
- 让 claude-code 跑：`browser_navigate https://gmail.com` → `browser_snapshot` 应返回已登录用户的 a11y tree
- codex 用 `--mcp-debug` 或 `codex mcp list` 看到 browser
- `~/anything-use/logs/browser/` 下能看到一个 trace（如果开了 `--save-session`）

---

## Phase 3 — Mobile MCP（mobile-mcp，复用 + 可选 sidecar）

**目标**：插上 Android 手机，agent 能截屏、点击、launch app、看 UI tree。

### 3.1 物理 / 系统准备

1. 拿空闲 Android 机，**factory reset**
2. 设置时用 AI Google 账号登录（这一步通常需要在手机上输 TOTP —— 直接看 1Password app 或 `op item get ... --otp`）
3. 开发者选项 → USB debugging 开
4. 设置 → 显示 → 屏幕超时设最长 / 充电时屏幕保持唤醒
5. 不锁屏，或者只用 PIN（不用指纹/面容 —— ADB 不能解锁生物识别）
6. （可选）安装 ADBKeyBoard APK，并在 设置 → 语言和输入 → 当前键盘 选它（解决 unicode 输入）
7. 用 USB 接 Mac，`adb devices` 应该看到设备
8. 切 ADB-over-Wi-Fi（永久版，从 Android 11+ 起）：
   ```bash
   adb tcpip 5555      # 在 USB 状态下
   adb shell ip route  # 找手机 IP
   adb connect 192.168.x.x:5555
   # 之后拔 USB 也能用
   ```
   或者用配对模式：手机设置 → 开发者选项 → 无线调试 → 配对 → `adb pair host:port code`

### 3.2 启动脚本 `servers/mobile/run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
export MOBILEMCP_DISABLE_TELEMETRY=1
exec npx -y @mobilenext/mobile-mcp@latest "$@"
```

### 3.3 注册到 CLI

claude-code：
```bash
claude mcp add mobile \
  --scope user \
  --transport stdio \
  --env MOBILEMCP_DISABLE_TELEMETRY=1 \
  -- npx -y @mobilenext/mobile-mcp@latest
```

codex：
```toml
[mcp_servers.mobile]
command = "npx"
args = ["-y", "@mobilenext/mobile-mcp@latest"]
env = { MOBILEMCP_DISABLE_TELEMETRY = "1" }
startup_timeout_sec = 60
```

### 3.4 验收

- `adb devices` 列出 1 台 device
- claude-code: `mobile_list_available_devices` 返回该设备
- `mobile_take_screenshot` 返回非空 PNG（在 client 里能看到截图）
- 让 agent `mobile_launch_app` 一个具体包，再 `mobile_list_elements_on_screen` 看到合理元素

### 3.5 可选：sidecar `mobile-extra`

只有当上面 5 个验收都通过、且实际使用中发现 mobile-mcp 缺了某个具体能力（例如 logcat、dumpsys、ADBKeyBoard）时再起这个 sidecar。

技术骨架（可后置到独立 phase）：Python + `mcp` SDK + `subprocess.run(["adb", "shell", ...])`。Tool 列表保持窄：`adb_dumpsys / adb_logcat_tail / adb_intent / adb_unicode_text`。打印 JSONL 到 `logs/mobile-extra/`。

---

## Phase 4 — Computer use（Docker 容器 + 自写 MCP wrapper）

**目标**：一个独立的 Linux 桌面 VM，agent 能在里面看见、点击、打字、跑命令。这是最难的一块。

### 4.1 架构选型

```
codex / claude-code
       │ stdio
       ▼
┌────────────────────┐
│ MCP wrapper (host) │  ← 这是我们要写的
│  ports: stdio      │
└──────────┬─────────┘
           │ HTTP (localhost:9222)
           ▼
┌──────────────────────────────────────┐
│ Container: anthropic-quickstarts     │
│  + tiny FastAPI sidecar (`agentd`)   │
│  - VNC 5900 / noVNC 6080 (人观察)    │
│  - agentd 9222 (不暴露公网)           │
│  Xvfb display :1, 1280x800           │
└──────────────────────────────────────┘
```

两个新组件：
- **`agentd`** —— 跑在容器里的小 HTTP server，把 `screenshot / click / type / key / scroll / bash` 这些原语暴露成 REST。用 xdotool + scrot 实现，~200 行 Python。
- **MCP wrapper** —— 跑在 host 上的 stdio MCP server，把 MCP `tool/call` 转成 agentd 的 HTTP 请求，把 PNG bytes 包成 `{type:image,...}` 返回给 agent。

为什么不直接复用官方 image 的 Streamlit loop：那是 LLM agent 自己包了一遍 Anthropic API，**它本身不是 MCP server**（见 0.5）。我们要的是把"屏幕"暴露给上层 agent（codex / claude-code）去操作，所以必须自己写桥。

### 4.2 工具集设计（最终 MCP tool 表）

| Tool | 输入 | 输出 |
|---|---|---|
| `computer_screenshot` | （可选）`region` | image/png |
| `computer_click` | `x, y, button="left", count=1` | text 状态 |
| `computer_move` | `x, y` | text |
| `computer_drag` | `x1,y1,x2,y2,duration_ms` | text |
| `computer_type` | `text` | text |
| `computer_key` | `combo`（如 `"ctrl+l"`、`"Return"`） | text |
| `computer_scroll` | `x, y, direction, amount` | text |
| `computer_screen_size` | — | `{width, height}` |
| `computer_bash` | `cmd, timeout_sec=30` | `{stdout, stderr, exit}` |
| `computer_open_url` | `url` | text（在容器 firefox 里打开） |

### 4.3 实施步骤

1. **`servers/computer/Dockerfile.wrapper`** —— 从 `ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest` FROM，叠加 `pip install fastapi uvicorn pillow`，COPY 一个 `agentd.py`，改 entrypoint 把 agentd 一起起来（同时保留原 entrypoint 的 X 服务器）
2. **`servers/computer/wrapper/agentd.py`**（容器内）：
   - FastAPI 路由：`POST /screenshot`（用 `scrot -o /tmp/x.png`）、`POST /click`（`xdotool mousemove X Y && xdotool click 1`）、`POST /type`（`xdotool type --delay 12 -- "$TEXT"`）、`POST /key`（`xdotool key $COMBO`）、`POST /bash`、`GET /size`（`xdpyinfo | grep dimensions`）
   - 监听 `127.0.0.1:9222`（容器内）
   - 每个请求写一行到 `/var/log/agentd.jsonl`
3. **`servers/computer/docker-compose.yml`**：
   - 用我们的 `Dockerfile.wrapper`
   - 端口映射：`5900:5900`、`6080:6080`、`9222:9222`（最后一个 bind `127.0.0.1` 避免外网）
   - volume：`./data:/home/computeruse`（家目录持久化，浏览器 profile/账号会留存）
   - 在 macOS Apple Silicon 上加 `platform: linux/amd64`
4. **`servers/computer/wrapper/mcp_server.py`**（host 上跑）：
   - 用 `mcp` Python SDK（`pip install mcp`）
   - stdio 传输，注册上面 10 个 tool
   - 每个 tool handler `requests.post("http://127.0.0.1:9222/...")`
   - 截图返回 `ImageContent(type="image", data=base64.b64encode(png), mimeType="image/png")`
   - 长任务（拖拽 / bash 30s）用 `notifications/progress`

### 4.4 注册到 CLI

claude-code：
```bash
claude mcp add computer \
  --scope user \
  --transport stdio \
  -- python /Users/cyrus/project/anything-use/servers/computer/wrapper/mcp_server.py
```

codex：
```toml
[mcp_servers.computer]
command = "python"
args = ["/Users/cyrus/project/anything-use/servers/computer/wrapper/mcp_server.py"]
startup_timeout_sec = 120
```

### 4.5 容器启停

- `bash servers/computer/run.sh up` → `docker compose up -d`
- `bash servers/computer/run.sh down` → `docker compose down`
- 浏览器看屏幕：`http://localhost:6080/vnc.html`（人工监督模式）

### 4.6 验收

- `curl localhost:9222/size` 返回 `{"width":1280,"height":800}`
- `curl -X POST localhost:9222/screenshot --output x.png && file x.png` 是有效 PNG
- claude-code: `computer_screenshot` 返回的图片在客户端能看见容器桌面
- 在 noVNC 里你能看到 agent 的鼠标在动
- `logs/computer/<date>.jsonl` 累积条目

---

## Phase 5 — CLI 集成 + 端到端

**目标**：一个脚本把三个 server 都注册进两个 CLI。

### 5.1 `scripts/install-claude-code.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/cyrus/project/anything-use"

claude mcp add browser \
  --scope user --transport stdio \
  -- bash "$ROOT/servers/browser/run.sh"

claude mcp add mobile \
  --scope user --transport stdio \
  --env MOBILEMCP_DISABLE_TELEMETRY=1 \
  -- npx -y @mobilenext/mobile-mcp@latest

claude mcp add computer \
  --scope user --transport stdio \
  -- python "$ROOT/servers/computer/wrapper/mcp_server.py"

claude mcp list
```

### 5.2 `scripts/install-codex.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
CFG="$HOME/.codex/config.toml"
mkdir -p "$HOME/.codex"
[ -f "$CFG" ] || touch "$CFG"

cat >> "$CFG" <<'EOF'

[mcp_servers.browser]
command = "bash"
args = ["/Users/cyrus/project/anything-use/servers/browser/run.sh"]
startup_timeout_sec = 60

[mcp_servers.mobile]
command = "npx"
args = ["-y", "@mobilenext/mobile-mcp@latest"]
env = { MOBILEMCP_DISABLE_TELEMETRY = "1" }
startup_timeout_sec = 60

[mcp_servers.computer]
command = "python"
args = ["/Users/cyrus/project/anything-use/servers/computer/wrapper/mcp_server.py"]
startup_timeout_sec = 120
EOF

echo "Wrote 3 MCP servers into $CFG"
```

⚠️ 这个脚本是 append。第二次跑会重复。后续可改成幂等（用 `tomlkit` 或简单 sed 删段）。

### 5.3 验收（端到端，跨三表面）

让 codex 跑这条 prompt 验收（claude-code 同样）：

> 用 browser 打开一个我的 Twitter 草稿；同时用 mobile 看我手机上的 Twitter app 主页第一条推文；最后在 computer 里 firefox 打开 https://example.com 截屏。三个截图都贴回来。

如果三张截图都返回，说明三个 server 都活的。

---

## Phase 6 — 操作手册 + 持续改进

**目标**：故障 / 升级 / 新机器接入有据可循。

### 6.1 `docs/runbook.md` 必备 section

- **profile 损坏**：删 `servers/browser/profiles/ai-default` 重登
- **手机断连**：`adb kill-server && adb start-server && adb connect $IP:5555`
- **容器卡死**：`docker compose restart`；如果 X 服务器挂了 → `docker compose down -v` 并恢复 `data/` 备份
- **TOTP 不对**：宿主机时钟漂移，`sudo sntp -sS time.apple.com`
- **Google 风控**：账号被锁 → 走 https://accounts.google.com/signin/recovery（恢复码在 1Password）

### 6.2 后续可加的能力（不在初版）

- mobile-extra sidecar（见 3.5）
- iOS 支持（Mac 已有，可接 mobile-mcp 的 iOS 路径）
- 多账号 profile 切换（browser 启动脚本接 `--user-data-dir` 参数化）
- 记录回放（用 Playwright 的 `--save-session` + agentd 的 JSONL 重放）
- 跨 server 的 session 共享（不推荐，见 0.7）

---

## 实施顺序（推荐节拍）

| Phase | 估时 | 阻塞前置 |
|---|---|---|
| 1 仓库+账号 | 半天（多数时间在等 Google 验证） | 实体 SIM 在手 |
| 2 Browser | 1 小时 | Phase 1 |
| 3 Mobile | 半天（factory reset 慢） | Phase 1，空闲手机 |
| 4 Computer | 1-2 天（自写 wrapper） | Phase 1，Docker Desktop |
| 5 集成脚本 | 半小时 | 2/3/4 任一可用即可起步 |
| 6 runbook | 边用边写 | — |

**关键决策检查点**：
- Phase 3 跑完 mobile-mcp 后，**实际用 1 周**，再决定要不要写 mobile-extra sidecar
- Phase 4 的 agentd 路线如果觉得复杂，备选是改用 `nut.js` 在 host 直接控屏（牺牲隔离换简单）—— 不推荐，但作为 fallback 留着

---

## 反 anti-pattern 提醒

- 不要把三个 server 合成一个 monolithic server（已决策）
- 不要用 SSE transport（spec 已 deprecated）
- 不要复制 cookie 跨 surface（会触发 Google 风控）
- 不要在 codex `config.toml` 里写 `mcp-servers`（必须下划线，否则静默失败）
- 不要把 noVNC / agentd 端口 bind 到 `0.0.0.0`（仅 `127.0.0.1`）
- 不要用 `--isolated` 跑长期 profile —— 会丢登录态
- 截图返回**必须**用 `{type:"image", data, mimeType}`，不要塞 base64 字符串到 text content
