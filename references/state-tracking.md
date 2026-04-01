# 特权模式状态管理

## 状态存储

特权模式状态存储在临时文件中：
- 文件路径：`/tmp/claude-sudo-mode-{session_id}`
- 或者环境变量：`CLAUDE_SUDO_MODE`

## 状态值

- `active` - 特权模式已激活
- `inactive` 或文件不存在 - 特权模式未激活

## 切换流程

### 进入特权模式
1. 用户输入 `/sudo`
2. 创建状态文件或设置环境变量
3. 显示确认消息："特权模式已激活"

### 退出特权模式
1. 用户输入 `/sudo exit` 或 `/exit`
2. 删除状态文件或清除环境变量
3. 显示确认消息："已退出特权模式"

## 自动 bypass 实现

由于 Claude Code 的架构限制，特权模式无法通过 hooks 自动修改 Bash 工具的参数。

**实际使用方式：**
当特权模式激活时，Claude 应该在每次调用 Bash 时主动添加 `dangerouslyDisableSandbox: true`。

这需要在 SKILL.md 的指令中明确说明：
```
当特权模式处于激活状态时，所有 Bash 工具调用必须包含 dangerouslyDisableSandbox: true
```
