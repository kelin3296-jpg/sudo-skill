#!/usr/bin/env python3
"""综合单元测试 - 覆盖所有优化后的组件."""

import unittest
import tempfile
import shutil
from pathlib import Path
import time

from safety_rules import SafetyRules, CommandSafety
from snapshot_engine import SnapshotEngine
from concurrency_manager import ConcurrencyManager
from dependency_analyzer import DependencyAnalyzer


class TestSafetyRules(unittest.TestCase):
    """测试安全规则分类."""
    
    def test_safe_commands(self):
        """测试安全命令."""
        safe_commands = [
            "cat /etc/passwd",
            "grep 'error' logfile.txt",
            "ls -la /tmp",
            "find . -name '*.py'",
        ]
        
        for cmd in safe_commands:
            self.assertEqual(
                SafetyRules.classify_command(cmd),
                CommandSafety.SAFE,
                f"Should classify '{cmd}' as SAFE"
            )
    
    def test_dangerous_commands(self):
        """测试危险命令."""
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "sudo chmod 777 /etc/sudoers",
        ]
        
        for cmd in dangerous_commands:
            self.assertEqual(
                SafetyRules.classify_command(cmd),
                CommandSafety.DANGEROUS,
                f"Should classify '{cmd}' as DANGEROUS"
            )
    
    def test_requires_confirm_commands(self):
        """测试需要确认的命令."""
        confirm_commands = [
            "cp important.txt backup.txt",
            "mv old.txt new.txt",
        ]
        
        for cmd in confirm_commands:
            safety = SafetyRules.classify_command(cmd)
            self.assertIn(
                safety,
                [CommandSafety.REQUIRES_CONFIRM, CommandSafety.SAFE_WITH_LOGGING],
                f"Should classify '{cmd}' as requiring confirmation"
            )
    
    def test_risk_score(self):
        """测试风险评分."""
        self.assertEqual(SafetyRules.get_risk_score("cat file.txt"), 0)
        self.assertGreater(SafetyRules.get_risk_score("cp file.txt backup.txt"), 0)
        self.assertEqual(SafetyRules.get_risk_score("rm -rf /"), 100)


class TestSnapshotEngine(unittest.TestCase):
    """测试快照引擎."""
    
    def setUp(self):
        """创建临时文件."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("Hello, World!")
    
    def tearDown(self):
        """清理临时文件."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_snapshot(self):
        """测试快照创建."""
        snapshot = SnapshotEngine.create_snapshot(self.test_file, include_full=True)
        
        self.assertTrue(snapshot["exists"])
        self.assertEqual(snapshot["kind"], "file")
        self.assertGreater(snapshot["size"], 0)
        self.assertIn("sha256", snapshot)
    
    def test_quick_match(self):
        """测试快速匹配."""
        snap1 = SnapshotEngine.create_snapshot(self.test_file)
        snap2 = SnapshotEngine.create_snapshot(self.test_file)
        
        # 相同文件应该匹配
        self.assertTrue(SnapshotEngine.quick_match(snap1, snap2))
    
    def test_quick_mismatch(self):
        """测试快速不匹配."""
        snap1 = SnapshotEngine.create_snapshot(self.test_file)
        
        # 修改文件
        self.test_file.write_text("Modified content!")
        snap2 = SnapshotEngine.create_snapshot(self.test_file)
        
        # 应该检测到差异
        self.assertFalse(SnapshotEngine.quick_match(snap1, snap2))
    
    def test_mismatch_report(self):
        """测试不匹配报告."""
        snap1 = SnapshotEngine.create_snapshot(self.test_file)
        self.test_file.write_text("Modified!")
        snap2 = SnapshotEngine.create_snapshot(self.test_file)
        
        report = SnapshotEngine.report_mismatch(snap1, snap2)
        self.assertIn("Snapshot mismatch", report)
        self.assertIn("size", report.lower())


class TestConcurrencyManager(unittest.TestCase):
    """测试并发管理."""
    
    def setUp(self):
        """创建临时目录."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理临时目录."""
        shutil.rmtree(self.temp_dir)
    
    def test_acquire_lock(self):
        """测试获取锁."""
        manager = ConcurrencyManager(Path(self.temp_dir))
        
        with manager.acquire_operations_lock():
            # 在锁定状态下做一些操作
            self.assertTrue(manager.is_locked())
    
    def test_lock_timeout(self):
        """测试锁超时."""
        manager = ConcurrencyManager(Path(self.temp_dir))
        
        with manager.acquire_operations_lock():
            # 尝试在另一个上下文中获取锁（应该超时）
            try:
                with manager.acquire_operations_lock(timeout=1):
                    self.fail("Should have timed out")
            except TimeoutError:
                pass  # 预期的行为


class TestDependencyAnalyzer(unittest.TestCase):
    """测试依赖分析."""
    
    def setUp(self):
        """设置测试数据."""
        self.operations = [
            {"id": 1, "type": "create", "path": "/tmp/file.txt"},
            {"id": 2, "type": "modify", "path": "/tmp/file.txt"},
            {"id": 3, "type": "modify", "path": "/tmp/file.txt"},
            {"id": 4, "type": "move", "src_path": "/tmp/file.txt", "dst_path": "/tmp/file2.txt"},
            {"id": 5, "type": "modify", "path": "/tmp/file2.txt"},
        ]
    
    def test_build_graph(self):
        """测试构建依赖图."""
        analyzer = DependencyAnalyzer(self.operations)
        graph = analyzer.build_graph()
        
        # 检查某些已知的依赖关系
        self.assertIn(2, graph.get(3, set()))  # op 3 依赖 op 2
    
    def test_get_dependents(self):
        """测试获取依赖项."""
        analyzer = DependencyAnalyzer(self.operations)
        dependents = analyzer.get_dependents(1)  # op 1 被谁依赖？
        
        # 至少应该被 op 2 依赖
        self.assertIn(2, dependents)
    
    def test_transitive_dependents(self):
        """测试传递依赖."""
        analyzer = DependencyAnalyzer(self.operations)
        transitive = analyzer._get_transitive_dependents(1)
        
        # op 1 应该被所有后续操作间接依赖
        self.assertTrue(len(transitive) > 0)
    
    def test_can_safely_rollback(self):
        """测试安全回滚检查."""
        analyzer = DependencyAnalyzer(self.operations)
        
        # 应该可以回滚最后一个操作
        can_rollback, reason = analyzer.can_safely_rollback([5])
        self.assertTrue(can_rollback)
        
        # 不应该可以回滚中间的操作
        can_rollback, reason = analyzer.can_safely_rollback([2])
        self.assertFalse(can_rollback)
    
    def test_topological_sort(self):
        """测试拓扑排序."""
        analyzer = DependencyAnalyzer(self.operations)
        
        # 对所有操作进行排序
        sorted_ops = analyzer.topological_sort([1, 2, 3, 4, 5])
        
        # 应该以逆序返回（用于回滚）
        self.assertEqual(sorted_ops[-1], 1)


class TestIntegration(unittest.TestCase):
    """集成测试."""
    
    def setUp(self):
        """创建测试环境."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境."""
        shutil.rmtree(self.temp_dir)
    
    def test_snapshot_and_safety(self):
        """测试快照和安全性的集成."""
        test_file = Path(self.temp_dir) / "important.txt"
        test_file.write_text("Important content")
        
        # 创建快照
        snapshot = SnapshotEngine.create_snapshot(test_file)
        self.assertTrue(snapshot["exists"])
        
        # 检查文件修改是否安全
        is_safe, reason = SafetyRules.check_file_modification(str(test_file))
        self.assertTrue(is_safe)
    
    def test_concurrency_and_snapshot(self):
        """测试并发和快照的集成."""
        manager = ConcurrencyManager(Path(self.temp_dir))
        
        test_file = Path(self.temp_dir) / "data.txt"
        test_file.write_text("Data")
        
        with manager.acquire_operations_lock():
            snapshot1 = SnapshotEngine.create_snapshot(test_file)
            time.sleep(0.1)
            snapshot2 = SnapshotEngine.create_snapshot(test_file)
            
            # 在锁定期间，快照应该相同
            self.assertTrue(SnapshotEngine.quick_match(snapshot1, snapshot2))


if __name__ == "__main__":
    unittest.main()
