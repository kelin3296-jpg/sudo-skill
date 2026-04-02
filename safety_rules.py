#!/usr/bin/env python3
"""统一的安全规则 - 权限检查和命令分类."""

import re
from enum import Enum
from typing import Optional


class CommandSafety(Enum):
    """命令安全等级."""
    SAFE = "safe"  # 完全安全的读取操作
    SAFE_WITH_LOGGING = "safe_with_logging"  # 安全但需要记录
    REQUIRES_CONFIRM = "requires_confirm"  # 需要用户确认
    DANGEROUS = "dangerous"  # 危险操作，应该拒绝


class SafetyRules:
    """统一的权限检查规则库."""
    
    # 完全安全的读取命令
    SAFE_READ_COMMANDS = [
        r'\bcat\b',
        r'\bhead\b',
        r'\btail\b',
        r'\bless\b',
        r'\bmore\b',
        r'\bgrep\b',
        r'\bawk\b(?!\s+-i)',  # 排除 awk -i
        r'\bsed\b(?!\s+-i)',  # 排除 sed -i
        r'\bls\b',
        r'\bfind\b',
        r'\bfile\b',
        r'\bstat\b',
        r'\bmd5sum\b',
        r'\bsha256sum\b',
        r'\bwc\b',
        r'\bsort\b',
        r'\buniq\b',
        r'\bcut\b',
        r'\btr\b',
        r'\bxargs\b',
        r'\bgzip\b',
        r'\bgunzip\b',
        r'\btar\s+-(t|x|z)',  # 解档，不打包
        r'\bjq\b',
        r'\byaml\b',
        r'\bjsondiff\b',
    ]
    
    # 需要记录但相对安全的操作 - 中等激进：添加文件操作
    SAFE_WITH_LOGGING_COMMANDS = [
        r'\becho\b',
        r'\bprintf\b',
        r'\bmkdir\b',
        r'\btouch\b',
        r'\bcp\b',  # 复制文件 - 中等激进：放行
        r'\bmv\b',  # 移动文件 - 中等激进：放行
        r'\bmkdir\s+-p',  # 深度目录创建 - 中等激进：放行
        r'\btar\s+-c',  # 打包 - 中等激进：放行
        r'\btar\s+-[zx]',  # 解包/解压 - 中等激进：放行
        r'\bchmod\b',  # 权限修改 - 中等激进：放行
        r'\bchown\b',  # 所有者修改 - 中等激进：放行
    ]
    
    # 需要外部确认的操作（UI 按钮）- 中等激进：文件操作已放行
    REQUIRES_CONFIRM_OPERATIONS = [
        # 文件操作已移到 SAFE_WITH_LOGGING，只保留真正需要确认的系统操作
    ]
    
    # 明确危险的操作 - 中等激进：chmod/chown 已放行
    DANGEROUS_COMMANDS = [
        r'\brm\b',           # 删除文件
        r'\brm\s+-r',        # 递归删除
        r'\brm\s+-f',        # 强制删除
        r'\brm\s+-rf',       # 强制递归删除 🚨
        r'\bdd\b',           # 磁盘操作
        r'\bmkfs\b',         # 格式化文件系统 🚨
        r'\bmount\b',        # 挂载
        r'\bumount\b',       # 卸载
        r'\bfdisk\b',        # 分区表修改
        r'\bparted\b',       # 分区编辑
        r'\bchgrp\b',        # 组修改
        r'\bsudo\b',         # sudo 提权
        r'\b>\s*[^>]',       # 无条件写入重定向 (>)
        r'\b>>\s',           # 无条件追加重定向 (>>)
        r'\b\|\s*\brm\b',    # 管道到 rm
        r'\b\|\s*\bdd\b',    # 管道到 dd
        r'\b\|\s*\bsed\s+-i', # 管道到 sed -i（原地编辑）
        r'\b\|\s*\bawk\s+-i', # 管道到 awk -i
        r'systemctl\s+stop', # 停止系统服务 🚨
        r'systemctl\s+restart',  # 重启服务
        r'service\b.*stop',  # 停止服务
        r'\bkill\b',         # 杀死进程
        r'\bpkill\b',        # 按名称杀死进程
    ]
    
    # 敏感的配置文件
    SENSITIVE_FILES = [
        '/etc/passwd',
        '/etc/shadow',
        '/etc/sudoers',
        '/etc/fstab',
        '/root/.ssh/authorized_keys',
        '~/.ssh/config',
        '~/.ssh/private*',
        '/etc/hosts',
        '/etc/hostname',
    ]
    
    @classmethod
    def classify_command(cls, command: str) -> CommandSafety:
        """分类命令的安全等级.
        
        Args:
            command: 要分析的命令字符串
            
        Returns:
            CommandSafety 枚举值
        """
        if not command or not command.strip():
            return CommandSafety.SAFE
        
        command = command.strip()
        
        # 第一层检查：危险命令
        for pattern in cls.DANGEROUS_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandSafety.DANGEROUS
        
        # 第二层检查：需要确认的命令
        for pattern in cls.REQUIRES_CONFIRM_OPERATIONS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandSafety.REQUIRES_CONFIRM
        
        # 第三层检查：需要记录的命令
        for pattern in cls.SAFE_WITH_LOGGING_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandSafety.SAFE_WITH_LOGGING
        
        # 第四层检查：完全安全的命令
        for pattern in cls.SAFE_READ_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandSafety.SAFE
        
        # 默认：如果无法分类，视为需要确认
        return CommandSafety.REQUIRES_CONFIRM
    
    @classmethod
    def is_safe_command(cls, command: str) -> bool:
        """判断命令是否完全安全.
        
        Args:
            command: 要检查的命令
            
        Returns:
            bool: 是否安全
        """
        return cls.classify_command(command) == CommandSafety.SAFE
    
    @classmethod
    def is_dangerous_command(cls, command: str) -> bool:
        """判断命令是否危险.
        
        Args:
            command: 要检查的命令
            
        Returns:
            bool: 是否危险
        """
        return cls.classify_command(command) == CommandSafety.DANGEROUS
    
    @classmethod
    def requires_external_confirm(cls, command: str) -> bool:
        """判断是否需要外部确认（UI 按钮）.
        
        Args:
            command: 要检查的命令
            
        Returns:
            bool: 是否需要确认
        """
        return cls.classify_command(command) in (
            CommandSafety.REQUIRES_CONFIRM,
            CommandSafety.DANGEROUS
        )
    
    @classmethod
    def check_file_modification(cls, filepath: str) -> tuple[bool, Optional[str]]:
        """检查文件修改是否安全.
        
        Args:
            filepath: 要修改的文件路径
            
        Returns:
            (is_safe, reason) 元组
        """
        import os
        from pathlib import Path
        
        expanded = os.path.expanduser(filepath)
        
        for pattern in cls.SENSITIVE_FILES:
            pattern_expanded = os.path.expanduser(pattern)
            if Path(expanded).resolve() == Path(pattern_expanded).resolve():
                return False, f"Cannot modify sensitive file: {filepath}"
        
        return True, None
    
    @classmethod
    def get_risk_score(cls, command: str) -> int:
        """计算命令的风险分数 (0-100).
        
        Args:
            command: 要分析的命令
            
        Returns:
            int: 风险分数
        """
        safety = cls.classify_command(command)
        
        if safety == CommandSafety.SAFE:
            return 0
        elif safety == CommandSafety.SAFE_WITH_LOGGING:
            return 10
        elif safety == CommandSafety.REQUIRES_CONFIRM:
            return 50
        else:  # DANGEROUS
            return 100
