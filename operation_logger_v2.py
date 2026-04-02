#!/usr/bin/env python3
"""改进的操作日志系统 - 添加 SQLite、并发控制和快照优化."""

from __future__ import annotations

import difflib
import gzip
import hashlib
import json
import os
import sqlite3
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from concurrency_manager import ConcurrencyManager
from snapshot_engine import SnapshotEngine
from backup_strategy import BackupStrategy

DEFAULT_HOME_DIRNAME = ".claude"
BACKUP_DIRNAME = "sudo-backups"
LOG_DIRNAME = "sudo-logs"
STATE_FILENAME = "sudo-state.json"
DB_FILENAME = "operations.db"


def resolve_skill_home() -> Path:
    override = os.environ.get("SUDO_SKILL_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / DEFAULT_HOME_DIRNAME


def resolve_backup_dir() -> Path:
    return resolve_skill_home() / BACKUP_DIRNAME


def resolve_log_dir() -> Path:
    return resolve_skill_home() / LOG_DIRNAME


def resolve_state_file() -> Path:
    return resolve_skill_home() / STATE_FILENAME


def resolve_db_file() -> Path:
    return resolve_skill_home() / DB_FILENAME


def ensure_storage_dirs() -> None:
    resolve_backup_dir().mkdir(parents=True, exist_ok=True)
    resolve_log_dir().mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_path(path: str | Path, *, include_hash: bool = True) -> dict[str, Any]:
    """创建文件快照."""
    target = Path(path).expanduser()
    normalized = normalize_path(target)
    if not target.exists():
        return {"path": normalized, "exists": False}

    stat_result = target.stat()
    snapshot = {
        "path": normalized,
        "exists": True,
        "kind": "directory" if target.is_dir() else "file" if target.is_file() else "other",
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "mode": stat_result.st_mode,
    }
    if target.is_file() and include_hash:
        snapshot["sha256"] = hash_file(target)
    return snapshot


def snapshots_match(current: dict[str, Any] | None, expected: dict[str, Any] | None) -> bool:
    """比较快照是否匹配."""
    if not current or not expected:
        return False
    if bool(current.get("exists")) != bool(expected.get("exists")):
        return False
    if not expected.get("exists"):
        return True

    for key in ("kind", "size", "mtime_ns", "mode"):
        if expected.get(key) != current.get(key):
            return False

    expected_hash = expected.get("sha256")
    if expected_hash is not None and current.get("sha256") != expected_hash:
        return False
    return True


def format_snapshot(snapshot: dict[str, Any] | None) -> str:
    """格式化快照为可读字符串."""
    if not snapshot:
        return "<missing snapshot>"
    if not snapshot.get("exists"):
        return f"{snapshot.get('path')} (missing)"
    return (
        f"{snapshot.get('path')} | kind={snapshot.get('kind')} | size={snapshot.get('size')} | "
        f"mtime_ns={snapshot.get('mtime_ns')} | sha256={snapshot.get('sha256', 'n/a')}"
    )


class OperationLogger:
    """改进的操作日志系统 - 支持 SQLite、并发和快照优化."""

    def __init__(self):
        ensure_storage_dirs()
        self.skill_home = resolve_skill_home()
        self.backup_dir = resolve_backup_dir()
        self.log_dir = resolve_log_dir()
        self.db_path = resolve_db_file()
        
        # 初始化并发管理
        self.concurrency = ConcurrencyManager(self.skill_home)
        
        # 初始化备份策略
        self.backup_strategy = BackupStrategy(self.backup_dir)
        
        # 初始化数据库
        self._init_database()
        
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.today_backup_dir = self.backup_dir / self.today
        self.today_backup_dir.mkdir(parents=True, exist_ok=True)
        self.deleted_dir = self.today_backup_dir / "deleted-files"
        self.deleted_dir.mkdir(parents=True, exist_ok=True)
        self.today_log_file = self.log_dir / f"{self.today}.jsonl"
        
        # 将现有的 JSONL 日志迁移到数据库
        self._migrate_jsonl_to_db()
        
        # 从数据库加载操作
        self.operations = self._load_operations()
    
    def _init_database(self):
        """初始化 SQLite 数据库."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT,
                    src_path TEXT,
                    dst_path TEXT,
                    state TEXT DEFAULT 'active',
                    rolled_back_at TEXT,
                    rollback_txn_id INTEGER,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引以加快查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON operations(path);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON operations(type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON operations(timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_state ON operations(state);")
            
            conn.commit()
    
    def _migrate_jsonl_to_db(self):
        """将旧的 JSONL 日志迁移到数据库."""
        with self.concurrency.acquire_operations_lock():
            for log_file in sorted(self.log_dir.glob("*.jsonl")):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f if line.strip()]
                    
                    if not lines:
                        continue
                    
                    with sqlite3.connect(self.db_path) as conn:
                        for line in lines:
                            op = json.loads(line)
                            
                            # 检查是否已存在
                            existing = conn.execute(
                                "SELECT id FROM operations WHERE id = ?",
                                (op.get("id"),)
                            ).fetchone()
                            
                            if existing:
                                continue
                            
                            # 插入到数据库
                            conn.execute("""
                                INSERT INTO operations 
                                (id, timestamp, type, path, src_path, dst_path, state, metadata)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                op.get("id"),
                                op.get("timestamp"),
                                op.get("type"),
                                op.get("path"),
                                op.get("src_path"),
                                op.get("dst_path"),
                                op.get("state", "active"),
                                json.dumps(op, ensure_ascii=False)
                            ))
                        
                        conn.commit()
                except Exception as e:
                    print(f"Migration error for {log_file}: {e}")
    
    def _load_operations(self) -> list[dict[str, Any]]:
        """从数据库加载操作."""
        operations = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, timestamp, type, path, metadata FROM operations ORDER BY id"
            ).fetchall()
            
            for row_id, timestamp, op_type, path, metadata in rows:
                op = json.loads(metadata) if metadata else {}
                op["id"] = row_id
                op["timestamp"] = timestamp
                op["type"] = op_type
                op["path"] = path
                operations.append(op)
        
        return operations
    
    def _next_operation_id(self) -> int:
        """获取下一个操作 ID."""
        if not self.operations:
            return 1
        return max(int(op.get("id", 0)) for op in self.operations) + 1
    
    def _append_operation(self, op: dict[str, Any]) -> int:
        """添加操作到日志."""
        with self.concurrency.acquire_operations_lock():
            op["id"] = self._next_operation_id()
            op["timestamp"] = iso_now()
            op.setdefault("state", "active")
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO operations
                    (id, timestamp, type, path, src_path, dst_path, state, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    op["id"],
                    op["timestamp"],
                    op.get("type"),
                    op.get("path"),
                    op.get("src_path"),
                    op.get("dst_path"),
                    op.get("state"),
                    json.dumps(op, ensure_ascii=False)
                ))
                conn.commit()
            
            self.operations.append(op)
            return int(op["id"])
    
    def query_operations(self,
                        path: Optional[str] = None,
                        op_type: Optional[str] = None,
                        state: str = "active",
                        limit: int = 100) -> list[dict[str, Any]]:
        """查询操作 - 使用 SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM operations WHERE state = ?"
            params = [state]
            
            if path:
                query += " AND path = ?"
                params.append(normalize_path(path))
            
            if op_type:
                query += " AND type = ?"
                params.append(op_type)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            # 转换为字典
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'type': row[2],
                    'path': row[3],
                    'metadata': json.loads(row[7]) if row[7] else {}
                })
            
            return results
    
    def get_backup_size(self) -> int:
        """获取备份总大小."""
        total = 0
        for file_path in self.backup_dir.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    def get_backup_count(self) -> int:
        """获取备份文件数量."""
        count = 0
        for file_path in self.backup_dir.rglob("*"):
            if file_path.is_file():
                count += 1
        return count

    def backup_status(self) -> dict[str, Any]:
        """获取备份状态."""
        storage = self.backup_strategy.estimate_storage_usage()
        return {
            "skill_home": str(self.skill_home),
            "backup_dir": str(self.backup_dir),
            "log_dir": str(self.log_dir),
            "db_path": str(self.db_path),
            "backup_files": self.get_backup_count(),
            "backup_size": self.get_backup_size(),
            "log_files": len(list(self.log_dir.glob("*.jsonl"))),
            "operations": len(self.operations),
            "storage_details": storage,
        }

    def _make_backup_path(self, filepath: Path, suffix: str = ".gz", deleted: bool = False) -> Path:
        """生成备份文件路径."""
        timestamp = datetime.now().strftime("%H%M%S%f")
        safe_name = filepath.name[:100] or "unnamed"
        base_dir = self.deleted_dir if deleted else self.today_backup_dir
        return base_dir / f"{safe_name}.{timestamp}{suffix}"

    def backup_file(self, filepath: str | Path, *, deleted: bool = False) -> dict[str, Any] | None:
        """备份文件."""
        target = Path(filepath).expanduser()
        if not target.exists() or not target.is_file():
            return None

        with self.concurrency.acquire_operations_lock():
            backup_path = self._make_backup_path(target, deleted=deleted)
            with open(target, "rb") as src, gzip.open(backup_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            with open(target, "rb") as handle:
                sample = handle.read(8192)
            content_kind = "binary" if b"\0" in sample else "text"
            return {
                "original_path": normalize_path(target),
                "file_size": target.stat().st_size,
                "storage": "gzip-original",
                "content_kind": content_kind,
                "backup_path": str(backup_path),
                "original_hash": hash_file(target),
            }

    def log_modify(self, filepath: str | Path) -> int:
        """记录文件修改前的状态."""
        target = Path(filepath).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"Cannot log modify for missing file: {target}")
        
        backup = self.backup_file(target)
        op = {
            "type": "modify",
            "path": normalize_path(target),
            "pre_snapshot": snapshot_path(target),
            "post_snapshot": None,
            "backup": backup,
        }
        return self._append_operation(op)

    def finalize_modify(self, filepath: str | Path, operation_id: int | None = None) -> int:
        """记录文件修改后的状态."""
        target = normalize_path(filepath)
        
        if operation_id is None:
            for op in reversed(self.operations):
                if (op.get("type") == "modify" and 
                    op.get("path") == target and 
                    op.get("state") == "active" and 
                    not op.get("post_snapshot")):
                    operation_id = int(op["id"])
                    break
        
        if operation_id is None:
            raise ValueError(f"No pending modify operation found for {target}")

        with self.concurrency.acquire_operations_lock():
            for op in self.operations:
                if op["id"] == operation_id:
                    op["post_snapshot"] = snapshot_path(target)
                    op["finalized_at"] = iso_now()
                    
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            UPDATE operations SET metadata = ? WHERE id = ?
                        """, (json.dumps(op, ensure_ascii=False), operation_id))
                        conn.commit()
                    break
        
        return operation_id

    def log_delete(self, filepath: str | Path) -> int:
        """记录文件删除."""
        target = Path(filepath).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"Cannot log delete for missing file: {target}")
        op = {
            "type": "delete",
            "path": normalize_path(target),
            "pre_snapshot": snapshot_path(target),
            "backup": self.backup_file(target, deleted=True),
        }
        return self._append_operation(op)

    def log_create(self, filepath: str | Path) -> int:
        """记录文件创建."""
        target = Path(filepath).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"Cannot log create for missing file: {target}")
        op = {
            "type": "create",
            "path": normalize_path(target),
            "post_snapshot": snapshot_path(target),
        }
        return self._append_operation(op)

    def log_move(self, src_path: str | Path, dst_path: str | Path) -> int:
        """记录文件移动."""
        destination = Path(dst_path).expanduser()
        if not destination.exists():
            raise FileNotFoundError(f"Cannot log move for missing destination: {destination}")
        op = {
            "type": "move",
            "src_path": normalize_path(src_path),
            "dst_path": normalize_path(destination),
            "dst_snapshot": snapshot_path(destination),
        }
        return self._append_operation(op)

    def log_chmod(self, filepath: str | Path, old_mode: int, new_mode: int) -> int:
        """记录权限修改."""
        target = Path(filepath).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"Cannot log chmod for missing path: {target}")
        op = {
            "type": "chmod",
            "path": normalize_path(target),
            "old_mode": int(old_mode),
            "new_mode": int(new_mode),
            "post_snapshot": snapshot_path(target, include_hash=False),
        }
        return self._append_operation(op)

    def recent_operations(self, limit: int = 20, *, active_only: bool = False) -> list[dict[str, Any]]:
        """获取最近的操作."""
        operations = [op for op in self.operations if not active_only or op.get("state") != "rolled_back"]
        return list(reversed(operations[-limit:]))

    def format_history(self, limit: int = 20) -> str:
        """格式化历史记录."""
        lines = ["Recent operations:"]
        recent = self.recent_operations(limit)
        if not recent:
            return "Recent operations:\n  (none)"

        for index, op in enumerate(recent, start=1):
            state = op.get("state", "active")
            path = op.get("path") or op.get("dst_path") or op.get("description", "")
            lines.append(
                f"  [{index}] state={state:<11} type={op.get('type', 'unknown'):<7} time={op.get('timestamp', 'n/a')} target={path}"
            )
        return "\n".join(lines)

    def _operation_by_id(self, operation_id: int) -> dict[str, Any] | None:
        """按 ID 获取操作."""
        for op in self.operations:
            if int(op["id"]) == operation_id:
                return op
        return None

    def cleanup_old_backups(self, days: int = 7) -> dict:
        """清理旧备份."""
        return self.backup_strategy.cleanup_old_backups(days=days)

    def _read_gzip_bytes(self, path: Path) -> bytes:
        with gzip.open(path, "rb") as handle:
            return handle.read()

    def _decode_text(self, data: bytes) -> str | None:
        for encoding in ("utf-8", "latin-1", "utf-16"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None
