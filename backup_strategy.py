#!/usr/bin/env python3
"""分层备份策略 - 多地点备份以提高可靠性."""

import gzip
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List


class BackupStrategy:
    """分层备份管理 - 主备份 + 冗余副本."""
    
    # 定义备份位置优先级
    BACKUP_TIERS = [
        ("primary", "~/.claude/sudo-backups"),  # 主备份
        ("secondary", "~/.backup/claude-sudo"),  # 系统备份目录
    ]
    
    def __init__(self, primary_backup_dir: Path):
        """初始化备份策略.
        
        Args:
            primary_backup_dir: 主备份目录
        """
        self.primary_backup_dir = Path(primary_backup_dir).expanduser()
        self.secondary_backup_dirs = [
            Path(tier_path).expanduser() 
            for _, tier_path in self.BACKUP_TIERS[1:]
        ]
    
    def get_available_tiers(self) -> List[tuple[str, Path]]:
        """获取所有可用的备份层级.
        
        Returns:
            可用的 (tier_name, path) 元组列表
        """
        tiers = [("primary", self.primary_backup_dir)]
        
        for tier_name, tier_path in zip(
            [t[0] for t in self.BACKUP_TIERS[1:]],
            self.secondary_backup_dirs
        ):
            if tier_path.parent.exists() or tier_path.parent.stat().st_dev == self.primary_backup_dir.stat().st_dev:
                # 如果不在同一磁盘上，才添加冗余
                if tier_path.stat().st_dev != self.primary_backup_dir.stat().st_dev:
                    tiers.append((tier_name, tier_path))
        
        return tiers
    
    def backup_file(self, 
                   filepath: Path,
                   redundancy: int = 1) -> dict:
        """备份文件到多个位置.
        
        Args:
            filepath: 要备份的文件
            redundancy: 冗余数量 (1=仅主备份, 2=主+1个副本)
            
        Returns:
            {
                'primary': {'path': '...', 'size': ...},
                'secondary': [...],
                'hashes': {...}
            }
        """
        target = Path(filepath).expanduser()
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Cannot backup non-existent file: {target}")
        
        tiers = self.get_available_tiers()
        backup_count = min(redundancy, len(tiers))
        
        result = {
            'primary': None,
            'secondary': [],
            'hashes': {}
        }
        
        for i, (tier_name, tier_path) in enumerate(tiers[:backup_count]):
            backup_path = self._make_backup_path(target, tier_path)
            
            # 执行备份
            with open(target, 'rb') as src:
                with gzip.open(backup_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            
            backup_info = {
                'path': str(backup_path),
                'size': backup_path.stat().st_size,
                'timestamp': datetime.now().isoformat(),
                'tier': tier_name
            }
            
            if i == 0:
                result['primary'] = backup_info
            else:
                result['secondary'].append(backup_info)
        
        return result
    
    def verify_backup_integrity(self, backup_path: Path) -> bool:
        """验证备份文件的完整性.
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 备份是否完整
        """
        try:
            with gzip.open(backup_path, 'rb') as f:
                # 尝试读取整个文件
                while chunk := f.read(1024 * 1024):
                    pass
            return True
        except Exception:
            return False
    
    def restore_from_backup(self, 
                           backup_path: Path,
                           target_path: Path,
                           verify: bool = True) -> bool:
        """从备份恢复文件.
        
        Args:
            backup_path: 备份文件路径
            target_path: 目标恢复路径
            verify: 恢复前是否验证备份
            
        Returns:
            bool: 恢复是否成功
        """
        if verify and not self.verify_backup_integrity(backup_path):
            raise ValueError(f"Backup integrity check failed: {backup_path}")
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with gzip.open(backup_path, 'rb') as src:
                with open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to restore from backup: {e}")
    
    def find_backup(self, 
                   original_path: Path,
                   backup_index: int = 0) -> Optional[Path]:
        """查找某文件的备份.
        
        按时间倒序查找最近的备份。
        
        Args:
            original_path: 原文件路径
            backup_index: 第 N 个备份 (0=最新)
            
        Returns:
            备份文件路径或 None
        """
        original_name = original_path.name[:100] or "unnamed"
        
        backups = []
        for tier_name, tier_path in self.get_available_tiers():
            pattern = f"{original_name}.*"
            matching = list(tier_path.glob(pattern))
            backups.extend(sorted(matching, key=lambda p: p.stat().st_mtime, reverse=True))
        
        if backup_index < len(backups):
            return backups[backup_index]
        
        return None
    
    def cleanup_old_backups(self, 
                           days: int = 7,
                           preserve_count: int = 5) -> dict:
        """清理旧备份文件.
        
        保留最近 N 个或 X 天内的备份。
        
        Args:
            days: 保留天数
            preserve_count: 最少保留备份数
            
        Returns:
            {
                'deleted_count': ...,
                'freed_bytes': ...,
                'preserved_count': ...
            }
        """
        from datetime import timedelta, datetime
        
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        freed_bytes = 0
        preserved_count = 0
        
        for tier_name, tier_path in self.get_available_tiers():
            if not tier_path.exists():
                continue
            
            # 按时间分组备份
            backups_by_original = {}
            for backup_file in tier_path.glob("*.gz"):
                original_name = backup_file.name.split(".")[0]
                if original_name not in backups_by_original:
                    backups_by_original[original_name] = []
                backups_by_original[original_name].append(backup_file)
            
            # 对每个原文件保留最近 N 个
            for original_name, backups in backups_by_original.items():
                sorted_backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)
                
                for backup_file in sorted_backups[preserve_count:]:
                    mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if mtime < cutoff_time:
                        freed_bytes += backup_file.stat().st_size
                        backup_file.unlink()
                        deleted_count += 1
                    else:
                        preserved_count += 1
        
        return {
            'deleted_count': deleted_count,
            'freed_bytes': freed_bytes,
            'preserved_count': preserved_count
        }
    
    def _make_backup_path(self, 
                         original: Path,
                         backup_dir: Path) -> Path:
        """生成备份文件路径.
        
        格式: {original_name}.{timestamp}.gz
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = original.name[:100] or "unnamed"
        return backup_dir / f"{safe_name}.{timestamp}.gz"
    
    def estimate_storage_usage(self) -> dict:
        """估计存储空间使用情况.
        
        Returns:
            {
                'total_backups': ...,
                'total_size_bytes': ...,
                'by_tier': {...}
            }
        """
        total = 0
        backup_count = 0
        by_tier = {}
        
        for tier_name, tier_path in self.get_available_tiers():
            if not tier_path.exists():
                by_tier[tier_name] = {'count': 0, 'size': 0}
                continue
            
            tier_size = 0
            tier_count = 0
            
            for backup_file in tier_path.glob("*.gz"):
                tier_size += backup_file.stat().st_size
                tier_count += 1
            
            total += tier_size
            backup_count += tier_count
            by_tier[tier_name] = {
                'count': tier_count,
                'size': tier_size
            }
        
        return {
            'total_backups': backup_count,
            'total_size_bytes': total,
            'by_tier': by_tier
        }
