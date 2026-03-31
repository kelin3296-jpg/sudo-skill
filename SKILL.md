---
name: sudo
description: 面向 Claude Code 的显式特权工作流，用备份、日志、diff 和安全回滚来降低敏感文件修改时的后顾之忧。支持智能 hook：当 /sudo 激活时自动绕过权限确认。适用于用户输入 /sudo、/sudo exit、/sudo status、/sudo history、/sudo diff、/sudo rollback、/sudo backup-clean、/sudo backup-purge，或需要以可回滚方式处理敏感文件、系统路径和高风险修改的场景。 Use when the user needs a reversible workflow for sensitive file edits and system paths.
---

# /sudo

当用户想要一个 `/sudo` 风格的高风险修改流程，但又希望"出错后有明确退路"时，使用这个 skill。

## 背景

用户真正担心的通常不是命令本身，而是高风险修改之后有没有明确兜底：

- 敏感文件改坏了怎么撤回
- 系统路径动了之后如何留痕
- shell history 不足以承担 rollback 的责任
- 进入特权模式后，用户会天然担心自己要为善后兜底

## 它解决什么问题

- 给 `/sudo` 这类高风险修改补上一条可追溯、可回滚的后路
- 在修改前记录备份，在修改后保留日志与 diff
- 用对象校验阻止不安全的 destructive rollback
- 让用户在进入特权工作流时少一些后顾之忧

## 兜底方案

如果改完之后不放心，优先：

1. 看 `/sudo diff`
2. 查 `/sudo history`
3. 在对象仍匹配时回滚最近活跃操作
4. 必要时检查 `~/.claude/sudo-backups/` 和 `~/.claude/sudo-logs/`

这个 skill **不会**自动绕过 Claude Code 的沙箱，也不会自动帮你修改 bash 参数；它真正负责的是：记录状态、备份、diff 和可审计的回滚元数据。

如果用户问安装，优先参考仓库 `README.md` 里的中文安装提示词，让用户可以直接复制发给 Claude Code。

## 命令映射

- `/sudo` -> `python ~/.claude/skills/sudo/sudo.py enter`
- `/sudo exit` -> `python ~/.claude/skills/sudo/sudo.py exit`
- `/sudo status` -> `python ~/.claude/skills/sudo/sudo.py status`
- `/sudo history [n]` -> `python ~/.claude/skills/sudo/sudo.py history [n]`
- `/sudo rollback [n]` -> `python ~/.claude/skills/sudo/sudo.py rollback [n]`
- `/sudo diff [path|n]` -> `python ~/.claude/skills/sudo/sudo.py diff [path|n]`
- `/sudo backup-clean` -> `python ~/.claude/skills/sudo/sudo.py clean --days 7`
- `/sudo backup-purge` -> `python ~/.claude/skills/sudo/sudo.py purge`

## 可用的 /sudo 子命令

### 用户常用命令
- `/sudo` - 进入显式特权工作流
- `/sudo exit` - 退出特权工作流
- `/sudo status` - 查看当前状态、备份统计和日志位置
- `/sudo history [n]` - 显示最近 n 条操作记录（默认 20 条）
- `/sudo diff [path|n]` - 显示指定路径或历史序号的变更差异
- `/sudo rollback [n]` - 回滚最近 n 条活跃操作（默认 1 条）
- `/sudo backup-clean` - 清理 7 天前的旧备份
- `/sudo backup-purge` - 清空所有备份和日志

### 内部记录命令（供 skill 集成使用）
- `/sudo log-modify <path>` - 记录文件修改前状态
- `/sudo finalize-modify <path>` - 完成文件修改记录
- `/sudo log-delete <path>` - 记录文件删除前状态
- `/sudo log-create <path>` - 记录文件创建后状态
- `/sudo log-move <src> <dst>` - 记录文件移动
- `/sudo log-chmod <path> <old_mode> <new_mode>` - 记录权限变更

## 高风险修改前怎么记录

### 修改文件

1. 修改前运行 `python ~/.claude/skills/sudo/sudo.py log-modify <path>`
2. 执行修改
3. 修改完成后运行 `python ~/.claude/skills/sudo/sudo.py finalize-modify <path>`

### 删除文件

1. 删除前运行 `python ~/.claude/skills/sudo/sudo.py log-delete <path>`
2. 再执行删除

### 创建文件

1. 先创建文件
2. 创建后运行 `python ~/.claude/skills/sudo/sudo.py log-create <path>`

### 移动或重命名文件

1. 先执行移动
2. 完成后运行 `python ~/.claude/skills/sudo/sudo.py log-move <src> <dst>`

### 修改权限

1. 先记录旧权限
2. 执行 chmod
3. 运行 `python ~/.claude/skills/sudo/sudo.py log-chmod <path> <old_mode_octal> <new_mode_octal>`

## 智能权限自动放行（可选）

可以配置 Claude Code 的 hook，让 `/sudo` 激活时自动绕过权限确认：

1. 在 `~/.claude/settings.json` 中添加：
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|Read|Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.claude/skills/sudo/check_sudo_hook.py",
            "statusMessage": "Checking /sudo state..."
          }
        ]
      }
    ]
  }
}
```

2. 配置后：
   - `/sudo` 激活时 → 自动允许所有工具调用
   - `/sudo` 未激活时 → 正常权限流程

## 使用原则

- `/sudo` 表示进入"显式特权工作流"，配合 hook 可实现自动提权
- 敏感变更完成后，先看 `/sudo diff`，再决定是否回滚
- 如果当前对象已经和记录时不一致，回滚应拒绝 destructive 操作
- 即使在 `/sudo` 下，`rm -rf` 这类命令仍建议额外确认
