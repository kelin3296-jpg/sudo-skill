---
name: sudo
description: 面向 Claude Code 的显式特权工作流，用备份、日志、diff 和安全回滚来降低敏感文件修改时的后顾之忧。适用于用户输入 /sudo、/sudo exit、/sudo history、/sudo rollback，或需要以可回滚方式处理敏感文件、系统路径和高风险修改的场景。 Use when the user needs a reversible workflow for sensitive file edits and system paths.
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

- `/sudo` -> `python3 ~/.claude/skills/sudo/sudo.py enter`
- `/sudo exit` -> `python3 ~/.claude/skills/sudo/sudo.py exit`
- `/sudo status` -> `python3 ~/.claude/skills/sudo/sudo.py status`
- `/sudo history [n]` -> `python3 ~/.claude/skills/sudo/sudo.py history [n]`
- `/sudo rollback [n]` -> `python3 ~/.claude/skills/sudo/sudo.py rollback [n]`
- `/sudo diff [path|n]` -> `python3 ~/.claude/skills/sudo/sudo.py diff [path|n]`
- `/sudo backup-clean` -> `python3 ~/.claude/skills/sudo/sudo.py clean --days 7`
- `/sudo backup-purge` -> `python3 ~/.claude/skills/sudo/sudo.py purge`

## 高风险修改前怎么记录

### 修改文件

1. 修改前运行 `python3 ~/.claude/skills/sudo/sudo.py log-modify <path>`
2. 执行修改
3. 修改完成后运行 `python3 ~/.claude/skills/sudo/sudo.py finalize-modify <path>`

### 删除文件

1. 删除前运行 `python3 ~/.claude/skills/sudo/sudo.py log-delete <path>`
2. 再执行删除

### 创建文件

1. 先创建文件
2. 创建后运行 `python3 ~/.claude/skills/sudo/sudo.py log-create <path>`

### 移动或重命名文件

1. 先执行移动
2. 完成后运行 `python3 ~/.claude/skills/sudo/sudo.py log-move <src> <dst>`

### 修改权限

1. 先记录旧权限
2. 执行 chmod
3. 运行 `python3 ~/.claude/skills/sudo/sudo.py log-chmod <path> <old_mode_octal> <new_mode_octal>`

## 使用原则

- `/sudo` 只表示进入"显式特权工作流"，不是自动提权
- 敏感变更完成后，先看 `/sudo diff`，再决定是否回滚
- 如果当前对象已经和记录时不一致，回滚应拒绝 destructive 操作
- 即使在 `/sudo` 下，`rm -rf` 这类命令仍需要额外确认
