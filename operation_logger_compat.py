#!/usr/bin/env python3
"""兼容性适配层 - 从 v1 到 v2 的无缝过渡."""

"""
这个模块确保任何使用 v1 的旧代码都能自动使用 v2 的优化。

使用方式：
  from operation_logger import OperationLogger
  
  logger = OperationLogger()
  # 自动使用 v2（如果可用），否则回滚到 v1
"""

import sys
from pathlib import Path

# 尝试导入 v2
try:
    from operation_logger_v2 import (
        OperationLogger, 
        ConcurrencyManager,
        SnapshotEngine,
        BackupStrategy,
        DependencyAnalyzer,
        SafetyRules,
    )
    print("✓ Using optimized v2 modules", file=sys.stderr)
    V2_AVAILABLE = True
except ImportError:
    # 回滚到 v1
    print("⚠ v2 modules not found, falling back to v1", file=sys.stderr)
    from operation_logger import OperationLogger  # noqa
    V2_AVAILABLE = False


# 如果 v2 可用，注册专用的初始化钩子
def initialize_v2():
    """初始化 v2 的所有优化组件."""
    if not V2_AVAILABLE:
        return
    
    try:
        # 初始化 SQLite 迁移
        logger = OperationLogger()
        logger._migrate_jsonl_to_db()
        print("✓ SQLite database initialized and data migrated", file=sys.stderr)
    except Exception as e:
        print(f"⚠ SQLite initialization failed: {e}", file=sys.stderr)


# 导出版本信息
__version__ = "2.0.0" if V2_AVAILABLE else "1.0.0"
__all__ = [
    "OperationLogger",
    "V2_AVAILABLE",
    "__version__",
]

if V2_AVAILABLE:
    __all__.extend([
        "ConcurrencyManager",
        "SnapshotEngine", 
        "BackupStrategy",
        "DependencyAnalyzer",
        "SafetyRules",
    ])
