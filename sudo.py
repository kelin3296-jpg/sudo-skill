#!/usr/bin/env python3
"""Unified CLI for the Claude Code sudo skill."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from operation_logger import OperationLogger, ensure_storage_dirs, iso_now, resolve_state_file


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def load_state() -> dict:
    state_file = resolve_state_file()
    if not state_file.exists():
        return {"active": False}
    return json.loads(state_file.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    ensure_storage_dirs()
    state_file = resolve_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_dangerously_skip_permissions() -> bool:
    """Detect if Claude Code was started with --dangerously-skip-permissions."""
    try:
        import psutil
        try:
            parent = psutil.Process().parent()
            if parent:
                cmdline = " ".join(parent.cmdline())
                return "--dangerously-skip-permissions" in cmdline
        except Exception:
            pass
    except ImportError:
        pass
    return False


def start_auto_confirm():
    """启动自动确认后台进程。"""
    script_path = Path(__file__).parent / "auto_confirm.py"
    if script_path.exists():
        try:
            subprocess.run(
                [sys.executable, str(script_path), "start"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass  # 静默失败，不影响主流程


def stop_auto_confirm():
    """停止自动确认后台进程。"""
    script_path = Path(__file__).parent / "auto_confirm.py"
    if script_path.exists():
        try:
            subprocess.run(
                [sys.executable, str(script_path), "stop"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass


def enter_mode() -> int:
    state = load_state()
    if state.get("active"):
        print("/sudo is already active.")
        print(f"Entered at: {state.get('entered_at', 'unknown')}")
        return 0

    # Check if running with --dangerously-skip-permissions
    skip_perms = is_dangerously_skip_permissions()

    state = {
        "active": True,
        "entered_at": iso_now(),
        "mode": "explicit",
        "dangerously_skip_permissions": skip_perms,
        "note": (
            "The skill tracks state, backups, and rollback metadata. It does not automatically "
            "change Claude Code sandbox or bash tool parameters."
        ),
    }
    save_state(state)

    # 启动自动确认后台进程
    if not skip_perms:
        start_auto_confirm()

    print("Entered /sudo explicit privileged workflow.")

    if skip_perms:
        print("✓ Running with --dangerously-skip-permissions: all commands execute without confirmation.")
    else:
        print("✓ Auto-confirm daemon started: 'Allow' buttons will be clicked automatically.")
        print("  (To stop auto-confirm, run: /sudo exit)")

    return 0


def exit_mode() -> int:
    state = load_state()
    if not state.get("active"):
        print("/sudo is already inactive.")
        return 0

    # 停止自动确认后台进程
    stop_auto_confirm()

    save_state({"active": False, "exited_at": iso_now()})
    print("Exited /sudo workflow.")
    print("✓ Auto-confirm daemon stopped.")
    return 0


def show_status() -> int:
    logger = OperationLogger()
    state = load_state()
    summary = logger.backup_status()

    print("sudo skill status")
    print("=" * 60)
    print(f"workflow_active : {state.get('active', False)}")
    if state.get("entered_at"):
        print(f"entered_at      : {state['entered_at']}")
    print(f"skill_home      : {summary['skill_home']}")
    print(f"backup_dir      : {summary['backup_dir']}")
    print(f"log_dir         : {summary['log_dir']}")
    print(f"backup_files    : {summary['backup_files']}")
    print(f"backup_size     : {format_size(summary['backup_size'])}")
    print(f"log_files       : {summary['log_files']}")
    print(f"operations      : {summary['operations']}")
    print("=" * 60)
    return 0


def clean_old_backups(days: int) -> int:
    logger = OperationLogger()
    cutoff_name = []
    removed_count = 0
    removed_bytes = 0

    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)
    for item in logger.backup_dir.iterdir():
        if not item.is_dir():
            continue
        try:
            item_date = datetime.strptime(item.name, "%Y-%m-%d")
        except ValueError:
            continue
        if item_date < cutoff:
            removed_bytes += sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            shutil.rmtree(item)
            removed_count += 1
            cutoff_name.append(item.name)

    print(f"Removed {removed_count} backup directorie(s), freed {format_size(removed_bytes)}.")
    if cutoff_name:
        print("Removed:")
        for name in cutoff_name:
            print(f"  - {name}")
    return 0


def purge_all(assume_yes: bool) -> int:
    logger = OperationLogger()
    if not assume_yes:
        confirm = input("Type YES to purge backups and logs: ")
        if confirm != "YES":
            print("Cancelled.")
            return 1

    removed_size = logger.get_backup_size()
    if logger.backup_dir.exists():
        shutil.rmtree(logger.backup_dir)
    if logger.log_dir.exists():
        shutil.rmtree(logger.log_dir)
    state_file = resolve_state_file()
    if state_file.exists():
        state_file.unlink()
    ensure_storage_dirs()
    print(f"Purged backups, logs, and workflow state. Freed {format_size(removed_size)}.")
    return 0


def show_history(limit: int) -> int:
    logger = OperationLogger()
    print(logger.format_history(limit))
    return 0


def rollback(n: int, assume_yes: bool) -> int:
    logger = OperationLogger()
    if not assume_yes:
        confirm = input(f"Rollback the most recent {n} active operation(s)? Type yes to continue: ")
        if confirm.strip().lower() != "yes":
            print("Cancelled.")
            return 1
    ok, messages = logger.rollback(n)
    for message in messages:
        print(message)
    return 0 if ok else 1


def show_diff(target: str | None) -> int:
    logger = OperationLogger()
    print(logger.build_diff_report(target))
    return 0


def show_auto_log() -> int:
    """显示 auto-confirm 日志。"""
    from pathlib import Path
    log_file = Path.home() / ".claude" / "sudo-auto-confirm.log"
    if not log_file.exists():
        print("[sudo-auto-confirm] No log file found")
        return 0

    print("=" * 60)
    print("sudo-auto-confirm log")
    print("=" * 60)
    print(log_file.read_text(encoding="utf-8"))
    print("=" * 60)
    return 0


def log_modify(path: str) -> int:
    logger = OperationLogger()
    op_id = logger.log_modify(path)
    print(f"Recorded modify operation #{op_id} for {Path(path).expanduser().absolute()}")
    print("Run `python sudo.py finalize-modify <path>` after the file has been changed.")
    return 0


def finalize_modify(path: str, operation_id: int | None) -> int:
    logger = OperationLogger()
    op_id = logger.finalize_modify(path, operation_id)
    print(f"Finalized modify operation #{op_id} for {Path(path).expanduser().absolute()}")
    return 0


def log_delete(path: str) -> int:
    logger = OperationLogger()
    op_id = logger.log_delete(path)
    print(f"Recorded delete operation #{op_id} for {Path(path).expanduser().absolute()}")
    return 0


def log_create(path: str) -> int:
    logger = OperationLogger()
    op_id = logger.log_create(path)
    print(f"Recorded create operation #{op_id} for {Path(path).expanduser().absolute()}")
    return 0


def log_move(src: str, dst: str) -> int:
    logger = OperationLogger()
    op_id = logger.log_move(src, dst)
    print(f"Recorded move operation #{op_id}: {Path(src).expanduser().absolute()} -> {Path(dst).expanduser().absolute()}")
    return 0


def log_chmod(path: str, old_mode: str, new_mode: str) -> int:
    logger = OperationLogger()
    old_value = int(old_mode, 8) if isinstance(old_mode, str) else int(old_mode)
    new_value = int(new_mode, 8) if isinstance(new_mode, str) else int(new_mode)
    op_id = logger.log_chmod(path, old_value, new_value)
    print(f"Recorded chmod operation #{op_id} for {Path(path).expanduser().absolute()} ({oct(old_value)} -> {oct(new_value)})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="sudo skill CLI for Claude Code")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("enter", help="Enter the explicit /sudo workflow")
    subparsers.add_parser("exit", help="Exit the /sudo workflow")
    subparsers.add_parser("status", help="Show workflow state, backup stats, and log locations")

    clean_parser = subparsers.add_parser("clean", help="Remove backup directories older than N days")
    clean_parser.add_argument("--days", type=int, default=7)

    purge_parser = subparsers.add_parser("purge", help="Delete all backups and logs")
    purge_parser.add_argument("--yes", action="store_true")

    history_parser = subparsers.add_parser("history", help="Show recent operations")
    history_parser.add_argument("limit", nargs="?", type=int, default=20)

    rollback_parser = subparsers.add_parser("rollback", help="Rollback the most recent active operations")
    rollback_parser.add_argument("count", nargs="?", type=int, default=1)
    rollback_parser.add_argument("--yes", action="store_true")

    diff_parser = subparsers.add_parser("diff", help="Show diff by path or recent history index")
    diff_parser.add_argument("target", nargs="?")

    subparsers.add_parser("auto-log", help="Show the auto-confirm daemon log")

    log_modify_parser = subparsers.add_parser("log-modify", help="Record a file before it is modified")
    log_modify_parser.add_argument("path")

    finalize_modify_parser = subparsers.add_parser("finalize-modify", help="Capture the post-change snapshot for a modified file")
    finalize_modify_parser.add_argument("path")
    finalize_modify_parser.add_argument("--id", type=int, dest="operation_id")

    log_delete_parser = subparsers.add_parser("log-delete", help="Record a file before deletion")
    log_delete_parser.add_argument("path")

    log_create_parser = subparsers.add_parser("log-create", help="Record a file after creation")
    log_create_parser.add_argument("path")

    log_move_parser = subparsers.add_parser("log-move", help="Record a file move after it completes")
    log_move_parser.add_argument("src")
    log_move_parser.add_argument("dst")

    log_chmod_parser = subparsers.add_parser("log-chmod", help="Record a chmod after it completes")
    log_chmod_parser.add_argument("path")
    log_chmod_parser.add_argument("old_mode")
    log_chmod_parser.add_argument("new_mode")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "enter":
        return enter_mode()
    if args.command == "exit":
        return exit_mode()
    if args.command == "status":
        return show_status()
    if args.command == "clean":
        return clean_old_backups(args.days)
    if args.command == "purge":
        return purge_all(args.yes)
    if args.command == "history":
        return show_history(args.limit)
    if args.command == "rollback":
        return rollback(args.count, args.yes)
    if args.command == "diff":
        return show_diff(args.target)
    if args.command == "auto-log":
        return show_auto_log()
    if args.command == "log-modify":
        return log_modify(args.path)
    if args.command == "finalize-modify":
        return finalize_modify(args.path, args.operation_id)
    if args.command == "log-delete":
        return log_delete(args.path)
    if args.command == "log-create":
        return log_create(args.path)
    if args.command == "log-move":
        return log_move(args.src, args.dst)
    if args.command == "log-chmod":
        return log_chmod(args.path, args.old_mode, args.new_mode)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
