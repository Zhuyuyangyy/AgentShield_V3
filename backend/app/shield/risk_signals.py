"""AgentShield V3 - Risk Signal and Graph Risk State models.

These types replace the old approach where risk_score was passed in
externally. Now the engine computes risk from behavior graph signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


class RiskSignalType(str, Enum):
    """Types of risk signals that can be detected from a tool event."""
    SENSITIVE_SOURCE = "sensitive_source"
    EXTERNAL_SINK = "external_sink"
    PRIVILEGE_CHANGE = "privilege_change"
    AUDIT_TAMPER = "audit_tamper"
    BULK_OPERATION = "bulk_operation"
    CREDENTIAL_ACCESS = "credential_access"
    CROSS_AGENT_DELEGATION = "cross_agent_delegation"
    POLICY_EVASION = "policy_evasion"


@dataclass
class RiskSignal:
    """A single risk signal detected from a tool event or graph context.

    Signals are the atomic units of risk evidence. Multiple signals
    are combined by the GraphRiskState to produce a final risk score.
    """
    signal_type: RiskSignalType
    score: float  # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list)
    source_event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "score": round(self.score, 4),
            "evidence": self.evidence,
            "source_event_id": self.source_event_id,
        }


@dataclass
class GraphRiskState:
    """Risk state derived from the behavior graph.

    This replaces the old approach of using a single externally-provided
    risk_score. The final risk is computed from multiple graph-derived signals.
    """
    local_risk: float = 0.0         # Risk from the current event alone
    inherited_risk: float = 0.0     # Risk propagated from upstream nodes
    downstream_exposure: float = 0.0  # Risk exposure to downstream nodes
    path_risk: float = 0.0          # Max risk along the critical path
    intervention_value: float = 0.0  # Value of intervening at this point
    confidence: float = 1.0         # Confidence in the risk assessment
    signals: List[RiskSignal] = field(default_factory=list)

    @property
    def combined_risk(self) -> float:
        """Compute the final combined risk score from all components.

        Uses a weighted combination where:
        - Local risk is the primary signal (weight 0.35)
        - Inherited risk captures upstream danger (weight 0.25)
        - Path risk captures chain-level danger (weight 0.20)
        - Downstream exposure captures potential future harm (weight 0.15)
        - Confidence modulates the overall score (weight 0.05)

        The result is clamped to [0.0, 1.0].
        """
        raw = (
            0.35 * self.local_risk
            + 0.25 * self.inherited_risk
            + 0.20 * self.path_risk
            + 0.15 * self.downstream_exposure
            + 0.05 * self.intervention_value
        )
        # Modulate by confidence (low confidence -> push toward review threshold)
        adjusted = raw * self.confidence + 0.5 * (1.0 - self.confidence) * raw
        return max(0.0, min(1.0, adjusted))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_risk": round(self.local_risk, 4),
            "inherited_risk": round(self.inherited_risk, 4),
            "downstream_exposure": round(self.downstream_exposure, 4),
            "path_risk": round(self.path_risk, 4),
            "intervention_value": round(self.intervention_value, 4),
            "confidence": round(self.confidence, 4),
            "combined_risk": round(self.combined_risk, 4),
            "signals": [s.to_dict() for s in self.signals],
        }
