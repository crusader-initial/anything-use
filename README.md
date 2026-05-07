# anything-use

本地 GUI agent 框架。把 codex 和 claude-code 通过 MCP 接到三种执行表面：

- **Browser** — `@playwright/mcp`（复用）
- **Mobile** — `@mobilenext/mobile-mcp`（复用，Android via ADB+UIAutomator）
- **Computer** — Anthropic computer-use Docker 容器 + 自写 MCP wrapper

完整设计 + 实施 plan 见 [`PLAN.md`](./PLAN.md)。

## 状态

Phase 1 — 仓库骨架完成。后续 phase 待执行：

- [ ] Phase 1: 仓库骨架 + AI 账号 + 1Password secrets
- [ ] Phase 2: Browser MCP（Playwright，复用）
- [ ] Phase 3: Mobile MCP（mobile-mcp，复用）
- [ ] Phase 4: Computer use（Docker 容器 + MCP wrapper）
- [ ] Phase 5: claude-code + codex 集成脚本
- [ ] Phase 6: 操作手册

AI 账号建立步骤见 [`docs/ai-account.md`](./docs/ai-account.md)（需要实体 SIM 收短信）。
