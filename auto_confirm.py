#!/usr/bin/env python3
"""
权限确认自动应答器 - 在 sudo 模式下自动点击 "Allow" 按钮。

原理：监听 Claude Code 的确认对话框，自动点击 "Allow"。
"""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path


PID_FILE = Path.home() / ".claude" / "sudo-auto-confirm.pid"


def is_macos() -> bool:
    return sys.platform == "darwin"


def click_allow_macos():
    """使用 AppleScript 点击 Allow 按钮。"""
    script = '''
    tell application "System Events"
        tell process "Claude Code"
            try
                -- 查找 "Allow" 按钮并点击
                click button "Allow" of window 1
                return "clicked"
            on error
                return "not found"
            end try
        end tell
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.stdout.strip() == "clicked"
    except Exception:
        return False


def find_and_click_allow():
    """查找并点击 Allow 按钮。"""
    if is_macos():
        return click_allow_macos()
    else:
        # Linux 可以用 xdotool，暂时不支持
        return False


def run_auto_confirm():
    """主循环：持续监听并点击 Allow。"""
    # 写入 PID 文件
    PID_FILE.write_text(str(os.getpid()))

    print(f"[sudo-auto-confirm] Started (PID: {os.getpid()})")
    print("[sudo-auto-confirm] Listening for 'Allow' buttons...")

    try:
        while True:
            if find_and_click_allow():
                print("[sudo-auto-confirm] Clicked 'Allow'")
            time.sleep(0.5)  # 每 500ms 检查一次
    except KeyboardInterrupt:
        print("\n[sudo-auto-confirm] Stopped")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def start():
    """启动后台进程。"""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text())
            # 检查进程是否还在运行
            os.kill(old_pid, 0)
            print(f"[sudo-auto-confirm] Already running (PID: {old_pid})")
            return
        except (OSError, ValueError):
            # 进程不存在了
            pass

    # 启动新进程
    subprocess.Popen(
        [sys.executable, __file__, "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    print("[sudo-auto-confirm] Started in background")


def stop():
    """停止后台进程。"""
    if not PID_FILE.exists():
        print("[sudo-auto-confirm] Not running")
        return

    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, signal.SIGTERM)
        print(f"[sudo-auto-confirm] Stopped (PID: {pid})")
    except (OSError, ValueError) as e:
        print(f"[sudo-auto-confirm] Error stopping: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            start()
        elif sys.argv[1] == "stop":
            stop()
        elif sys.argv[1] == "--daemon":
            run_auto_confirm()
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: auto_confirm.py [start|stop]")
    else:
        print("Usage: auto_confirm.py [start|stop]")
        print("")
        print("Commands:")
        print("  start  - Start background auto-confirm daemon")
        print("  stop   - Stop the daemon")
