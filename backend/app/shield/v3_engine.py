"""
AgentShield V3 Engine - 行为链风险治理核心引擎
继承 ASF-BGT Framework + V2 AgentBehaviorGraph
"""

from __future__ import annotations

import sys
import uuid
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

_ASF_BGT_ROOT = r"D:\ZYY Project\ASF-BGT-Framework"
_AGENT_SHIELD_V3_ROOT = r"D:\ZYY Project\AgentShield_V3\backend"
if _ASF_BGT_ROOT not in sys.path:
    sys.path.insert(0, _ASF_BGT_ROOT)
if _AGENT_SHIELD_V3_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_SHIELD_V3_ROOT)

from core.world import World
from core.branch import Branch, BranchPoint, BranchTree
from core.causal_chain import CausalChain, CausalNode
from engine.simulator import Simulator
from engine.counterfactual import CounterfactualEngine, WhatIfScenario
from governance.gates import GovernanceGate, GovernanceResult, GovernanceAction
from governance.risk_scorer import DefaultRiskScorer

from app.shield.agent_behavior_graph import AgentBehaviorGraph, BehaviorNode, NodeRiskStatus
from app.shield.v3_audit_logger import V3AuditLogger


class V3ShieldEngine:
    """
    AgentShield V3 核心引擎
    在 ASF-BGT 框架基础上，增加 V2 的 ToolCallRequest 治理能力，
    扩展为"未来多步行为链"的风险推演与治理。
    """

    def __init__(
        self,
        session_id: str,
        world_name: str = "V3ShieldWorld",
        risk_threshold: float = 0.70,
        max_branches: int = 5,
        enable_counterfactual: bool = True,
    ):
        self.session_id = session_id
        self.engine_id = f"v3engine_{uuid.uuid4().hex[:8]}"
        self.risk_threshold = risk_threshold
        self.max_branches = max_branches
        self.enable_counterfactual = enable_counterfactual

        # ASF-BGT core
        self.world = World(name=world_name)
        self.world.patch_state({"session_id": session_id})
        self.world.patch_state({"v3_engine_id": self.engine_id})

        # BranchTree: create empty, then init root
        self.branch_tree = BranchTree()
        self.branch_tree.create_root(self.world.state.data, label="root")

        self.simulator = Simulator(world=self.world)
        self.counterfactual = CounterfactualEngine(world=self.world) if enable_counterfactual else None
        self.risk_scorer = DefaultRiskScorer()
        self.governance_gates: List[GovernanceGate] = []

        # V2 behavior graph (local copy)
        self.behavior_graph = AgentBehaviorGraph(session_id=session_id)

        # Audit logger
        self.audit_logger = V3AuditLogger()
        self._init_audit()

    def _init_audit(self):
        self.audit_logger.log(
            event="V3_ENGINE_INIT",
            session_id=self.session_id,
            data={
                "engine_id": self.engine_id,
                "world_name": self.world.name,
                "risk_threshold": self.risk_threshold,
                "max_branches": self.max_branches,
            },
        )

    def process_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        params: Dict[str, Any],
        risk_score: float,
        fuse_action: str,
        parent_node_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        params_summary = self._summarize_params(tool_name, params)

        node = self.behavior_graph.add_tool_call_as_node(
            agent_id=agent_id,
            tool_name=tool_name,
            params_summary=params_summary,
            fuse_action=fuse_action,
            shadow_risk_score=risk_score,
            parent_node_id=parent_node_id,
            inherited_risk=0.0,
            labels=labels or [],
        )

        self.behavior_graph.compute_risk_propagation()
        branches = self._generate_future_branches(agent_id, tool_name, risk_score)
        gate_result = self._governance_decision(risk_score, branches)

        what_if_result = None
        if self.enable_counterfactual and risk_score >= self.risk_threshold:
            what_if_result = self._counterfactual_whatif(agent_id, tool_name, risk_score, fuse_action)

        self.world.patch_state({
            f"last_tool_{agent_id}": {
                "tool": tool_name,
                "risk": risk_score,
                "action": fuse_action,
                "time": time.time(),
            }
        })

        self.audit_logger.log(
            event="TOOL_CALL_PROCESSED",
            session_id=self.session_id,
            data={
                "call_id": call_id,
                "node_id": node.node_id,
                "agent_id": agent_id,
                "tool_name": tool_name,
                "risk_score": risk_score,
                "fuse_action": fuse_action,
                "gate_action": gate_result.action.value if gate_result else "ALLOW",
                "branches_generated": len(branches),
                "whatif_triggered": what_if_result is not None,
            },
        )

        return {
            "call_id": call_id,
            "node_id": node.node_id,
            "behavior_graph_summary": self.behavior_graph.summary(),
            "gate_result": {
                "action": gate_result.action.value if gate_result else "ALLOW",
                "reason": gate_result.reason if gate_result else "no-gate",
                "score": gate_result.score if gate_result else 0.0,
            } if gate_result else None,
            "future_branches": [b.to_dict() if hasattr(b, 'to_dict') else str(b) for b in branches[:self.max_branches]],
            "whatif_result": what_if_result,
            "critical_nodes": [n.node_id for n in self.behavior_graph.get_critical_nodes()],
        }

    def fork_branch(self, branch_label: str, intervention: Dict[str, Any]) -> str:
        """手动创建分支（干预点）"""
        bp = self.branch_tree.fork(
            point_label=branch_label,
            state_snapshot=self.world.state.data,
            candidate_labels=[f"候选A: {branch_label}", f"候选B: {branch_label}"],
            governance_results=None,
            step=int(time.time()),
        )
        self._apply_intervention(intervention)
        branch_id = bp.candidates[0].branch_id if bp.candidates else bp.point_id
        self.audit_logger.log(
            event="BRANCH_FORKED",
            session_id=self.session_id,
            data={"branch_id": branch_id, "point_id": bp.point_id, "label": branch_label, "intervention": intervention},
        )
        return branch_id

    def get_governance_status(self) -> Dict[str, Any]:
        all_branches = self.branch_tree.get_all_branches()
        return {
            "session_id": self.session_id,
            "engine_id": self.engine_id,
            "risk_threshold": self.risk_threshold,
            "branch_count": len(all_branches),
            "behavior_graph": self.behavior_graph.summary(),
            "gate_count": len(self.governance_gates),
            "world_state_keys": list(self.world.state.data.keys()),
        }

    def export_chain(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "engine_id": self.engine_id,
            "behavior_graph": self.behavior_graph.to_graph_dict(),
            "branch_tree": {
                "root": self.branch_tree.root_branch.branch_id if self.branch_tree.root_branch else None,
                "active": self.branch_tree.active_branch.branch_id if self.branch_tree.active_branch else None,
                "total_branches": len(self.branch_tree.get_all_branches()),
                "branch_points": [
                    {"point_id": bp.point_id, "label": bp.label, "candidates": len(bp.candidates)}
                    for bp in (self.branch_tree.branch_points or [])
                ],
            },
            "audit_chain": self.audit_logger.export_chain(),
        }

    def _summarize_params(self, tool_name: str, params: Dict[str, Any]) -> str:
        sensitive = {"password", "token", "secret", "api_key", "authorization", "credential"}
        safe = {k: "***" if k.lower() in sensitive else v for k, v in params.items()}
        return f"{tool_name}({', '.join(f'{k}={v}' for k, v in safe.items())})"

    def _generate_future_branches(
        self, agent_id: str, tool_name: str, risk_score: float
    ) -> List[Branch]:
        if risk_score < self.risk_threshold:
            return []
        candidates = self._candidate_next_tools(agent_id, tool_name)
        cand_labels = [f"branch{i+1}:{agent_id}->{c}" for i, c in enumerate(candidates[:self.max_branches])]
        gov_results = [
            {"action": "ALLOW" if self._branch_risk_from_score(0.4 * risk_score) < self.risk_threshold else "REVIEW",
             "reason": "auto-eval"}
            for _ in cand_labels
        ]
        bp = self.branch_tree.fork(
            point_label=f"future:{agent_id}.{tool_name}",
            state_snapshot=self.world.state.data,
            candidate_labels=cand_labels,
            governance_results=gov_results,
            step=0,
        )
        return bp.candidates

    def _candidate_next_tools(self, agent_id: str, current_tool: str) -> List[str]:
        patterns = {
            "send_email": ["cursor.execute", "http_request"],
            "cursor.execute": ["cursor.execute", "http_request", "send_email"],
            "http_request": ["cursor.execute", "file_write"],
            "file_write": ["cursor.execute", "send_email"],
        }
        return patterns.get(current_tool, ["cursor.execute", "http_request"])

    def _branch_risk_from_score(self, score: float) -> float:
        return score

    def _governance_decision(self, risk_score: float, branches: List[Branch]) -> Optional[GovernanceResult]:
        if not self.governance_gates:
            if risk_score >= 0.90:
                action = GovernanceAction.BLOCK
                reason = "risk_score >= 0.90"
            elif risk_score >= self.risk_threshold:
                action = GovernanceAction.REVIEW
                reason = f"risk_score >= threshold({self.risk_threshold})"
            elif branches and any(self._branch_risk(b) > self.risk_threshold for b in branches):
                action = GovernanceAction.REVIEW
                reason = "future branch exceeds risk threshold"
            else:
                action = GovernanceAction.ALLOW
                reason = "below threshold"
            return GovernanceResult(action=action, reason=reason, score=risk_score, gate_name="DefaultV3Gate")
        for gate in self.governance_gates:
            result = gate.evaluate(score=risk_score, context={"branches": branches})
            if result.action != GovernanceAction.ALLOW:
                return result
        return GovernanceResult(action=GovernanceAction.ALLOW, reason="all gates allow", score=risk_score)

    def _branch_risk(self, branch: Branch) -> float:
        return getattr(branch, 'risk_score', 0.0) or 0.0

    def _counterfactual_whatif(
        self, agent_id: str, tool_name: str, risk_score: float, current_action: str
    ) -> Optional[Dict[str, Any]]:
        if not self.counterfactual:
            return None
        intervention = {
            "type": "block_tool_call",
            "agent_id": agent_id,
            "tool_name": tool_name,
            "risk_score": risk_score,
        }
        scenario = WhatIfScenario(
            scenario_id=f"whatif_{uuid.uuid4().hex[:8]}",
            label=f"假设拦截 {agent_id}.{tool_name}",
            hypothesis=intervention,
            projected_risk=risk_score * 0.5,
        )
        scenario.projected_outcome = {
            "blocked": True,
            "risk_reduced_by": risk_score * 0.5,
            "agents_affected": [agent_id],
        }
        scenario.comparison_with_baseline = {
            "baseline_risk": risk_score,
            "projected_risk_after_block": risk_score * 0.5,
            "delta": -risk_score * 0.5,
        }
        self.counterfactual.scenarios.append(scenario)
        return {
            "scenario_id": scenario.scenario_id,
            "label": scenario.label,
            "risk_delta": scenario.risk_delta(risk_score),
            "projected_outcome": scenario.projected_outcome,
            "comparison": scenario.comparison_with_baseline,
        }

    def _apply_intervention(self, intervention: Dict[str, Any]):
        itype = intervention.get("type", "")
        if itype == "block_tool_call":
            tool = intervention.get("tool_name", "")
            self.world.patch_state({f"blocked_{tool}": True})
        elif itype == "rate_limit":
            self.world.patch_state({"rate_limited_agents": intervention.get("agents", [])})
        elif itype == "escalate":
            self.world.patch_state({"escalated": True})