#!/usr/bin/env python3
"""
自动点击 Claude Code 的 "Allow" 按钮。

使用方法:
    python auto_allow.py start   # 后台启动自动点击
    python auto_allow.py stop    # 停止自动点击
    python auto_allow.py status  # 查看状态
"""

import sys
import os
import time
import subprocess
import signal
from pathlib import Path

PID_FILE = Path.home() / ".claude" / "sudo-auto-allow.pid"

def is_pyautogui_installed():
    """检查 PyAutoGUI 是否已安装"""
    try:
        import pyautogui
        return True
    except ImportError:
        return False

def install_pyautogui():
    """安装 PyAutoGUI"""
    print("正在安装 PyAutoGUI...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui"], check=True)
    print("PyAutoGUI 安装完成")

def find_and_click_allow():
    """查找并点击 Allow 按钮"""
    try:
        import pyautogui

        # 在屏幕上查找 "Allow" 文字
        # 注意：这需要 "Allow" 按钮在屏幕上可见
        location = pyautogui.locateOnScreen('Allow', confidence=0.7)

        if location:
            # 点击按钮中心
            center = pyautogui.center(location)
            pyautogui.click(center)
            return True

        # 如果没找到文字，尝试找常见的按钮位置
        # 通常 Allow 按钮在屏幕底部或中央
        screen_width, screen_height = pyautogui.size()

        # 尝试点击屏幕中央偏下位置（常见对话框位置）
        pyautogui.click(screen_width // 2, screen_height * 0.7)

        return False

    except Exception as e:
        # 静默失败，不要影响主程序
        return False

def run_daemon():
    """后台运行自动点击"""
    try:
        import pyautogui

        # 禁用 PyAutoGUI 的故障保护（防止鼠标移到角落时退出）
        pyautogui.FAILSAFE = False

        # 写入 PID 文件
        PID_FILE.write_text(str(os.getpid()))

        allow_count = 0

        while True:
            if find_and_click_allow():
                allow_count += 1
                # 记录日志（可选）
                log_dir = Path.home() / ".claude" / "sudo-logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "auto_allow.log"
                with open(log_file, "a") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Clicked Allow (#{allow_count})\n")

            # 每 500ms 检查一次
            time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()

def start_daemon():
    """启动后台进程"""
    if not is_pyautogui_installed():
        print("PyAutoGUI 未安装，需要先安装")
        try:
            install_pyautogui()
        except Exception as e:
            print(f"安装失败: {e}")
            print("请手动运行: pip install pyautogui")
            sys.exit(1)

    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text())
            os.kill(pid, 0)  # 检查进程是否存在
            print(f"Auto-allow daemon already running (PID: {pid})")
            return
        except (OSError, ValueError):
            # 进程不存在，删除旧的 PID 文件
            PID_FILE.unlink()

    # 启动新进程
    subprocess.Popen(
        [sys.executable, __file__, "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    # 等待 PID 文件创建
    for _ in range(10):
        if PID_FILE.exists():
            pid = PID_FILE.read_text()
            print(f"Auto-allow daemon started (PID: {pid})")
            return
        time.sleep(0.1)

    print("Auto-allow daemon started")

def stop_daemon():
    """停止后台进程"""
    if not PID_FILE.exists():
        print("Auto-allow daemon not running")
        return

    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, signal.SIGTERM)
        print(f"Auto-allow daemon stopped (PID: {pid})")
    except (OSError, ValueError) as e:
        print(f"Error stopping daemon: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()

def show_status():
    """显示状态"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text())
            os.kill(pid, 0)
            print(f"Auto-allow daemon is running (PID: {pid})")
            return
        except (OSError, ValueError):
            pass

    print("Auto-allow daemon is not running")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: auto_allow.py [start|stop|status]")
        print("")
        print("Commands:")
        print("  start   - Start auto-allow daemon")
        print("  stop    - Stop auto-allow daemon")
        print("  status  - Show daemon status")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        start_daemon()
    elif command == "stop":
        stop_daemon()
    elif command == "status":
        show_status()
    elif command == "--daemon":
        run_daemon()
    else:
        print(f"Unknown command: {command}")
        print("Usage: auto_allow.py [start|stop|status]")
        sys.exit(1)
