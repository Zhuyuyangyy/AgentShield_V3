"""
AgentBehaviorGraph - V3 Layer 1
===============================
多 Agent 行为链追踪与状态图谱。

将单个会话中多个 Agent 的工具调用序列建模为有向图：
- 节点（BehaviorNode）：Agent 身份 + 工具调用请求 + 熔断决策 + 风险状态
- 边（BehaviorEdge）：Agent 间调用关系（invoke/subagent/delegate）或数据流向
- 关键能力：识别风险沿调用链如何扩散

每个 ToolCallRequest 进入这个图，产生/更新一个节点。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class NodeRiskStatus(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class BehaviorNode:
    """
    行为图中的一个节点：对应一次工具调用
    """
    node_id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    agent_id: str = "unknown"
    session_id: str = "unknown"
    tool_name: str = ""
    params_summary: str = ""          # 参数摘要（脱敏后，用于图谱展示）
    fuse_action: str = "allow"        # allow / block / human_review
    shadow_risk_score: float = 0.0    # V2 的影子风险评分
    risk_status: NodeRiskStatus = NodeRiskStatus.SAFE
    timestamp: datetime = field(default_factory=datetime.now)
    # 该节点是否产生了风险扩散（沿某条边传到下游）
    downstream_risk_amplified: bool = False
    # 该节点触发的干预次数
    intervention_count: int = 0
    # 因果归因：该节点的风险有多少传导自上游
    inherited_risk: float = 0.0
    # 节点标签（用于可视化）
    labels: list[str] = field(default_factory=list)
    # 元数据
    metadata: dict = field(default_factory=dict)

    def is_risk_amplifier(self) -> bool:
        """该节点是否放大了上游风险"""
        return self.downstream_risk_amplified

    def to_summary(self) -> dict:
        return {
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "fuse_action": self.fuse_action,
            "risk_score": self.shadow_risk_score,
            "risk_status": self.risk_status.value,
            "inherited_risk": round(self.inherited_risk, 3),
            "intervention_count": self.intervention_count,
        }


@dataclass
class BehaviorEdge:
    """
    行为图中的边：表示 Agent 间的调用关系或数据流向
    """
    edge_id: str = field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    from_node_id: str = ""
    to_node_id: str = ""
    edge_type: str = "calls"          # calls / invokes / data_flow / returns
    risk_flow: float = 0.0            # 沿这条边流动的风险量
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_summary(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "from": self.from_node_id,
            "to": self.to_node_id,
            "type": self.edge_type,
            "risk_flow": round(self.risk_flow, 3),
        }


class AgentBehaviorGraph:
    """
    Agent 行为图谱

    将一个 session 中所有 Agent 的工具调用组织为有向图，
    支持：
    - 节点和边的增删查
    - 风险沿边的传播计算
    - 识别关键风险节点（风险放大器）
    - 关键路径提取（从某节点到另一节点的最风险路径）
    - 单次工具调用作为节点加入图谱
    """

    def __init__(self, session_id: str = "unknown"):
        self.session_id = session_id
        self.nodes: dict[str, BehaviorNode] = {}
        self.edges: dict[str, BehaviorEdge] = {}
        self._node_list: list[BehaviorNode] = []   # 按时间顺序
        self._adjacency: dict[str, list[str]] = {}  # node_id → [child_node_ids]

    # ─── 图写入 ──────────────────────────────────────────────

    def add_node(self, node: BehaviorNode) -> BehaviorNode:
        """将一个工具调用节点加入图谱"""
        if node.node_id in self.nodes:
            # 已存在则更新（同一工具调用可能产生多个审计结果）
            existing = self.nodes[node.node_id]
            for k, v in node.__dict__.items():
                if v != getattr(existing, k):
                    setattr(existing, k, v)
            return existing

        self.nodes[node.node_id] = node
        self._node_list.append(node)
        self._adjacency[node.node_id] = []
        return node

    def add_edge(self, edge: BehaviorEdge) -> BehaviorEdge:
        """添加一条边（Agent 间调用关系）"""
        if edge.edge_id in self.edges:
            return self.edges[edge.edge_id]
        if edge.from_node_id not in self.nodes:
            raise ValueError(f"from_node {edge.from_node_id} not in graph")
        if edge.to_node_id not in self.nodes:
            raise ValueError(f"to_node {edge.to_node_id} not in graph")

        self.edges[edge.edge_id] = edge
        self._adjacency[edge.from_node_id].append(edge.to_node_id)
        return edge

    def add_tool_call_as_node(
        self,
        agent_id: str,
        tool_name: str,
        params_summary: str,
        fuse_action: str,
        shadow_risk_score: float,
        parent_node_id: Optional[str] = None,
        edge_type: str = "calls",
        inherited_risk: float = 0.0,
        labels: Optional[list[str]] = None,
    ) -> BehaviorNode:
        """
        将一次工具调用快速加入图谱。
        如果指定了 parent_node_id，自动创建边。
        """
        node = BehaviorNode(
            agent_id=agent_id,
            session_id=self.session_id,
            tool_name=tool_name,
            params_summary=params_summary,
            fuse_action=fuse_action,
            shadow_risk_score=shadow_risk_score,
            risk_status=self._score_to_status(shadow_risk_score),
            inherited_risk=inherited_risk,
            labels=labels or [],
        )
        self.add_node(node)

        if parent_node_id and parent_node_id in self.nodes:
            edge = BehaviorEdge(
                from_node_id=parent_node_id,
                to_node_id=node.node_id,
                edge_type=edge_type,
                risk_flow=shadow_risk_score,
            )
            self.add_edge(edge)

        return node

    # ─── 图查询 ──────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[BehaviorNode]:
        return self.nodes.get(node_id)

    def get_session_nodes(self) -> list[BehaviorNode]:
        """返回该会话所有节点（按时间顺序）"""
        return self._node_list

    def get_critical_nodes(self, threshold: float = 0.7) -> list[BehaviorNode]:
        """
        识别风险放大器节点（高风险 + 放大了上游风险）
        """
        return [
            n for n in self._node_list
            if n.shadow_risk_score >= threshold and n.downstream_risk_amplified
        ]

    def get_risk_path(self, start_node_id: str, end_node_id: str) -> list[BehaviorNode]:
        """
        提取从 start 到 end 的最风险路径（风险加权最短路径）
        """
        if start_node_id not in self.nodes or end_node_id not in self.nodes:
            return []

        # BFS with risk as weight (higher risk = shorter effective distance)
        visited = set()
        queue = [(start_node_id, [start_node_id])]

        while queue:
            node_id, path = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            if node_id == end_node_id:
                return [self.nodes[nid] for nid in path]

            for child_id in self._adjacency.get(node_id, []):
                if child_id not in visited:
                    queue.append((child_id, path + [child_id]))

        return []

    def get_downstream_nodes(self, node_id: str) -> list[BehaviorNode]:
        """获取某节点的所有下游节点"""
        result = []
        visited = set()
        queue = list(self._adjacency.get(node_id, []))

        while queue:
            child_id = queue.pop(0)
            if child_id in visited:
                continue
            visited.add(child_id)
            if child_id in self.nodes:
                result.append(self.nodes[child_id])
                queue.extend(self._adjacency.get(child_id, []))

        return result

    def compute_risk_propagation(self) -> dict[str, float]:
        """
        从叶子节点逆向传播，计算每个节点继承了多少上游风险。
        风险传播规则：
          inherited_risk[node] = max(
              inherited_risk[node],
              inherited_risk[parent] * edge.risk_flow
          )
        叶子节点先计算自己本地的 shadow_risk_score，
        然后逆向遍历更新所有祖先节点的 inherited_risk。
        """
        if not self._node_list:
            return {}

        # 按时间顺序建立父子关系映射
        # 从最后一个往前推
        node_risk: dict[str, float] = {}

        # 叶子节点 = 没有子节点的节点
        has_child = {edge.to_node_id for edge in self.edges.values()}
        leaf_nodes = [n for n in self._node_list if n.node_id not in has_child]

        # 每个叶子从自己的 shadow_risk_score 开始
        for leaf in leaf_nodes:
            node_risk[leaf.node_id] = leaf.shadow_risk_score

        # 逆向传播（从叶子到根）
        # 建立 to → from 的反向邻接表
        reverse_adj: dict[str, list[str]] = {}
        for nid in self.nodes:
            reverse_adj[nid] = []
        for edge in self.edges.values():
            reverse_adj[edge.to_node_id].append(edge.from_node_id)

        # BFS 向上传播
        visited = set()
        # Track depth from leaf for dynamic decay
        node_depth: dict[str, int] = {}
        for leaf in leaf_nodes:
            node_depth[leaf.node_id] = 0
        queue = list(leaf_nodes)

        while queue:
            node = queue.pop(0)
            if node.node_id in visited:
                continue
            visited.add(node.node_id)

            current_risk = node_risk.get(node.node_id, 0.0)
            current_depth = node_depth.get(node.node_id, 0)

            for parent_id in reverse_adj.get(node.node_id, []):
                if parent_id not in self.nodes:
                    continue
                parent = self.nodes[parent_id]
                # Dynamic decay based on chain length:
                # decay = 1.0 / (1 + 0.3 * chain_length)
                # chain_length grows as we propagate further from the leaf
                chain_length = current_depth + 1
                decay = 1.0 / (1.0 + 0.3 * chain_length)
                inherited = current_risk * decay
                if parent_id not in node_risk:
                    node_risk[parent_id] = inherited
                else:
                    node_risk[parent_id] = max(node_risk[parent_id], inherited)
                node_depth[parent_id] = chain_length

                # 标记是否放大下游风险
                if inherited > 0.1:
                    parent.downstream_risk_amplified = True

                if parent_id not in visited:
                    queue.append(parent)

        # 更新节点 inherited_risk
        for nid, ir in node_risk.items():
            if nid in self.nodes:
                self.nodes[nid].inherited_risk = ir

        return node_risk

    def to_graph_dict(self) -> dict:
        """导出为 dict（用于序列化或前端图谱渲染）"""
        return {
            "session_id": self.session_id,
            "nodes": [n.to_summary() for n in self._node_list],
            "edges": [e.to_summary() for e in self.edges.values()],
            "critical_nodes": [n.node_id for n in self.get_critical_nodes()],
        }

    # ─── 辅助 ──────────────────────────────────────────────

    @staticmethod
    def _score_to_status(score: float) -> NodeRiskStatus:
        if score >= 0.90:
            return NodeRiskStatus.CRITICAL
        elif score >= 0.70:
            return NodeRiskStatus.HIGH
        elif score >= 0.50:
            return NodeRiskStatus.MEDIUM
        elif score >= 0.20:
            return NodeRiskStatus.LOW
        return NodeRiskStatus.SAFE

    def summary(self) -> dict:
        """图谱统计摘要"""
        nodes = self._node_list
        return {
            "session_id": self.session_id,
            "total_nodes": len(nodes),
            "total_edges": len(self.edges),
            "risk_distribution": {
                "safe": sum(1 for n in nodes if n.risk_status == NodeRiskStatus.SAFE),
                "low": sum(1 for n in nodes if n.risk_status == NodeRiskStatus.LOW),
                "medium": sum(1 for n in nodes if n.risk_status == NodeRiskStatus.MEDIUM),
                "high": sum(1 for n in nodes if n.risk_status == NodeRiskStatus.HIGH),
                "critical": sum(1 for n in nodes if n.risk_status == NodeRiskStatus.CRITICAL),
            },
            "critical_node_count": len(self.get_critical_nodes()),
            "blocked_count": sum(1 for n in nodes if n.fuse_action == "block"),
            "review_count": sum(1 for n in nodes if n.fuse_action == "human_review"),
        }
