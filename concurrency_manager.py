#!/usr/bin/env python3
"""并发控制 - 提供线程安全的日志操作."""

import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


class ConcurrencyManager:
    """管理文件级锁，确保并发安全."""
    
    def __init__(self, lock_dir: Path):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.lock_dir / ".operations.lock"
        self.state_lock_file = self.lock_dir / ".state.lock"
    
    @contextmanager
    def acquire_operations_lock(self, timeout: int = 30):
        """获取操作日志锁 (独占).
        
        Args:
            timeout: 等待超时秒数
            
        Yields:
            bool: 是否成功获取锁
        """
        lock_file = None
        try:
            lock_file = open(self.lock_file, 'w')
            start_time = time.time()
            
            # 尝试获取独占锁
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Cannot acquire operations lock within {timeout}s")
                    time.sleep(0.1)
            
            yield True
        finally:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except Exception:
                    pass
    
    @contextmanager
    def acquire_state_lock(self, timeout: int = 5):
        """获取状态文件锁 (独占).
        
        Args:
            timeout: 等待超时秒数
            
        Yields:
            bool: 是否成功获取锁
        """
        lock_file = None
        try:
            lock_file = open(self.state_lock_file, 'w')
            start_time = time.time()
            
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Cannot acquire state lock within {timeout}s")
                    time.sleep(0.01)
            
            yield True
        finally:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except Exception:
                    pass
    
    def is_locked(self) -> bool:
        """检查操作日志是否被锁定."""
        try:
            with open(self.lock_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
        except IOError:
            return True
