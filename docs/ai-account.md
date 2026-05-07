# AI 账号建立手册

为 anything-use 准备一个**专门的** Google 账号，独立于你日常账号。
全程预计 30-60 分钟（多数时间在等 Google 验证）。

## 前置准备

- [ ] 一张能收 SMS 的实体 SIM 卡（Google Voice / 接码平台命中率低，不建议）
- [ ] 1Password 已登录、CLI `op` 可用：`op signin && op whoami`
- [ ] 一台干净的电脑或浏览器 profile（推荐：用 Phase 2 即将建立的 `servers/browser/profiles/ai-default` 这个目录作为 Chrome user data dir 走注册）

## 步骤

### 1. 在 1Password 里建条目占位
名称：`AI / Google Master`
字段：username, password（先空着）, recovery email（可选）, OTP（一次性密码 secret，注册时填入）, recovery codes

### 2. 注册 Google 账号
1. 用即将作为 Browser server profile 的目录启动一个干净的 Chrome：
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --user-data-dir=/Users/cyrus/project/anything-use/servers/browser/profiles/ai-default
   ```
2. 访问 https://accounts.google.com/signup
3. 用 1Password 生成强密码（≥16 字符），保存到上面的条目
4. 用实体 SIM 完成手机验证

### 3. 立刻开 2FA
1. https://myaccount.google.com/security → 2-Step Verification → 开启
2. 添加 **Authenticator app**
3. 屏幕上扫码那一步，**不要扫**，点 "Can't scan it?" 拿到文字 secret
4. 在 1Password 条目里 OTP 字段粘贴这个 secret（1Password 自动开始生成 6 位码）
5. 用 1Password 当前显示的码完成 Google 的验证

### 4. 备份恢复码
1. 同一页面 → "Show backup codes" → 生成 10 个
2. 全部复制进 1Password 条目的 `recovery codes` 字段（每行一个）
3. 这是账号丢失时唯一的兜底，**离开浏览器前确认已存**

### 5. 关闭无人值守不需要的功能
- 关闭"账号活动通知到手机"
- 关闭"添加备用电话提醒"（Google 会反复推这个）
- 不绑定第二个手机号

### 6. 验证 CLI 取 TOTP 通畅
```bash
op item get "AI / Google Master" --otp
# 应输出 6 位数字
```

### 7. 把这个账号也用到 Phase 3 的手机上
factory-reset 后第一次开机 setup wizard 用这个账号登录。
TOTP 在手机上输入时，回到 Mac 跑上一行 op 命令拿码。

## 风险与对策

| 场景 | 怎么办 |
|---|---|
| Google 风控锁号 | 走 https://accounts.google.com/signin/recovery；恢复码已存 1Password |
| Mac 时钟漂移 → TOTP 不对 | `sudo sntp -sS time.apple.com` |
| 实体 SIM 不在身边 | 注册前确认；Google 一年内可能多次要求重新验证手机号 |
| 想换 password manager | TOTP secret 直接迁移到新 vault；Google 会用现有 OTP 重新验证 |

## 不要做的

- ❌ 不要把这个账号的 cookie 跨设备复制（会触发 Google 风控）
- ❌ 不要把密码或 TOTP secret 写到任何文件或仓库
- ❌ 不要给账号绑你的日常手机号 / 备用邮箱
