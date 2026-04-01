#!/usr/bin/env python3
"""Internal logging, backup, diff, and rollback helpers for sudo skill."""

from __future__ import annotations

import difflib
import gzip
import hashlib
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_HOME_DIRNAME = ".claude"
BACKUP_DIRNAME = "sudo-backups"
LOG_DIRNAME = "sudo-logs"
STATE_FILENAME = "sudo-state.json"


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


def ensure_storage_dirs() -> None:
    resolve_backup_dir().mkdir(parents=True, exist_ok=True)
    resolve_log_dir().mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().absolute())


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_path(path: str | Path, *, include_hash: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    normalized = normalize_path(target)
    if not target.exists():
        return {"path": normalized, "exists": False}

    stat_result = target.stat()
    snapshot: dict[str, Any] = {
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
    if not snapshot:
        return "<missing snapshot>"
    if not snapshot.get("exists"):
        return f"{snapshot.get('path')} (missing)"
    return (
        f"{snapshot.get('path')} | kind={snapshot.get('kind')} | size={snapshot.get('size')} | "
        f"mtime_ns={snapshot.get('mtime_ns')} | sha256={snapshot.get('sha256', 'n/a')}"
    )


class OperationLogger:
    """Track reversible file operations for the sudo skill."""

    def __init__(self) -> None:
        ensure_storage_dirs()
        self.skill_home = resolve_skill_home()
        self.backup_dir = resolve_backup_dir()
        self.log_dir = resolve_log_dir()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.today_backup_dir = self.backup_dir / self.today
        self.today_backup_dir.mkdir(parents=True, exist_ok=True)
        self.deleted_dir = self.today_backup_dir / "deleted-files"
        self.deleted_dir.mkdir(parents=True, exist_ok=True)
        self.today_log_file = self.log_dir / f"{self.today}.jsonl"
        self.operations = self._load_operations()

    def _load_operations(self) -> list[dict[str, Any]]:
        operations: list[dict[str, Any]] = []
        next_id = 1
        for log_file in sorted(self.log_dir.glob("*.jsonl")):
            with open(log_file, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    op = json.loads(raw_line)
                    if "id" not in op:
                        op["id"] = next_id
                    next_id = max(next_id, int(op["id"]) + 1)
                    op.setdefault("state", "active")
                    op.setdefault("rolled_back_at", None)
                    op.setdefault("rollback_txn_id", None)
                    op["_log_file"] = str(log_file)
                    operations.append(op)
        operations.sort(key=lambda item: (item.get("timestamp", ""), int(item.get("id", 0))))
        return operations

    def _next_operation_id(self) -> int:
        if not self.operations:
            return 1
        return max(int(op.get("id", 0)) for op in self.operations) + 1

    def _serialize_operation(self, op: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in op.items() if not key.startswith("_")}

    def _rewrite_logs(self) -> None:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for op in self.operations:
            grouped[op["_log_file"]].append(op)

        for log_file, items in grouped.items():
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                for item in items:
                    handle.write(json.dumps(self._serialize_operation(item), ensure_ascii=False) + "\n")

    def _append_operation(self, op: dict[str, Any]) -> int:
        op["id"] = self._next_operation_id()
        op["timestamp"] = iso_now()
        op.setdefault("state", "active")
        op.setdefault("rolled_back_at", None)
        op.setdefault("rollback_txn_id", None)
        op["_log_file"] = str(self.today_log_file)
        self.operations.append(op)
        with open(self.today_log_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(self._serialize_operation(op), ensure_ascii=False) + "\n")
        return int(op["id"])

    def get_backup_size(self) -> int:
        total = 0
        for file_path in self.backup_dir.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    def get_backup_count(self) -> int:
        count = 0
        for file_path in self.backup_dir.rglob("*"):
            if file_path.is_file():
                count += 1
        return count

    def backup_status(self) -> dict[str, Any]:
        return {
            "skill_home": str(self.skill_home),
            "backup_dir": str(self.backup_dir),
            "log_dir": str(self.log_dir),
            "backup_files": self.get_backup_count(),
            "backup_size": self.get_backup_size(),
            "log_files": len(list(self.log_dir.glob("*.jsonl"))),
            "operations": len(self.operations),
        }

    def _make_backup_path(self, filepath: Path, suffix: str = ".gz", deleted: bool = False) -> Path:
        timestamp = datetime.now().strftime("%H%M%S%f")
        safe_name = filepath.name[:100] or "unnamed"
        base_dir = self.deleted_dir if deleted else self.today_backup_dir
        return base_dir / f"{safe_name}.{timestamp}{suffix}"

    def backup_file(self, filepath: str | Path, *, deleted: bool = False) -> dict[str, Any] | None:
        target = Path(filepath).expanduser()
        if not target.exists() or not target.is_file():
            return None

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
        target = normalize_path(filepath)
        if operation_id is None:
            for op in reversed(self.operations):
                if op.get("type") == "modify" and op.get("path") == target and op.get("state") == "active" and not op.get("post_snapshot"):
                    operation_id = int(op["id"])
                    break
        if operation_id is None:
            raise ValueError(f"No pending modify operation found for {target}")

        operation = self._operation_by_id(operation_id)
        operation["post_snapshot"] = snapshot_path(target)
        operation["finalized_at"] = iso_now()
        self._rewrite_logs()
        return operation_id

    def log_delete(self, filepath: str | Path) -> int:
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
        operations = [op for op in self.operations if not active_only or op.get("state") != "rolled_back"]
        return list(reversed(operations[-limit:]))

    def format_history(self, limit: int = 20) -> str:
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

    def resolve_operation_for_diff(self, target: str | None = None) -> dict[str, Any]:
        candidates = [
            op
            for op in reversed(self.operations)
            if op.get("type") in {"modify", "create", "delete", "move", "chmod"}
        ]
        if not candidates:
            raise ValueError("No recorded operations available for diff")

        if target is None:
            return candidates[0]

        if target.isdigit():
            index = int(target)
            recent = self.recent_operations(index)
            if len(recent) < index:
                raise ValueError(f"History index out of range: {target}")
            return recent[index - 1]

        normalized = normalize_path(target)
        for op in candidates:
            if op.get("path") == normalized or op.get("dst_path") == normalized:
                return op
        raise ValueError(f"No recorded operation found for path: {normalized}")

    def build_diff_report(self, target: str | None = None) -> str:
        op = self.resolve_operation_for_diff(target)
        op_type = op.get("type")
        if op_type != "modify":
            return self._build_non_modify_report(op)
        return self._build_modify_report(op)

    def _build_non_modify_report(self, op: dict[str, Any]) -> str:
        lines = [f"Operation type: {op.get('type')}"]
        for key in ("path", "src_path", "dst_path"):
            if key in op:
                lines.append(f"{key}: {op[key]}")
        if "pre_snapshot" in op:
            lines.append(f"pre_snapshot: {format_snapshot(op['pre_snapshot'])}")
        if "post_snapshot" in op:
            lines.append(f"post_snapshot: {format_snapshot(op['post_snapshot'])}")
        if "dst_snapshot" in op:
            lines.append(f"dst_snapshot: {format_snapshot(op['dst_snapshot'])}")
        return "\n".join(lines)

    def _build_modify_report(self, op: dict[str, Any]) -> str:
        path = Path(op["path"])
        backup = op.get("backup") or {}
        backup_path = Path(backup["backup_path"])
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file is missing: {backup_path}")

        before_bytes = self._read_gzip_bytes(backup_path)
        current_exists = path.exists()
        current_bytes = path.read_bytes() if current_exists and path.is_file() else b""

        if not current_exists:
            return (
                f"Current file is missing: {path}\n"
                f"Stored backup: {backup_path}\n"
                f"Original hash: {backup.get('original_hash', 'n/a')}"
            )

        before_text = self._decode_text(before_bytes)
        current_text = self._decode_text(current_bytes)
        if before_text is not None and current_text is not None:
            diff = list(
                difflib.unified_diff(
                    before_text.splitlines(),
                    current_text.splitlines(),
                    fromfile=f"before:{path}",
                    tofile=f"current:{path}",
                    lineterm="",
                )
            )
            if not diff:
                return f"No content difference for {path}."
            return "\n".join(diff)

        return "\n".join(
            [
                f"Binary file summary for {path}",
                f"  backup_path: {backup_path}",
                f"  original_hash: {backup.get('original_hash', 'n/a')}",
                f"  current_hash: {hash_file(path)}",
                f"  original_size: {backup.get('file_size', 'n/a')}",
                f"  current_size: {path.stat().st_size}",
            ]
        )

    def _read_gzip_bytes(self, backup_path: Path) -> bytes:
        with gzip.open(backup_path, "rb") as handle:
            return handle.read()

    def _decode_text(self, content: bytes) -> str | None:
        if b"\0" in content[:8192]:
            return None
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _operation_by_id(self, operation_id: int) -> dict[str, Any]:
        for op in self.operations:
            if int(op.get("id", 0)) == int(operation_id):
                return op
        raise ValueError(f"Unknown operation id: {operation_id}")

    def _mark_rolled_back(self, op: dict[str, Any], rollback_txn_id: str) -> None:
        op["state"] = "rolled_back"
        op["rolled_back_at"] = iso_now()
        op["rollback_txn_id"] = rollback_txn_id

    def rollback(self, n: int = 1) -> tuple[bool, list[str]]:
        if n <= 0:
            return False, ["Please specify a rollback count greater than 0."]

        targets = self.recent_operations(n, active_only=True)
        if len(targets) < n:
            return False, [f"Only found {len(targets)} active operation(s); cannot rollback {n}."]

        messages: list[str] = []
        rollback_txn_id = datetime.now().strftime("rollback-%Y%m%d%H%M%S%f")
        success = True
        for op in targets:
            ok, op_messages = self._rollback_one(op, rollback_txn_id)
            messages.extend(op_messages)
            success = success and ok

        self._rewrite_logs()
        return success, messages

    def _rollback_one(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        if op.get("state") == "rolled_back":
            return False, [f"Operation already rolled back: {op.get('type')} {op.get('path', '')}"]

        op_type = op.get("type")
        if op_type == "modify":
            return self._rollback_modify(op, rollback_txn_id)
        if op_type == "delete":
            return self._rollback_delete(op, rollback_txn_id)
        if op_type == "create":
            return self._rollback_create(op, rollback_txn_id)
        if op_type == "move":
            return self._rollback_move(op, rollback_txn_id)
        if op_type == "chmod":
            return self._rollback_chmod(op, rollback_txn_id)
        return False, [f"Unsupported rollback type: {op_type}"]

    def _rollback_modify(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        path = Path(op["path"])
        pre_snapshot = op.get("pre_snapshot")
        post_snapshot = op.get("post_snapshot")
        backup_path = Path((op.get("backup") or {}).get("backup_path", ""))
        current_snapshot = snapshot_path(path)

        if snapshots_match(current_snapshot, pre_snapshot):
            self._mark_rolled_back(op, rollback_txn_id)
            return True, [f"Modify already matches backup: {path}"]
        if not post_snapshot:
            return False, [f"Modify rollback requires finalize-modify metadata: {path}"]
        if not snapshots_match(current_snapshot, post_snapshot):
            return False, [f"Refusing to overwrite changed file during rollback: {path}"]
        if not backup_path.exists():
            return False, [f"Backup is missing for modify rollback: {backup_path}"]

        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(backup_path, "rb") as src, open(path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        self._mark_rolled_back(op, rollback_txn_id)
        return True, [f"Rolled back modify: {path}"]

    def _rollback_delete(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        path = Path(op["path"])
        backup_path = Path((op.get("backup") or {}).get("backup_path", ""))
        if path.exists():
            if snapshots_match(snapshot_path(path), op.get("pre_snapshot")):
                self._mark_rolled_back(op, rollback_txn_id)
                return True, [f"Delete already restored: {path}"]
            return False, [f"Refusing to restore delete over existing path: {path}"]
        if not backup_path.exists():
            return False, [f"Backup is missing for delete rollback: {backup_path}"]

        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(backup_path, "rb") as src, open(path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        self._mark_rolled_back(op, rollback_txn_id)
        return True, [f"Restored deleted file: {path}"]

    def _rollback_create(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        path = Path(op["path"])
        current_snapshot = snapshot_path(path)
        post_snapshot = op.get("post_snapshot")
        if not current_snapshot.get("exists"):
            self._mark_rolled_back(op, rollback_txn_id)
            return True, [f"Create already removed: {path}"]
        if not snapshots_match(current_snapshot, post_snapshot):
            return False, [f"Refusing to remove a changed file created later: {path}"]
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        self._mark_rolled_back(op, rollback_txn_id)
        return True, [f"Rolled back create: {path}"]

    def _rollback_move(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        src_path = Path(op["src_path"])
        dst_path = Path(op["dst_path"])
        dst_snapshot = op.get("dst_snapshot")
        if src_path.exists():
            return False, [f"Refusing to rollback move because source already exists: {src_path}"]
        if not dst_path.exists():
            self._mark_rolled_back(op, rollback_txn_id)
            return True, [f"Move already reversed or destination missing: {dst_path}"]
        if not snapshots_match(snapshot_path(dst_path), dst_snapshot):
            return False, [f"Refusing to move back a changed destination: {dst_path}"]

        src_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst_path), str(src_path))
        self._mark_rolled_back(op, rollback_txn_id)
        return True, [f"Rolled back move: {dst_path} -> {src_path}"]

    def _rollback_chmod(self, op: dict[str, Any], rollback_txn_id: str) -> tuple[bool, list[str]]:
        path = Path(op["path"])
        if not path.exists():
            return False, [f"Cannot rollback chmod for missing path: {path}"]
        path.chmod(int(op["old_mode"]))
        self._mark_rolled_back(op, rollback_txn_id)
        return True, [f"Rolled back chmod: {path}"]
