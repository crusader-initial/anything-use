# Mobile (Android) 准备手册

把一台**空闲**的 Android 手机变成 AI 可控的 GUI agent 设备。
预计一次性投入 30-60 分钟。

> iOS 用户：mobile-mcp 也支持 iOS（通过 WebDriverAgent），但需要 Mac + Xcode + Apple 开发者签名，这份文档不覆盖。本框架的 OSS 重点路径是 Android。

## 你需要

- 一台 Android 手机（Android 8+，推荐 11+，因为 Wi-Fi ADB 配对更顺）
- 一根 USB 数据线（首次配对用）
- Mac/Linux/Windows 任一开发机；本仓库的脚本基于 macOS 测试，Linux 应直接可用，Windows 推荐 WSL2
- （强烈推荐）一个**专门的** Google 账号 — 见 [`ai-account.md`](./ai-account.md)。也可以用你现有账号，但那意味着 agent 会看到你的私人邮件、相册、聊天

## 一次性设置

### 1. 在 Mac 上装 ADB

```bash
brew install --cask android-platform-tools
adb --version   # 校验
```

Linux/Windows: https://developer.android.com/tools/releases/platform-tools

### 2. 准备手机

1. 关机 → 长按音量+ 和电源键进 recovery，**factory reset**（账号会被清掉，谨慎）
2. 开机 setup wizard：
   - 用专门的 Google 账号登录
   - 跳过指纹/面容（biometric 阻碍 ADB 解锁）
   - 跳过广告 ID 之类的隐私选项（无所谓）
3. 设置 → 关于本机 → 连续点 **版本号** 7 次 → 解锁开发者选项
4. 设置 → 系统 → 开发者选项：
   - **USB debugging** = 开
   - **Stay awake**（充电时屏幕保持唤醒）= 开
   - **Disable adb authorization timeout** = 开（避免一段时间不操作就要重新授权）
5. 设置 → 安全 → 屏幕锁定 = **None** 或 **PIN**（不要用图案/指纹/面容）
   - 如果隐私敏感想锁屏，PIN 可以用 ADB 解锁：`adb shell input text $PIN && adb shell input keyevent 66`
6. （强烈推荐，中文/emoji 用户必装）安装 [ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard)：
   ```bash
   # 下载 ADBKeyBoard.apk 到 Mac
   adb install ADBKeyBoard.apk
   adb shell ime list -a
   # 输出里找到 com.android.adbkeyboard/.AdbIME，复制完整 ID
   adb shell ime enable com.android.adbkeyboard/.AdbIME
   adb shell ime set com.android.adbkeyboard/.AdbIME
   ```
   这样 `adb shell input text` 才能正确处理 unicode（默认 IME 不支持中文/emoji）。

### 3. USB 配对

```bash
# 用 USB 接到 Mac
adb devices
# List of devices attached
# ABCDEF12345  device     ← 看到这一行就成功了
```

第一次连会在手机上弹"是否允许此电脑调试"，勾"始终允许"。

### 4. 切到 Wi-Fi（可选但强烈建议）

让手机和 Mac 在**同一个 Wi-Fi 网段**，然后：

```bash
adb tcpip 5555                  # 让手机监听 5555
adb shell ip route | awk '{print $9}'   # 拿手机的 IP，比如 192.168.1.42
adb connect 192.168.1.42:5555
adb devices                     # 应该看到 192.168.1.42:5555  device
# 验证后可以拔 USB
```

Android 11+ 也支持永久无线调试（无需 USB 引导）：手机上 设置 → 开发者选项 → **Wireless debugging** → "Pair device with pairing code" → 拿到 IP+port+code 后：

```bash
adb pair 192.168.1.42:37251 123456
adb connect 192.168.1.42:5555
```

### 5. 验证 mobile-mcp 能看见手机

```bash
npx -y @mobilenext/mobile-mcp@latest --help    # 拉镜像 + 启动测试
# Ctrl-C 退出；只要不报错就行
```

### 6. 注册到 claude-code（或 codex）

在 anything-use repo 里：

```bash
bash scripts/install-claude-code.sh    # 注册到 claude-code（user scope）
# 或
bash scripts/install-codex.sh          # 注册到 codex（~/.codex/config.toml）
```

## 验证一切通了

打开新的 claude-code 会话，让它跑：

```
mobile_list_available_devices
mobile_take_screenshot
mobile_list_elements_on_screen
```

应该返回 1 台设备 + 一张你手机当前画面 + UI 元素列表。

## 故障排查

| 现象 | 解决 |
|---|---|
| `adb devices` 显示 `unauthorized` | 拔重插 USB，手机上重新勾"允许调试" |
| `adb devices` 显示 `offline` | `adb kill-server && adb start-server` |
| Wi-Fi 连一会儿就断 | 关闭手机 Wi-Fi 智能切换；或路由器把这台手机加白 |
| `mobile_take_screenshot` 黑屏 | 屏幕已熄屏 → 设 Stay awake；或 `adb shell input keyevent 26`（电源键唤醒） |
| `mobile_type_keys` 中文变乱码 | 没装/没启用 ADBKeyBoard，回到 §2.6 |
| 手机锁屏后 ADB 不响应 | 正常 — 设 None 或 PIN 锁屏；用 `adb shell input keyevent 82` 唤醒后再 input text 输 PIN |

## 安全提示

这台手机现在等于把控制权交给了 AI agent。建议：

- **不存私密内容**：通讯录、照片、付款账户都搬走
- **专号专机**：不要用日常 Google 账号
- **网络隔离**（可选）：路由器划个 guest VLAN 给它，免得它能横向扫你内网
- **审计**：mobile-mcp 的工具调用会被 claude-code / codex 记到对话日志里；本仓库 `logs/mobile/` 暂未启用，规划见 PLAN.md §6
