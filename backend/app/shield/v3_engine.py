"""AgentShield V3 core engine.

This module restores the V3 contract used by the API, tests, and benchmark:
tool calls become behavior-graph nodes, receive a governance gate decision,
optionally create future branches, and produce a compact what-if analysis.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.shield.agent_behavior_graph import AgentBehaviorGraph
from app.shield.v3_audit_logger import V3AuditLogger


@dataclass
class _WorldState:
    data: Dict[str, Any] = field(default_factory=dict)


class _World:
    def __init__(self, name: str):
        self.name = name
        self.state = _WorldState()

    def patch_state(self, patch: Dict[str, Any]) -> None:
        self.state.data.update(patch)


@dataclass
class _Branch:
    branch_id: str
    label: str
    risk_score: float
    governance_action: str
    governance_reason: str
    probability: float
    step: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "label": self.label,
            "risk_score": round(self.risk_score, 3),
            "governance_action": self.governance_action,
            "governance_reason": self.governance_reason,
            "probability": self.probability,
            "step": self.step,
            "timestamp": self.timestamp,
        }


@dataclass
class _BranchPoint:
    point_id: str
    label: str
    candidates: List[_Branch]
    step: int
    timestamp: float = field(default_factory=time.time)


class _BranchTree:
    def __init__(self, initial_state: Dict[str, Any]):
        root = _Branch(
            branch_id=f"branch_{uuid.uuid4().hex[:8]}",
            label="root",
            risk_score=0.0,
            governance_action="ALLOW",
            governance_reason="root",
            probability=1.0,
            step=0,
        )
        self.root_branch = root
        self.active_branch = root
        self.branch_points: List[_BranchPoint] = []
        self.all_branches: Dict[str, _Branch] = {root.branch_id: root}
        self.initial_state = dict(initial_state)

    def fork(
        self,
        point_label: str,
        candidate_labels: List[str],
        candidate_risks: List[float],
        step: int,
    ) -> _BranchPoint:
        probability = 1.0 / max(len(candidate_labels), 1)
        candidates: List[_Branch] = []
        for index, label in enumerate(candidate_labels):
            risk = candidate_risks[index] if index < len(candidate_risks) else 0.0
            action = _action_for_score(risk)
            branch = _Branch(
                branch_id=f"branch_{uuid.uuid4().hex[:8]}",
                label=label,
                risk_score=risk,
                governance_action=action,
                governance_reason=f"projected risk {risk:.2f}",
                probability=probability,
                step=step,
            )
            candidates.append(branch)
            self.all_branches[branch.branch_id] = branch

        point = _BranchPoint(
            point_id=f"bp_{uuid.uuid4().hex[:8]}",
            label=point_label,
            candidates=candidates,
            step=step,
        )
        self.branch_points.append(point)
        allowed = [branch for branch in candidates if branch.governance_action == "ALLOW"]
        if candidates:
            self.active_branch = allowed[0] if allowed else min(candidates, key=lambda b: b.risk_score)
        return point

    def get_all_branches(self) -> List[_Branch]:
        return list(self.all_branches.values())


def _action_for_score(score: float) -> str:
    if score >= 0.90:
        return "BLOCK"
    if score >= 0.60:
        return "HUMAN_REVIEW"
    return "ALLOW"


def _risk_level_for_score(score: float) -> str:
    if score >= 0.90:
        return "critical"
    if score >= 0.70:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


class V3ShieldEngine:
    """V3 engine for behavior-chain governance."""

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

        self.world = _World(world_name)
        self.world.patch_state({"session_id": session_id, "v3_engine_id": self.engine_id})
        self.branch_tree = _BranchTree(self.world.state.data)
        self.behavior_graph = AgentBehaviorGraph(session_id=session_id)
        self.audit_logger = V3AuditLogger()
        self.governance_gates: List[Any] = []
        self._gate_count = 0

        self.audit_logger.log(
            event="V3_ENGINE_INIT",
            session_id=session_id,
            data={
                "engine_id": self.engine_id,
                "world_name": world_name,
                "risk_threshold": risk_threshold,
                "max_branches": max_branches,
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
        risk_score = max(0.0, min(float(risk_score), 1.0))
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        action = _action_for_score(risk_score)
        node_action = self._node_action(action)

        node = self.behavior_graph.add_tool_call_as_node(
            agent_id=agent_id,
            tool_name=tool_name,
            params_summary=self._summarize_params(tool_name, params),
            fuse_action=node_action,
            shadow_risk_score=risk_score,
            parent_node_id=parent_node_id,
            inherited_risk=0.0,
            labels=labels or [],
        )
        self.behavior_graph.compute_risk_propagation()

        branches = self._generate_future_branches(agent_id, tool_name, risk_score)
        gate_result = {
            "action": action,
            "reason": self._gate_reason(risk_score, action),
            "score": risk_score,
            "risk_level": _risk_level_for_score(risk_score),
            "gate_name": "DefaultV3Gate",
        }
        self._gate_count += 1

        whatif_result = None
        if self.enable_counterfactual and risk_score >= self.risk_threshold:
            whatif_result = self._counterfactual_whatif(agent_id, tool_name, risk_score, action)

        self.world.patch_state(
            {
                f"last_tool_{agent_id}": {
                    "tool": tool_name,
                    "risk": risk_score,
                    "action": action,
                    "time": time.time(),
                }
            }
        )
        self.audit_logger.log(
            event="TOOL_CALL_PROCESSED",
            session_id=self.session_id,
            data={
                "call_id": call_id,
                "node_id": node.node_id,
                "agent_id": agent_id,
                "tool_name": tool_name,
                "risk_score": risk_score,
                "gate_action": action,
                "branches_generated": len(branches),
                "whatif_triggered": whatif_result is not None,
            },
        )

        return {
            "call_id": call_id,
            "node_id": node.node_id,
            "session_id": self.session_id,
            "decision": action.lower() if action != "HUMAN_REVIEW" else "review",
            "risk_level": _risk_level_for_score(risk_score),
            "risk_score": risk_score,
            "reasoning": gate_result["reason"],
            "behavior_graph_summary": self.behavior_graph.summary(),
            "gate_result": gate_result,
            "future_branches": [branch.to_dict() for branch in branches],
            "whatif_result": whatif_result,
            "critical_nodes": [n.node_id for n in self.behavior_graph.get_critical_nodes()],
        }

    def fork_branch(self, branch_label: str, intervention: Dict[str, Any]) -> str:
        risk = float(intervention.get("risk_score", 0.0) or 0.0)
        point = self.branch_tree.fork(
            point_label=branch_label,
            candidate_labels=[branch_label],
            candidate_risks=[risk],
            step=len(self.branch_tree.branch_points) + 1,
        )
        self._apply_intervention(intervention)
        branch_id = point.candidates[0].branch_id if point.candidates else point.point_id
        self.audit_logger.log(
            event="BRANCH_FORKED",
            session_id=self.session_id,
            data={"branch_id": branch_id, "label": branch_label, "intervention": intervention},
        )
        return branch_id

    def get_governance_status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "engine_id": self.engine_id,
            "risk_threshold": self.risk_threshold,
            "branch_count": len(self.branch_tree.get_all_branches()),
            "behavior_graph": self.behavior_graph.summary(),
            "gate_count": self._gate_count,
            "world_state_keys": list(self.world.state.data.keys()),
        }

    def export_chain(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "engine_id": self.engine_id,
            "behavior_graph": self.behavior_graph.to_graph_dict(),
            "branch_tree": {
                "root": self.branch_tree.root_branch.branch_id,
                "active": self.branch_tree.active_branch.branch_id,
                "total_branches": len(self.branch_tree.get_all_branches()),
                "branch_points": [
                    {
                        "point_id": point.point_id,
                        "label": point.label,
                        "candidates": len(point.candidates),
                    }
                    for point in self.branch_tree.branch_points
                ],
            },
            "audit_chain": self.audit_logger.export_chain(),
        }

    def _generate_future_branches(
        self, agent_id: str, tool_name: str, risk_score: float
    ) -> List[_Branch]:
        if risk_score < self.risk_threshold:
            return []

        next_tools = self._candidate_next_tools(tool_name)[: self.max_branches]
        candidate_labels = [
            f"{agent_id}:{tool_name}->candidate_{index + 1}:{next_tool}"
            for index, next_tool in enumerate(next_tools)
        ]
        candidate_risks = [
            max(0.0, min(1.0, risk_score * factor))
            for factor in [0.45, 0.65, 0.85, 0.30, 0.55][: len(candidate_labels)]
        ]
        point = self.branch_tree.fork(
            point_label=f"future:{agent_id}.{tool_name}",
            candidate_labels=candidate_labels,
            candidate_risks=candidate_risks,
            step=len(self.branch_tree.branch_points) + 1,
        )
        return point.candidates

    @staticmethod
    def _candidate_next_tools(current_tool: str) -> List[str]:
        tool = current_tool.lower()
        if "email" in tool or "smtp" in tool:
            return ["external_delivery_receipt", "audit_log_write", "http_request"]
        if "sql" in tool or "cursor" in tool or "database" in tool:
            return ["export_csv", "send_email", "http_request", "audit_log_write"]
        if "http" in tool or "upload" in tool or "webhook" in tool:
            return ["response_parse", "file_write", "send_email"]
        return ["audit_log_write", "http_request", "cursor.execute"]

    @staticmethod
    def _summarize_params(tool_name: str, params: Dict[str, Any]) -> str:
        sensitive_keys = {"password", "token", "secret", "api_key", "authorization", "credential"}
        safe = {
            str(key): "***" if str(key).lower() in sensitive_keys else value
            for key, value in params.items()
        }
        body = ", ".join(f"{key}={value}" for key, value in safe.items())
        return f"{tool_name}({body})"

    @staticmethod
    def _node_action(action: str) -> str:
        if action == "BLOCK":
            return "block"
        if action == "HUMAN_REVIEW":
            return "human_review"
        return "allow"

    @staticmethod
    def _gate_reason(risk_score: float, action: str) -> str:
        if action == "BLOCK":
            return f"risk_score {risk_score:.2f} >= 0.90"
        if action == "HUMAN_REVIEW":
            return f"0.60 <= risk_score {risk_score:.2f} < 0.90"
        return f"risk_score {risk_score:.2f} < 0.60"

    @staticmethod
    def _counterfactual_whatif(
        agent_id: str, tool_name: str, risk_score: float, action: str
    ) -> Dict[str, Any]:
        projected_risk = round(risk_score * 0.5, 3)
        risk_delta = round(projected_risk - risk_score, 3)
        return {
            "scenario_id": f"whatif_{uuid.uuid4().hex[:8]}",
            "label": f"block {agent_id}.{tool_name} before execution",
            "baseline_action": action,
            "hypothesis": {
                "type": "block_tool_call",
                "agent_id": agent_id,
                "tool_name": tool_name,
            },
            "risk_delta": risk_delta,
            "projected_outcome": {
                "blocked": True,
                "baseline_risk": risk_score,
                "projected_risk": projected_risk,
                "risk_reduced_by": round(risk_score - projected_risk, 3),
                "agents_affected": [agent_id],
            },
            "comparison": {
                "baseline_risk": risk_score,
                "projected_risk_after_block": projected_risk,
                "delta": risk_delta,
            },
        }

    def _apply_intervention(self, intervention: Dict[str, Any]) -> None:
        itype = intervention.get("type", "")
        if itype == "block_tool_call":
            self.world.patch_state({f"blocked_{intervention.get('tool_name', '')}": True})
        elif itype == "rate_limit":
            self.world.patch_state({"rate_limited_agents": intervention.get("agents", [])})
        elif itype == "escalate":
            self.world.patch_state({"escalated": True})
