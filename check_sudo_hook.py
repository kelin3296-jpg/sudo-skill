#!/usr/bin/env python3
"""Hook script for Claude Code to check sudo state and auto-allow safe operations."""

import json
import sys
import re
from pathlib import Path


def get_sudo_state() -> dict:
    """Check if sudo mode is active by reading sudo-state.json."""
    skill_home = Path.home() / ".claude"
    state_file = skill_home / "sudo-state.json"

    if not state_file.exists():
        return {"active": False}

    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"active": False}


def is_safe_read_command(command: str) -> bool:
    """
    判断命令是否是安全的文件读取操作。

    安全的读取操作包括：
    - cat, head, tail, less, more
    - grep, awk, sed（只读模式）
    - ls, find（只读）
    - file, stat, md5sum, sha256sum

    危险的操作会被排除：
    - rm, mv, cp（修改）
    - dd, mkfs（磁盘操作）
    - >, >>（重定向写入）
    - | 管道后的修改命令
    """
    if not command or not command.strip():
        return False

    command = command.strip()

    # 危险命令列表（直接拒绝）
    dangerous_patterns = [
        r'\brm\s',           # rm 命令
        r'\bmkfs\.',        # mkfs 格式化
        r'\bdd\s',           # dd 磁盘操作
        r'\bmount\s',       # mount
        r'\bumount\s',      # umount
        r'\bchmod\s',       # chmod（权限修改）
        r'\bchown\s',       # chown（所有者修改）
        r'\bmv\s',          # mv（移动/重命名）
        r'\bcp\s',          # cp（复制，可能覆盖）
        r'>\s*[^>]',         # 重定向写入（不包括 >> 追加）
        r'\|\s*\brm',       # 管道到 rm
        r'\|\s*\bsed\s+-i', # 管道到 sed -i（原地编辑）
        r'sudo\s+',          # sudo（提权命令）
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            return False

    # 安全命令列表（白名单）
    safe_patterns = [
        r'^\s*cat\s',           # cat 查看
        r'^\s*head\s',           # head 查看开头
        r'^\s*tail\s',           # tail 查看结尾
        r'^\s*less\s',          # less 分页查看
        r'^\s*more\s',          # more 分页查看
        r'^\s*grep\s',          # grep 搜索
        r'^\s*awk\s',           # awk 处理（只读）
        r'^\s*sed\s+[^-]*[^i]', # sed 处理（不含 -i 原地编辑）
        r'^\s*ls\s',            # ls 列出
        r'^\s*find\s',          # find 查找
        r'^\s*file\s',          # file 识别类型
        r'^\s*stat\s',          # stat 查看元数据
        r'^\s*md5sum\s',        # md5sum 校验
        r'^\s*sha256sum\s',     # sha256sum 校验
        r'^\s*echo\s',          # echo 输出
        r'^\s*which\s',          # which 查找命令
        r'^\s*whoami\s',         # whoami 查看用户
        r'^\s*pwd\s',            # pwd 查看当前目录
    ]

    for pattern in safe_patterns:
        if re.match(pattern, command):
            return True

    # 默认：不匹配任何已知模式，保守起见返回 False
    return False


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    state = get_sudo_state()
    sudo_active = state.get("active", False)

    # 获取工具信息
    tool_name = input_data.get("tool", "")
    tool_input = input_data.get("input", {})

    # 如果 sudo 激活且是 Bash 工具，检查命令是否安全
    if sudo_active and tool_name == "Bash":
        command = tool_input.get("command", "")

        if is_safe_read_command(command):
            # 安全的读取操作，自动授权
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "/sudo mode active: safe read command auto-allowed"
                },
                "systemMessage": "/sudo active: auto-allowed safe read command"
            }
            json.dump(output, sys.stdout, ensure_ascii=False)
            print()
            return
        else:
            # 危险命令，让 Claude Code 自己决定（通常会要求确认）
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "continue",
                    "permissionDecisionReason": "/sudo mode active but command requires verification"
                },
                "systemMessage": "/sudo active: command requires manual verification"
            }
            json.dump(output, sys.stdout, ensure_ascii=False)
            print()
            return

    if sudo_active:
        # Sudo 激活但非 Bash 工具，或其他情况
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "continue",
                "permissionDecisionReason": "/sudo mode is active"
            },
            "systemMessage": "/sudo active"
        }
    else:
        # Sudo not active - let normal permission flow continue
        output = {
            "continue": True
        }

    # Output JSON for Claude Code
    json.dump(output, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
