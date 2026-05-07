# Computer-use 准备手册

让 AI agent 操作一个**沙盒化**的 Linux 桌面（跑在 Docker 容器里）。
原理：Anthropic 官方 computer-use 镜像 + 我们写的 `agentd` HTTP sidecar + 主机侧 stdio MCP wrapper。

> 这是三个 surface 里**最重**的一块。装 + 跑通预计 30-60 分钟，主要时间在第一次拉镜像（amd64 镜像在 Apple Silicon 上 ~3GB + Rosetta 翻译）。

## 你需要

- **Docker Desktop**（macOS/Windows）或 docker engine + compose v2（Linux）
  - macOS：https://www.docker.com/products/docker-desktop/
  - 配置足够内存：Settings → Resources → Memory ≥ 4 GB
  - 在 Apple Silicon 上：Settings → General → Use Rosetta for x86/amd64 emulation = on
- **Python 3.10+** + pip（host 上跑 MCP wrapper）
- 至少 ~5 GB 磁盘（镜像 ~3 GB + persistent volume）

## 一次性设置

### 1. 装 host 侧 Python 依赖

```bash
cd anything-use
python3 -m pip install --user -r servers/computer/wrapper/requirements.txt
# 或者用 venv（推荐）：
python3 -m venv .venv && source .venv/bin/activate
pip install -r servers/computer/wrapper/requirements.txt
```

如果用 venv，把它的 `python3` 路径填给 install 脚本：

```bash
PY="$(pwd)/.venv/bin/python3" bash scripts/install-claude-code.sh    # （需要你手改脚本支持 PY 变量）
```

最简单的路：用系统 `python3`，全局装包。

### 2. 启动容器

```bash
bash servers/computer/run.sh up
# 第一次会编译镜像，~5 分钟
# 完成后会打印 "agentd is up"
```

### 3. 看一眼桌面

打开 http://localhost:6080/vnc.html  
点 **Connect** → 你应该看到一个 1280×800 的 Linux 桌面，里面有 Firefox / LibreOffice / 终端等。

这个 noVNC 窗口是给**人类**看的（监督 AI 的操作）。AI 不通过它工作，AI 通过 agentd HTTP API。

### 4. 注册 MCP server

```bash
bash scripts/install-claude-code.sh
# 或 codex
bash scripts/install-codex.sh
```

新开一个 claude-code / codex 会话，让它跑：
```
computer_health           # 应输出 OK 和分辨率
computer_screenshot       # 应返回一张容器桌面截图
computer_open_url https://example.com
computer_screenshot       # 应该看到 Firefox 已经打开
```

## 工具列表

| Tool | 作用 |
|---|---|
| `computer_health` | 心跳 + 屏幕尺寸 |
| `computer_screen_size` | `{width, height}` |
| `computer_screenshot` | 当前桌面 PNG |
| `computer_click(x, y, button, count)` | 鼠标点击 |
| `computer_move(x, y)` | 移动鼠标 |
| `computer_drag(x1,y1,x2,y2,duration_ms)` | 拖拽 |
| `computer_type(text, delay_ms)` | 在焦点处打字 |
| `computer_key(combo)` | 按键 / 组合键，如 `"ctrl+l"` `"Return"` |
| `computer_scroll(x, y, direction, amount)` | 滚轮 |
| `computer_bash(cmd, timeout_sec)` | 在容器里跑命令 |
| `computer_open_url(url)` | Firefox 打开 URL |

## 架构速览

```
claude-code / codex (host)
        │ stdio (MCP)
        ▼
servers/computer/wrapper/mcp_server.py   ← 你刚装的 Python
        │ HTTP (127.0.0.1:9222)
        ▼
┌──────────────────────────────────────┐
│  Docker container (anything-use-     │
│    computer)                          │
│                                       │
│  /opt/agentd/agentd.py  ← FastAPI    │
│    └─ xdotool, scrot, bash           │
│                                       │
│  Xvfb :1 + mutter + tint2            │
│    └─ Firefox, LibreOffice, etc.     │
│                                       │
│  x11vnc → noVNC at :6080 (human)     │
└──────────────────────────────────────┘
```

端口表（全部 bind 在 `127.0.0.1`，**不要改成 0.0.0.0** 除非加认证）：

| 端口 | 谁用 |
|---|---|
| 5900 | 直连 VNC（Mac 上 Finder → Connect to Server `vnc://localhost:5900`） |
| 6080 | noVNC web，给人 |
| 8080 | 上游官方 demo 的 chat+desktop UI（没用上，但留着方便调试） |
| 8501 | 上游 Streamlit 应用（同上） |
| 9222 | **agentd**，AI 实际用的 |

## 故障排查

| 现象 | 解决 |
|---|---|
| `run.sh up` 卡在 "Waiting for agentd" | `docker compose logs` 看是不是 X 启动失败；通常是内存不够（设到 4GB+） |
| `computer_health` → "agentd not reachable" | 容器没起；`./run.sh status` 验证 |
| 截图全黑 | X 还没起完；等 5 秒重试。或者 Firefox 没启动 → `computer_open_url` 试试 |
| Apple Silicon 上特别慢 | 正常，amd64 模拟开销大；考虑减少 WIDTH/HEIGHT 到 1024×768 |
| `pip install mcp` 失败 | Python ≥ 3.10 才有 mcp 包；用 `python3 --version` 确认 |
| 中文输入乱码 | 容器 locale 问题，进 `./run.sh shell` 跑 `locale-gen zh_CN.UTF-8` |

## 安全提示

- agentd 没鉴权（绑 127.0.0.1 是唯一防线）。**不要把 9222 暴露公网**
- 容器是个完整 Linux 桌面，agent 在里面**等同 root**（容器内）。沙盒边界是 Docker，不是用户权限
- 如果你不想容器有外网访问，docker-compose.yml 加 `network_mode: none` 然后只通过 host 的 `bash` 工具下发任务。会损失 Firefox 联网，但更安全
- 持久化的 `./data/` 目录里会留 Firefox profile / 缓存。**别在容器里登录你的私人账号**

## 卸载

```bash
bash servers/computer/run.sh down
docker rmi anything-use/computer:latest   # 可选，删本地镜像
rm -rf servers/computer/data              # 删持久化数据
```
