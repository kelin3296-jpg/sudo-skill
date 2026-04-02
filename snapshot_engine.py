#!/usr/bin/env python3
"""快照对比优化引擎 - 多层次验证策略."""

import hashlib
from pathlib import Path
from typing import Any, Optional


class SnapshotEngine:
    """智能快照对比 - 先快后精."""
    
    # 块大小常量
    HEADER_SIZE = 4096  # 文件开始 4KB
    FOOTER_SIZE = 4096  # 文件末尾 4KB
    BLOCK_SIZE = 1024 * 1024  # 1MB
    
    @staticmethod
    def hash_file_full(filepath: str | Path) -> str:
        """完整文件 hash (SHA256)."""
        digest = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(SnapshotEngine.BLOCK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()
    
    @staticmethod
    def hash_file_partial(filepath: str | Path) -> dict[str, str]:
        """部分文件 hash - 头、尾、中间各 16KB.
        
        Returns:
            {
                'header': '...hex...',
                'footer': '...hex...',
                'middle': '...hex...'
            }
        """
        hashes = {}
        size = Path(filepath).stat().st_size
        
        digest = hashlib.sha256()
        with open(filepath, 'rb') as f:
            # 头部
            data = f.read(SnapshotEngine.HEADER_SIZE)
            digest.update(data)
            hashes['header'] = digest.hexdigest()
            
            # 中间
            if size > SnapshotEngine.HEADER_SIZE + SnapshotEngine.FOOTER_SIZE:
                f.seek(size // 2)
                digest = hashlib.sha256()
                data = f.read(SnapshotEngine.HEADER_SIZE)
                digest.update(data)
                hashes['middle'] = digest.hexdigest()
            
            # 尾部
            f.seek(-SnapshotEngine.FOOTER_SIZE, 2)
            digest = hashlib.sha256()
            data = f.read(SnapshotEngine.FOOTER_SIZE)
            digest.update(data)
            hashes['footer'] = digest.hexdigest()
        
        return hashes
    
    @staticmethod
    def quick_match(current: dict[str, Any] | None, 
                   expected: dict[str, Any] | None) -> bool:
        """第一层：快速匹配 (mtime, size, mode).
        
        最快的检查方式，适合大多数场景。
        """
        if not current or not expected:
            return False
        
        if bool(current.get("exists")) != bool(expected.get("exists")):
            return False
        
        if not expected.get("exists"):
            return True
        
        # 比较基本属性（这些变化会导致 mtime 改变）
        if current.get("mtime_ns") != expected.get("mtime_ns"):
            return False
        
        if current.get("size") != expected.get("size"):
            return False
        
        if current.get("mode") != expected.get("mode"):
            return False
        
        return True
    
    @staticmethod
    def partial_match(current: dict[str, Any] | None,
                     expected: dict[str, Any] | None) -> bool:
        """第二层：部分匹配 (块级 hash).
        
        快速但不完全的验证，用于大文件。
        """
        if not SnapshotEngine.quick_match(current, expected):
            return False
        
        expected_hashes = expected.get("partial_hashes")
        current_hashes = current.get("partial_hashes")
        
        if not expected_hashes or not current_hashes:
            return True  # 如果没有部分 hash，跳过这层检查
        
        for key in expected_hashes:
            if expected_hashes[key] != current_hashes.get(key):
                return False
        
        return True
    
    @staticmethod
    def full_match(current: dict[str, Any] | None,
                   expected: dict[str, Any] | None) -> bool:
        """第三层：完整匹配 (完整 SHA256).
        
        最精确的验证，用作最终确认。
        """
        if not SnapshotEngine.quick_match(current, expected):
            return False
        
        expected_hash = expected.get("sha256")
        current_hash = current.get("sha256")
        
        if expected_hash is None:
            return True  # 如果没有完整 hash 记录，跳过这层检查
        
        return expected_hash == current_hash
    
    @staticmethod
    def smart_match(current: dict[str, Any] | None,
                   expected: dict[str, Any] | None,
                   depth: int = 0) -> bool:
        """智能提升匹配 - 按需快速检查.
        
        Args:
            current: 当前快照
            expected: 预期快照
            depth: 检查深度 (0=快速, 1=部分, 2=完整)
            
        Returns:
            bool: 是否匹配
        """
        if depth == 0:
            return SnapshotEngine.quick_match(current, expected)
        elif depth == 1:
            return SnapshotEngine.partial_match(current, expected)
        else:
            return SnapshotEngine.full_match(current, expected)
    
    @staticmethod
    def create_snapshot(filepath: str | Path, 
                       include_partial: bool = True,
                       include_full: bool = False) -> dict[str, Any]:
        """创建优化的快照.
        
        Args:
            filepath: 目标文件路径
            include_partial: 是否计算部分 hash
            include_full: 是否计算完整 hash
            
        Returns:
            快照字典
        """
        target = Path(filepath).expanduser()
        normalized = str(target.resolve())
        
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
        
        if target.is_file():
            # 计算部分 hash（默认）
            if include_partial and stat_result.st_size > 0:
                snapshot["partial_hashes"] = SnapshotEngine.hash_file_partial(target)
            
            # 计算完整 hash（可选，耗时）
            if include_full and stat_result.st_size > 0:
                snapshot["sha256"] = SnapshotEngine.hash_file_full(target)
        
        return snapshot
    
    @staticmethod
    def report_mismatch(current: dict[str, Any] | None,
                       expected: dict[str, Any] | None) -> str:
        """生成详细的不匹配报告.
        
        Returns:
            人类可读的不匹配原因
        """
        if not current and not expected:
            return "Both snapshots are None"
        
        if not current:
            return "Current snapshot is missing"
        
        if not expected:
            return "Expected snapshot is missing"
        
        if current.get("exists") != expected.get("exists"):
            return f"Existence mismatch: current={current.get('exists')}, expected={expected.get('exists')}"
        
        if not expected.get("exists"):
            return "File does not exist (expected)"
        
        reasons = []
        
        if current.get("size") != expected.get("size"):
            reasons.append(f"size: {current.get('size')} vs {expected.get('size')}")
        
        if current.get("mtime_ns") != expected.get("mtime_ns"):
            reasons.append(f"mtime: {current.get('mtime_ns')} vs {expected.get('mtime_ns')}")
        
        if current.get("mode") != expected.get("mode"):
            reasons.append(f"mode: {oct(current.get('mode', 0))} vs {oct(expected.get('mode', 0))}")
        
        current_hashes = current.get("partial_hashes", {})
        expected_hashes = expected.get("partial_hashes", {})
        for key in expected_hashes:
            if current_hashes.get(key) != expected_hashes.get(key):
                reasons.append(f"hash_{key}: mismatch")
        
        if current.get("sha256") != expected.get("sha256"):
            reasons.append("sha256: full hash mismatch")
        
        return "Snapshot mismatch: " + ", ".join(reasons) if reasons else "Unknown mismatch"
