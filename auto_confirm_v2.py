#!/usr/bin/env python3
"""改进的自动确认机制 - 更可靠的 Allow 按钮自动化."""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path
import json
from typing import Optional, List, Tuple


PID_FILE = Path.home() / ".claude" / "sudo-auto-confirm.pid"
LOG_FILE = Path.home() / ".claude" / "sudo-auto-confirm.log"
STATE_FILE = Path.home() / ".claude" / "sudo-auto-confirm-state.json"


def is_macos() -> bool:
    return sys.platform == "darwin"


def click_allow_macos_improved():
    """改进的 AppleScript 版本 - 增加重试和回滚."""
    attempt = 0
    max_attempts = 3
    
    while attempt < max_attempts:
        script = '''
        on click_button(btn_name)
            try
                tell application "System Events"
                    -- 尝试所有可能的应用名称
                    set app_names to {"Code", "Claude", "VSCodium", "Visual Studio Code", "VS Code"}
                    repeat with app_name in app_names
                        try
                            tell process app_name
                                set windowList to windows
                                repeat with win in windowList
                                    try
                                        -- 尝试查找按钮
                                        set btn to (first button of win whose name is btn_name)
                                        click btn
                                        return {"status": "clicked", "app": app_name, "button": btn_name}
                                    end try
                                end repeat
                            end tell
                        on error
                            -- 继续下一个应用
                        end try
                    end repeat
                    return {"status": "not_found"}
                end tell
            on error err
                return {"status": "error", "message": err}
            end try
        end on
        
        click_button("Allow")
        '''
        
        try:
            result = subprocess.run(
                ["osascript", "-",],
                input=script,
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                return True
            
            attempt += 1
            time.sleep(0.2)  # 短暂延迟后重试
        except Exception:
            pass
    
    return False


def click_allow_with_fallback():
    """带回滚的点击 Allow 机制."""
    if is_macos():
        # 首先尝试改进的 AppleScript
        if click_allow_macos_improved():
            return True
        
        # 降级到简单版本
        return click_allow_simple_macos()
    
    return False


def click_allow_simple_macos():
    """简单的 AppleScript 版本（向后兼容）."""
    script = '''
    tell application "System Events"
        set appNames to {"Code", "Claude", "VSCodium"}
        set buttonNames to {"Allow", "允许", "是", "Yes"}
        repeat with appName in appNames
            try
                tell process appName
                    set allButtons to buttons of windows
                    repeat with btn in allButtons
                        set btnName to name of btn
                        repeat with targetName in buttonNames
                            if btnName is targetName then
                                click btn
                                return "clicked"
                            end if
                        end repeat
                    end repeat
                end tell
            on error
            end try
        end repeat
        return "not_found"
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


def log_message(message: str, level: str = "INFO"):
    """写日志到文件和 stdout."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    print(log_line, end="")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass


def load_state() -> dict:
    """加载状态文件."""
    if not STATE_FILE.exists():
        return {"click_count": 0, "success_count": 0, "failure_count": 0}
    
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"click_count": 0, "success_count": 0, "failure_count": 0}


def save_state(state: dict):
    """保存状态文件."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_auto_confirm():
    """主循环：持续监听并点击 Allow."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    
    # 清空旧日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    
    log_message(f"Started (PID: {os.getpid()})")
    log_message("✓ Listening for 'Allow' buttons...")
    
    state = load_state()
    check_interval = 0.3  # 300ms 检查间隔（比原来快）
    failed_attempts = 0
    max_failed = 10  # 连续失败 10 次后降速
    
    try:
        while True:
            if click_allow_with_fallback():
                state["click_count"] = state.get("click_count", 0) + 1
                state["success_count"] = state.get("success_count", 0) + 1
                failed_attempts = 0  # 重置失败计数
                check_interval = 0.3  # 恢复快速检查
                
                log_message(
                    f"✓ Clicked 'Allow' (total: {state['click_count']})",
                    level="SUCCESS"
                )
            else:
                failed_attempts += 1
                state["failure_count"] = state.get("failure_count", 0) + 1
                
                # 如果连续失败，降速以减少 CPU 使用
                if failed_attempts > max_failed:
                    check_interval = 0.5
                    failed_attempts = 0  # 重置计数
            
            save_state(state)
            time.sleep(check_interval)
    except KeyboardInterrupt:
        log_message("✓ Stopped by user")
    except Exception as e:
        log_message(f"✗ Error: {e}", level="ERROR")
    finally:
        cleanup()


def cleanup():
    """清理资源."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
        log_message("✓ Cleanup complete")
    except Exception:
        pass


def start():
    """启动后台进程 - 改进的版本."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text())
            # 检查进程是否还在运行
            os.kill(old_pid, 0)
            print(f"✓ [sudo-auto-confirm] Already running (PID: {old_pid})")
            print(f"  Log: {LOG_FILE}")
            return
        except (OSError, ValueError):
            # 进程不存在了
            pass
    
    # 清空旧日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    
    # 启动新进程
    try:
        proc = subprocess.Popen(
            [sys.executable, __file__, "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"✓ [sudo-auto-confirm] Started in background (PID: {proc.pid})")
        print(f"  Log: {LOG_FILE}")
        time.sleep(0.5)  # 让进程有时间启动
    except Exception as e:
        print(f"✗ [sudo-auto-confirm] Failed to start: {e}")


def stop():
    """停止后台进程."""
    if not PID_FILE.exists():
        print("[sudo-auto-confirm] Not running")
        return
    
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, signal.SIGTERM)
        print(f"[sudo-auto-confirm] Stopped (PID: {pid})")
        
        # 等待进程退出
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                break
    except (OSError, ValueError) as e:
        print(f"[sudo-auto-confirm] Error stopping: {e}")
    finally:
        cleanup()


def status():
    """显示自动确认守护进程的状态."""
    if not PID_FILE.exists():
        print("[sudo-auto-confirm] Status: inactive")
        return
    
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, 0)
        print(f"[sudo-auto-confirm] Status: active (PID: {pid})")
        
        state = load_state()
        print(f"  Clicks: {state.get('click_count', 0)}")
        print(f"  Successes: {state.get('success_count', 0)}")
        print(f"  Failures: {state.get('failure_count', 0)}")
        
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
            if lines:
                print(f"  Last log: {lines[-1]}")
    except OSError:
        print("[sudo-auto-confirm] Status: inactive (stale PID file)")


if __name__ == "__main__":
    # 处理信号
    signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "start":
            start()
        elif cmd == "stop":
            stop()
        elif cmd == "status":
            status()
        elif cmd == "--daemon":
            run_auto_confirm()
    else:
        print("Usage: auto_confirm.py {start|stop|status}")
