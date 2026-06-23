"""AgentShield V3 - Risk Signal Extractor.

Extracts risk signals from tool events and behavior graph context.
This replaces the old approach of using externally-provided risk_score.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.shield.risk_signals import RiskSignal, RiskSignalType, GraphRiskState
from app.shield.schemas import ObservedToolEvent


# ─── Pattern Definitions ─────────────────────────────────────────────────────

SENSITIVE_SOURCE_PATTERNS = {
    "execute_sql", "cursor.execute", "database_query", "read_file",
    "load_data", "fetch_records", "query_api",
}

EXTERNAL_SINK_PATTERNS = {
    "send_email", "http_request", "upload_file", "webhook_call",
    "export_csv", "external_delivery", "post_data",
}

PRIVILEGE_CHANGE_PATTERNS = {
    "modify_role", "update_permission", "change_config",
    "set_admin", "grant_access", "escalate_privilege",
}

AUDIT_TAMPER_PATTERNS = {
    "disable_audit", "delete_log", "clear_history",
    "modify_log", "audit_log_write",
}

BULK_OPERATION_PATTERNS = {
    "bulk_delete", "batch_update", "mass_operation",
    "drop_table", "truncate",
}

CREDENTIAL_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api_key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"private_key", re.IGNORECASE),
]

SENSITIVE_DATA_PATTERNS = [
    re.compile(r"ssn|social_security", re.IGNORECASE),
    re.compile(r"credit_card|card_number", re.IGNORECASE),
    re.compile(r"id_card|identity", re.IGNORECASE),
    re.compile(r"phone|mobile|telephone", re.IGNORECASE),
    re.compile(r"email.*@.*\.(com|org|net)", re.IGNORECASE),
    re.compile(r"address|home_addr", re.IGNORECASE),
]

POLICY_EVASION_PATTERNS = [
    re.compile(r"ignore\s+(previous|above|all)", re.IGNORECASE),
    re.compile(r"bypass", re.IGNORECASE),
    re.compile(r"override\s+(policy|rule|check)", re.IGNORECASE),
]


class RiskSignalExtractor:
    """Extracts risk signals from tool events and graph context.

    This is the core component that replaces the old externally-provided
    risk_score. It computes risk from observable event features and
    behavior graph state.
    """

    def __init__(self):
        self.signal_weights: Dict[RiskSignalType, float] = {
            RiskSignalType.SENSITIVE_SOURCE: 0.25,
            RiskSignalType.EXTERNAL_SINK: 0.35,
            RiskSignalType.PRIVILEGE_CHANGE: 0.40,
            RiskSignalType.AUDIT_TAMPER: 0.45,
            RiskSignalType.BULK_OPERATION: 0.50,
            RiskSignalType.CREDENTIAL_ACCESS: 0.30,
            RiskSignalType.CROSS_AGENT_DELEGATION: 0.20,
            RiskSignalType.POLICY_EVASION: 0.55,
        }

    def extract_signals(
        self,
        event: ObservedToolEvent,
        graph_inherited_risk: float = 0.0,
        graph_downstream_exposure: float = 0.0,
        graph_path_risk: float = 0.0,
    ) -> List[RiskSignal]:
        """Extract all risk signals from an observed tool event."""
        signals: List[RiskSignal] = []

        tool = event.tool_name.lower()
        tool_input_str = str(event.tool_input).lower()

        # 1. Sensitive source detection
        if any(pattern in tool for pattern in SENSITIVE_SOURCE_PATTERNS):
            score = self.signal_weights[RiskSignalType.SENSITIVE_SOURCE]
            # Boost if accessing sensitive data
            for pattern in SENSITIVE_DATA_PATTERNS:
                if pattern.search(tool_input_str):
                    score = min(1.0, score + 0.2)
                    break
            signals.append(RiskSignal(
                signal_type=RiskSignalType.SENSITIVE_SOURCE,
                score=score,
                evidence=[f"Tool '{tool}' accesses sensitive data source"],
                source_event_id=event.event_id,
            ))

        # 2. External sink detection
        if any(pattern in tool for pattern in EXTERNAL_SINK_PATTERNS):
            score = self.signal_weights[RiskSignalType.EXTERNAL_SINK]
            # Boost if previous tool was a sensitive source
            prev_tools = event.previous_tools
            if prev_tools and any(
                any(sp in pt.lower() for sp in SENSITIVE_SOURCE_PATTERNS)
                for pt in prev_tools[-3:]
            ):
                score = min(1.0, score + 0.3)
                signals.append(RiskSignal(
                    signal_type=RiskSignalType.SENSITIVE_SOURCE,
                    score=0.3,
                    evidence=[f"Previous tool in chain was a sensitive source"],
                    source_event_id=event.event_id,
                ))
            signals.append(RiskSignal(
                signal_type=RiskSignalType.EXTERNAL_SINK,
                score=score,
                evidence=[f"Tool '{tool}' sends data externally"],
                source_event_id=event.event_id,
            ))

        # 3. Privilege change detection
        if any(pattern in tool for pattern in PRIVILEGE_CHANGE_PATTERNS):
            signals.append(RiskSignal(
                signal_type=RiskSignalType.PRIVILEGE_CHANGE,
                score=self.signal_weights[RiskSignalType.PRIVILEGE_CHANGE],
                evidence=[f"Tool '{tool}' modifies privileges or access control"],
                source_event_id=event.event_id,
            ))

        # 4. Audit tamper detection
        if any(pattern in tool for pattern in AUDIT_TAMPER_PATTERNS):
            signals.append(RiskSignal(
                signal_type=RiskSignalType.AUDIT_TAMPER,
                score=self.signal_weights[RiskSignalType.AUDIT_TAMPER],
                evidence=[f"Tool '{tool}' modifies audit logging"],
                source_event_id=event.event_id,
            ))

        # 5. Bulk operation detection
        if any(pattern in tool for pattern in BULK_OPERATION_PATTERNS):
            signals.append(RiskSignal(
                signal_type=RiskSignalType.BULK_OPERATION,
                score=self.signal_weights[RiskSignalType.BULK_OPERATION],
                evidence=[f"Tool '{tool}' performs bulk/destructive operation"],
                source_event_id=event.event_id,
            ))

        # 6. Credential access detection
        for pattern in CREDENTIAL_PATTERNS:
            if pattern.search(tool_input_str):
                signals.append(RiskSignal(
                    signal_type=RiskSignalType.CREDENTIAL_ACCESS,
                    score=self.signal_weights[RiskSignalType.CREDENTIAL_ACCESS],
                    evidence=[f"Tool input contains credential pattern: {pattern.pattern}"],
                    source_event_id=event.event_id,
                ))
                break

        # 7. Cross-agent delegation
        if event.agent_role and "delegate" in tool:
            signals.append(RiskSignal(
                signal_type=RiskSignalType.CROSS_AGENT_DELEGATION,
                score=self.signal_weights[RiskSignalType.CROSS_AGENT_DELEGATION],
                evidence=[f"Agent '{event.agent_id}' delegates via tool '{tool}'"],
                source_event_id=event.event_id,
            ))

        # 8. Policy evasion detection
        for pattern in POLICY_EVASION_PATTERNS:
            if pattern.search(tool_input_str):
                signals.append(RiskSignal(
                    signal_type=RiskSignalType.POLICY_EVASION,
                    score=self.signal_weights[RiskSignalType.POLICY_EVASION],
                    evidence=[f"Tool input contains policy evasion pattern: {pattern.pattern}"],
                    source_event_id=event.event_id,
                ))
                break

        return signals

    def compute_graph_risk_state(
        self,
        event: ObservedToolEvent,
        graph_inherited_risk: float = 0.0,
        graph_downstream_exposure: float = 0.0,
        graph_path_risk: float = 0.0,
    ) -> GraphRiskState:
        """Compute the full GraphRiskState for an event.

        This is the main entry point for the new risk computation pipeline.
        """
        signals = self.extract_signals(
            event, graph_inherited_risk, graph_downstream_exposure, graph_path_risk
        )

        # Local risk from signals
        if signals:
            # Weighted combination of signal scores
            total_weight = sum(self.signal_weights.get(s.signal_type, 0.3) for s in signals)
            weighted_sum = sum(
                self.signal_weights.get(s.signal_type, 0.3) * s.score
                for s in signals
            )
            local_risk = min(1.0, weighted_sum / max(total_weight, 0.01))
        else:
            local_risk = 0.0

        # Compute intervention value
        intervention_value = 0.0
        if graph_downstream_exposure > 0.3:
            intervention_value = min(1.0, graph_downstream_exposure * 0.8)

        # Confidence based on number of signals and graph connectivity
        confidence = min(1.0, 0.5 + 0.1 * len(signals) + 0.1 * min(event.chain_length, 5))

        return GraphRiskState(
            local_risk=local_risk,
            inherited_risk=graph_inherited_risk,
            downstream_exposure=graph_downstream_exposure,
            path_risk=graph_path_risk,
            intervention_value=intervention_value,
            confidence=confidence,
            signals=signals,
        )
