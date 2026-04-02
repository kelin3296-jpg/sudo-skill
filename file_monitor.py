#!/usr/bin/env python3
"""实时文件监控 - 检测外部文件变更."""

import threading
import time
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from collections import defaultdict


class FileMonitor:
    """实时文件监控 - 检测由外部程序或用户直接编辑的文件变更."""
    
    def __init__(self, check_interval: float = 1.0):
        """初始化监控器.
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self.check_interval = check_interval
        self.monitored_files: Dict[str, Dict[str, Any]] = {}
        self.callbacks: list[Callable] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
    
    def add_watched_file(self, 
                        filepath: Path,
                        snapshot: Dict[str, Any]) -> None:
        """添加要监控的文件.
        
        Args:
            filepath: 文件路径
            snapshot: 初始快照
        """
        normalized = str(Path(filepath).expanduser().resolve())
        self.monitored_files[normalized] = {
            'snapshot': snapshot,
            'last_check': time.time()
        }
    
    def remove_watched_file(self, filepath: Path) -> None:
        """停止监控某个文件.
        
        Args:
            filepath: 文件路径
        """
        normalized = str(Path(filepath).expanduser().resolve())
        if normalized in self.monitored_files:
            del self.monitored_files[normalized]
    
    def clear_watched_files(self) -> None:
        """清空所有监控的文件."""
        self.monitored_files.clear()
    
    def register_callback(self, callback: Callable) -> None:
        """注册变更回调函数.
        
        回调签名: callback(filepath: str, change_type: str, old_snapshot: dict, new_snapshot: dict)
        
        change_type 可能的值:
        - 'modified': 文件内容被修改
        - 'deleted': 文件被删除
        - 'recreated': 文件被重新创建
        - 'mode_changed': 权限被修改
        
        Args:
            callback: 回调函数
        """
        self.callbacks.append(callback)
    
    def start(self) -> None:
        """启动监控线程."""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self) -> None:
        """停止监控线程."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self) -> None:
        """主监控循环."""
        while self.running:
            try:
                self._check_all_files()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(self.check_interval)
    
    def _check_all_files(self) -> None:
        """检查所有被监控的文件."""
        for filepath, info in list(self.monitored_files.items()):
            self._check_file(Path(filepath), info)
    
    def _check_file(self, filepath: Path, info: Dict[str, Any]) -> None:
        """检查单个文件的变更.
        
        Args:
            filepath: 文件路径
            info: 监控信息
        """
        old_snapshot = info['snapshot']
        new_snapshot = self._take_snapshot(filepath)
        
        if not new_snapshot and old_snapshot.get('exists'):
            # 文件被删除
            self._trigger_callbacks(
                str(filepath),
                'deleted',
                old_snapshot,
                new_snapshot
            )
            info['snapshot'] = new_snapshot
            return
        
        if not old_snapshot.get('exists') and new_snapshot and new_snapshot.get('exists'):
            # 文件被重新创建
            self._trigger_callbacks(
                str(filepath),
                'recreated',
                old_snapshot,
                new_snapshot
            )
            info['snapshot'] = new_snapshot
            return
        
        if not new_snapshot or not new_snapshot.get('exists'):
            return
        
        # 检查权限变更
        if old_snapshot.get('mode') != new_snapshot.get('mode'):
            self._trigger_callbacks(
                str(filepath),
                'mode_changed',
                old_snapshot,
                new_snapshot
            )
            info['snapshot'] = new_snapshot
            return
        
        # 检查内容变更
        if old_snapshot.get('size') != new_snapshot.get('size'):
            self._trigger_callbacks(
                str(filepath),
                'modified',
                old_snapshot,
                new_snapshot
            )
            info['snapshot'] = new_snapshot
            return
        
        # 检查 mtime 变更但大小不变（部分内容修改）
        if old_snapshot.get('mtime_ns') != new_snapshot.get('mtime_ns'):
            self._trigger_callbacks(
                str(filepath),
                'modified',
                old_snapshot,
                new_snapshot
            )
            info['snapshot'] = new_snapshot
    
    def _take_snapshot(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """为文件创建快照.
        
        Returns:
            快照字典或 None
        """
        try:
            target = filepath.expanduser()
            if not target.exists():
                return None
            
            stat = target.stat()
            return {
                'path': str(target.resolve()),
                'exists': True,
                'size': stat.st_size,
                'mtime_ns': stat.st_mtime_ns,
                'mode': stat.st_mode,
            }
        except Exception:
            return None
    
    def _trigger_callbacks(self,
                          filepath: str,
                          change_type: str,
                          old_snapshot: Dict[str, Any],
                          new_snapshot: Dict[str, Any]) -> None:
        """触发所有已注册的回调.
        
        Args:
            filepath: 文件路径
            change_type: 变更类型
            old_snapshot: 旧快照
            new_snapshot: 新快照
        """
        for callback in self.callbacks:
            try:
                callback(filepath, change_type, old_snapshot, new_snapshot)
            except Exception as e:
                print(f"Callback error: {e}")


class MonitoredSnapshot:
    """带有监控功能的快照类."""
    
    def __init__(self, filepath: Path, snapshot: Dict[str, Any]):
        """初始化.
        
        Args:
            filepath: 文件路径
            snapshot: 快照数据
        """
        self.filepath = filepath
        self.snapshot = snapshot
        self.monitor = FileMonitor()
        self.changes: list[Dict[str, Any]] = []
        
        # 注册变更回调
        self.monitor.register_callback(self._on_file_change)
        self.monitor.add_watched_file(filepath, snapshot)
    
    def _on_file_change(self,
                       filepath: str,
                       change_type: str,
                       old_snapshot: Dict[str, Any],
                       new_snapshot: Dict[str, Any]) -> None:
        """文件变更回调."""
        self.changes.append({
            'timestamp': time.time(),
            'type': change_type,
            'old': old_snapshot,
            'new': new_snapshot
        })
    
    def start_monitoring(self) -> None:
        """启动监控."""
        self.monitor.start()
    
    def stop_monitoring(self) -> None:
        """停止监控."""
        self.monitor.stop()
    
    def has_external_changes(self) -> bool:
        """检查是否有外部变更.
        
        Returns:
            bool: 是否检测到外部变更
        """
        return len(self.changes) > 0
    
    def get_changes_summary(self) -> Dict[str, Any]:
        """获取变更摘要.
        
        Returns:
            {
                'has_changes': bool,
                'change_count': int,
                'change_types': [...],
                'last_change_time': float,
                'changes': [...]
            }
        """
        return {
            'has_changes': len(self.changes) > 0,
            'change_count': len(self.changes),
            'change_types': list(set(c['type'] for c in self.changes)),
            'last_change_time': self.changes[-1]['timestamp'] if self.changes else None,
            'changes': self.changes
        }
