#!/usr/bin/env python3
"""依赖分析引擎 - 操作之间的依赖关系."""

from collections import defaultdict
from typing import Any, Optional, Set


class DependencyAnalyzer:
    """分析操作之间的依赖关系."""
    
    def __init__(self, operations: list[dict[str, Any]]):
        """初始化分析器.
        
        Args:
            operations: 操作列表 (应按时间序列排列)
        """
        self.operations = operations
        self.graph = None  # 延迟构建
    
    def build_graph(self) -> dict[int, Set[int]]:
        """构建依赖关系图.
        
        返回格式:
        {
            operation_id: {依赖的_operation_ids},
            ...
        }
        
        Returns:
            依赖关系图
        """
        if self.graph is not None:
            return self.graph
        
        graph: dict[int, Set[int]] = defaultdict(set)
        
        # 遍历所有操作对
        for i, op1 in enumerate(self.operations):
            for j, op2 in enumerate(self.operations):
                if i >= j:
                    continue
                
                dep = self._find_dependency(op1, op2)
                if dep:
                    # op2 依赖 op1
                    op2_id = int(op2.get("id", j))
                    op1_id = int(op1.get("id", i))
                    graph[op2_id].add(op1_id)
        
        self.graph = graph
        return graph
    
    def _find_dependency(self, earlier_op: dict[str, Any], 
                        later_op: dict[str, Any]) -> bool:
        """判断 later_op 是否依赖 earlier_op.
        
        依赖条件：
        1. 同一文件的连续修改
        2. 创建的文件被后续操作使用
        3. 删除前的备份操作
        4. 权限修改后的文件操作
        
        Args:
            earlier_op: 时间上更早的操作
            later_op: 时间上更晚的操作
            
        Returns:
            bool: 是否存在依赖关系
        """
        earlier_path = earlier_op.get("path")
        later_path = later_op.get("path")
        
        earlier_type = earlier_op.get("type")
        later_type = later_op.get("type")
        
        # 规则 1: 同一文件的连续修改 (modify -> modify)
        if earlier_type == "modify" and later_type == "modify":
            if earlier_path == later_path:
                return True
        
        # 规则 2: 创建依赖性
        if earlier_type == "create" and earlier_path:
            if later_path == earlier_path:
                # 创建的文件被后续操作使用
                return True
        
        # 规则 3: 删除依赖性
        if earlier_type == "delete" and later_type == "create":
            if earlier_path == later_path:
                # 删除后重新创建同一文件
                return False  # 没有依赖，独立操作
        
        # 规则 4: 移动后的操作依赖
        if earlier_type == "move":
            earlier_dst = earlier_op.get("dst_path")
            if later_path == earlier_dst:
                return True
        
        # 规则 5: 权限修改后的操作
        if earlier_type == "chmod":
            if earlier_path == later_path and later_type != "chmod":
                # 权限改变后的非权限操作依赖
                return True
        
        return False
    
    def get_dependents(self, operation_id: int) -> Set[int]:
        """获取依赖某操作的所有操作.
        
        Args:
            operation_id: 操作 ID
            
        Returns:
            依赖此操作的所有操作 ID
        """
        graph = self.build_graph()
        dependents = set()
        
        for op_id, deps in graph.items():
            if operation_id in deps:
                dependents.add(op_id)
        
        return dependents
    
    def get_dependencies(self, operation_id: int) -> Set[int]:
        """获取操作的所有依赖.
        
        Args:
            operation_id: 操作 ID
            
        Returns:
            此操作依赖的所有操作 ID
        """
        graph = self.build_graph()
        return graph.get(operation_id, set())
    
    def topological_sort(self, operation_ids: list[int]) -> list[int]:
        """对操作进行拓扑排序（逆序用于回滚）.
        
        Args:
            operation_ids: 要排序的操作 ID 列表
            
        Returns:
            排序后的操作 ID 列表（从后向前，适合回滚）
        """
        graph = self.build_graph()
        
        # 构建仅包含指定操作的子图
        sub_graph = {}
        for op_id in operation_ids:
            deps = graph.get(op_id, set())
            sub_graph[op_id] = deps & set(operation_ids)
        
        # Kahn 算法进行拓扑排序
        in_degree = defaultdict(int)
        for op_id in operation_ids:
            in_degree[op_id] = len(sub_graph.get(op_id, set()))
        
        queue = [op_id for op_id in operation_ids if in_degree[op_id] == 0]
        sorted_ops = []
        
        while queue:
            op_id = queue.pop(0)
            sorted_ops.append(op_id)
            
            # 找所有依赖这个操作的操作
            for other_id, deps in sub_graph.items():
                if op_id in deps:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
        
        # 检查是否有循环依赖
        if len(sorted_ops) != len(operation_ids):
            raise ValueError("Circular dependency detected in operations")
        
        # 逆序返回（用于回滚）
        return sorted_ops[::-1]
    
    def can_safely_rollback(self, operation_ids: list[int]) -> tuple[bool, Optional[str]]:
        """检查是否可以安全回滚一组操作.
        
        Args:
            operation_ids: 要回滚的操作 ID 列表
            
        Returns:
            (can_rollback, reason) 元组
        """
        graph = self.build_graph()
        
        for op_id in operation_ids:
            dependents = self.get_dependents(op_id)
            unsafe_dependents = dependents - set(operation_ids)
            
            if unsafe_dependents:
                dependent_list = ", ".join(str(d) for d in sorted(unsafe_dependents))
                return False, (
                    f"Cannot rollback operation {op_id}: "
                    f"it is depended by operations {dependent_list} which are not included in rollback"
                )
        
        return True, None
    
    def get_safe_rollback_set(self, operation_id: int) -> Set[int]:
        """获取可以与某操作一起安全回滚的最大操作集合.
        
        这会返回所有直接或间接依赖目标操作的操作。
        
        Args:
            operation_id: 目标操作 ID
            
        Returns:
            可以一起回滚的操作 ID 集合
        """
        dependents = self._get_transitive_dependents(operation_id)
        return dependents | {operation_id}
    
    def _get_transitive_dependents(self, operation_id: int) -> Set[int]:
        """递归获取所有间接依赖的操作.
        
        Args:
            operation_id: 操作 ID
            
        Returns:
            所有依赖此操作的操作 ID（直接和间接）
        """
        direct = self.get_dependents(operation_id)
        transitive = set()
        
        for dep_id in direct:
            transitive.add(dep_id)
            transitive.update(self._get_transitive_dependents(dep_id))
        
        return transitive
    
    def print_graph(self) -> str:
        """生成依赖关系图的文本表示.
        
        Returns:
            格式化的图表字符串
        """
        graph = self.build_graph()
        
        lines = ["Operation Dependencies:", "=" * 50]
        
        for op_id in sorted(graph.keys()):
            deps = sorted(graph[op_id])
            if deps:
                lines.append(f"Operation {op_id}:")
                lines.append(f"  ├─ depends on: {', '.join(str(d) for d in deps)}")
                dependents = self.get_dependents(op_id)
                if dependents:
                    lines.append(f"  └─ depended by: {', '.join(str(d) for d in sorted(dependents))}")
            else:
                lines.append(f"Operation {op_id}: (no dependencies)")
        
        return "\n".join(lines)
