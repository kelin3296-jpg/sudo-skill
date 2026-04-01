#!/usr/bin/env python3
"""
Bash 工具包装器 - 在 sudo 模式下自动添加 dangerouslyDisableSandbox。

使用方法：
1. 设置环境变量：export CLAUDE_BASH_WRAPPER=1
2. 启动 Claude Code
3. /sudo 进入特权模式
4. 所有 Bash 调用将自动绕过权限确认
"""

import os
import sys
import json


def is_sudo_active() -> bool:
    """检查 sudo 模式是否激活。"""
    state_file = os.path.expanduser("~/.claude/sudo-state.json")
    if not os.path.exists(state_file):
        return False
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
            return state.get("active", False)
    except Exception:
        return False


def wrap_bash_command(original_command: dict) -> dict:
    """包装 Bash 命令，在 sudo 模式下添加 dangerouslyDisableSandbox。"""
    if not is_sudo_active():
        return original_command

    # 克隆原始命令
    wrapped = dict(original_command)

    # 添加绕过沙箱的标志
    # 注意：这只能在工具层面工作，Claude Code 可能仍会在更上层拦截
    wrapped["dangerouslyDisableSandbox"] = True

    # 记录包装日志
    log_dir = os.path.expanduser("~/.claude/sudo-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bash_wrapper.log")

    with open(log_file, "a") as f:
        f.write(f"[SUDO ACTIVE] Wrapped command: {original_command.get('command', 'N/A')[:100]}...\n")

    return wrapped


def main():
    """主函数 - 作为命令行工具使用。"""
    if len(sys.argv) < 2:
        print("Usage: bash_wrapper.py '<bash_command>'")
        print("\nEnvironment variables:")
        print("  SUDO_ACTIVE=1    - Force sudo mode on")
        sys.exit(1)

    command = sys.argv[1]

    # 构建 Bash 工具调用结构
    original = {
        "command": command,
        "description": f"Executing (sudo mode: {is_sudo_active()})"
    }

    # 包装命令
    wrapped = wrap_bash_command(original)

    # 输出结果
    print("Original:")
    print(json.dumps(original, indent=2))
    print("\nWrapped:")
    print(json.dumps(wrapped, indent=2))

    # 如果 sudo 激活，可以执行命令
    if is_sudo_active():
        print("\n[SUDO MODE] Command would execute without confirmation prompts")
    else:
        print("\n[NORMAL MODE] Command may require confirmation")


if __name__ == "__main__":
    main()
