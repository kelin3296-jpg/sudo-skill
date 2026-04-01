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
LOG_FILE = Path.home() / ".claude" / "sudo-auto-confirm.log"


def is_macos() -> bool:
    return sys.platform == "darwin"


def click_allow_macos():
    """使用 AppleScript 点击 Allow/Yes 按钮。"""
    script = '''
    tell application "System Events"
        -- 尝试多个可能的应用程序
        set appNames to {"Claude Code", "Code", "Visual Studio Code", "VSCodium"}
        set buttonNames to {"Allow", "允许", "Yes", "是"}
        repeat with appName in appNames
            try
                tell process appName
                    -- 尝试查找所有窗口中的按钮
                    try
                        set allWindows to windows
                        repeat with win in allWindows
                            try
                                set allButtons to buttons of win
                                repeat with btn in allButtons
                                    set btnName to name of btn
                                    repeat with targetName in buttonNames
                                        if btnName is targetName then
                                            click btn
                                            return "clicked"
                                        end if
                                    end repeat
                                end repeat
                            end try
                        end repeat
                    end try
                end tell
            on error
                -- 这个应用没有运行，继续下一个
            end try
        end repeat
        return "not found"
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
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


def log_message(message: str):
    """写日志到文件和 stdout。"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass


def run_auto_confirm():
    """主循环：持续监听并点击 Allow。"""
    # 写入 PID 文件
    PID_FILE.write_text(str(os.getpid()))

    # 清空旧日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    log_message(f"Started (PID: {os.getpid()})")
    log_message("Listening for 'Allow' buttons...")

    click_count = 0
    try:
        while True:
            if find_and_click_allow():
                click_count += 1
                log_message(f"Clicked 'Allow' (total: {click_count})")
            time.sleep(0.5)  # 每 500ms 检查一次
    except KeyboardInterrupt:
        log_message("Stopped")
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
            print(f"[sudo-auto-confirm] Log file: {LOG_FILE}")
            return
        except (OSError, ValueError):
            # 进程不存在了
            pass

    # 清空旧日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    # 启动新进程
    subprocess.Popen(
        [sys.executable, __file__, "--daemon"],
        stdout=open(LOG_FILE, "w", encoding="utf-8"),
        stderr=open(LOG_FILE, "a", encoding="utf-8"),
        start_new_session=True
    )
    print(f"[sudo-auto-confirm] Started in background")
    print(f"[sudo-auto-confirm] Log file: {LOG_FILE}")


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


def show_log():
    """显示日志。"""
    if not LOG_FILE.exists():
        print("[sudo-auto-confirm] No log file found")
        return

    print("=" * 60)
    print("sudo-auto-confirm log")
    print("=" * 60)
    print(LOG_FILE.read_text(encoding="utf-8"))
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            start()
        elif sys.argv[1] == "stop":
            stop()
        elif sys.argv[1] == "log":
            show_log()
        elif sys.argv[1] == "--daemon":
            run_auto_confirm()
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: auto_confirm.py [start|stop|log]")
    else:
        print("Usage: auto_confirm.py [start|stop|log]")
        print("")
        print("Commands:")
        print("  start  - Start background auto-confirm daemon")
        print("  stop   - Stop the daemon")
        print("  log    - Show the auto-confirm log")
