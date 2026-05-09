"""
AgentShield V3 Engine Tests
测试 V3 核心引擎：行为链处理 + 分支推演 + 治理决策
"""

import pytest
import sys
import os

# 硬编码绝对路径
ASF_BGT_ROOT = r"D:\ZYY Project\ASF-BGT-Framework"
AGENT_SHIELD_V2_ROOT = r"D:\ZYY Project\agent-shield-v2\backend"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ASF_BGT_ROOT)
sys.path.insert(0, AGENT_SHIELD_V2_ROOT)
sys.path.insert(0, WORKSPACE)


class TestV3EngineBasics:
    """V3 引擎基本功能测试"""

    def test_engine_creation(self):
        """引擎可以正常创建"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(
            session_id="test_session_001",
            world_name="TestV3World",
            risk_threshold=0.70,
        )
        assert engine.session_id == "test_session_001"
        assert engine.engine_id.startswith("v3engine_")
        assert engine.behavior_graph is not None
        assert engine.world is not None

    def test_engine_process_tool_call(self):
        """处理工具调用 → 行为图谱 + 治理决策"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_session_002")

        result = engine.process_tool_call(
            agent_id="financial_agent",
            tool_name="cursor.execute",
            params={"sql": "SELECT * FROM customers"},
            risk_score=0.85,
            fuse_action="block",
        )

        assert "node_id" in result
        assert "call_id" in result
        assert "behavior_graph_summary" in result
        assert "gate_result" in result
        assert result["gate_result"]["action"] in ["BLOCK", "REVIEW", "ALLOW"]

    def test_engine_high_risk_triggers_whatif(self):
        """高风险调用触发 What-if 反事实推演"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(
            session_id="test_session_003",
            risk_threshold=0.70,
            enable_counterfactual=True,
        )

        result = engine.process_tool_call(
            agent_id="attacker_agent",
            tool_name="send_email",
            params={"to": "external@example.com", "attachment": "customer_data.csv"},
            risk_score=0.95,
            fuse_action="block",
        )

        assert result["whatif_result"] is not None
        assert "scenario_id" in result["whatif_result"]
        assert result["whatif_result"]["risk_delta"] < 0

    def test_engine_low_risk_allows(self):
        """低风险调用直接放行"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_session_004", risk_threshold=0.70)

        result = engine.process_tool_call(
            agent_id="safe_agent",
            tool_name="read_file",
            params={"path": "/data/report.txt"},
            risk_score=0.05,
            fuse_action="allow",
        )

        assert result["gate_result"]["action"] == "ALLOW"
        assert result["whatif_result"] is None

    def test_fork_branch(self):
        """分支创建成功"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_session_005")

        branch_id = engine.fork_branch(
            branch_label="人工干预点A",
            intervention={"type": "block_tool_call", "tool_name": "send_email"},
        )

        assert branch_id is not None and len(branch_id) >= 6
        status = engine.get_governance_status()
        assert status["branch_count"] >= 1

    def test_governance_status(self):
        """治理状态查询正常"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_session_006")
        engine.process_tool_call(
            agent_id="agent_a",
            tool_name="cursor.execute",
            params={"sql": "SELECT id FROM orders"},
            risk_score=0.60,
            fuse_action="allow",
        )

        status = engine.get_governance_status()
        assert status["session_id"] == "test_session_006"
        assert "behavior_graph" in status
        assert status["behavior_graph"]["total_nodes"] == 1

    def test_export_chain(self):
        """行为链导出正常"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_session_007")
        engine.process_tool_call(
            agent_id="agent_b",
            tool_name="http_request",
            params={"url": "https://api.example.com/data"},
            risk_score=0.45,
            fuse_action="allow",
        )

        chain = engine.export_chain()
        assert "session_id" in chain
        assert "behavior_graph" in chain


class TestBehaviorGraph:
    """行为图谱测试（继承 V2 AgentBehaviorGraph）"""

    def test_add_node(self):
        """节点添加成功"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_graph_001")
        result = engine.process_tool_call(
            agent_id="test_agent",
            tool_name="cursor.execute",
            params={"sql": "SELECT 1"},
            risk_score=0.3,
            fuse_action="allow",
        )

        assert result["behavior_graph_summary"]["total_nodes"] == 1

    def test_critical_node_detection(self):
        """关键风险节点识别"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_graph_002")

        engine.process_tool_call(
            agent_id="agent_1",
            tool_name="safe_tool",
            params={},
            risk_score=0.2,
            fuse_action="allow",
        )
        engine.process_tool_call(
            agent_id="agent_2",
            tool_name="dangerous_tool",
            params={},
            risk_score=0.85,
            fuse_action="block",
        )

        critical = engine.behavior_graph.get_critical_nodes(threshold=0.7)
        assert isinstance(critical, list)


class TestRiskPropagation:
    """风险传播计算测试"""

    def test_risk_propagation_chain(self):
        """风险沿调用链传播"""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="test_risk_001")

        result1 = engine.process_tool_call(
            agent_id="agent_alpha",
            tool_name="cursor.execute",
            params={"sql": "SELECT name FROM products"},
            risk_score=0.4,
            fuse_action="allow",
        )
        node1_id = result1["node_id"]

        result2 = engine.process_tool_call(
            agent_id="agent_beta",
            tool_name="send_email",
            params={"to": "test@example.com"},
            risk_score=0.6,
            fuse_action="review",
            parent_node_id=node1_id,
        )

        assert result2["behavior_graph_summary"]["total_nodes"] == 2
        propagation = engine.behavior_graph.compute_risk_propagation()
        assert isinstance(propagation, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
