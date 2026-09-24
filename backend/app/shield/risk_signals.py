"""AgentShield V3 - Risk Signal and Graph Risk State models.

These types replace the old approach where risk_score was passed in
externally. Now the engine computes risk from behavior graph signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# Ceiling applied to the combined risk when the operator explicitly authorised
# the action. Authorisation suppresses presence-based alarms (that is what
# makes a user-requested payment pass) without erasing structural violations.
AUTHORISED_ACTION_CEILING = 0.55

# Ceiling applied when the call's entities were resolved from structured or
# financial content rather than an external fetch. Weaker than full
# authorisation: an entity arriving through a trusted *store* is more likely
# legitimate than one scraped off a web page, but the operator never named it,
# so it does not get the authorisation ceiling.
TRUSTED_ENTITY_CEILING = 0.70


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
    # ── Provenance / taint signals (stage D-F) ──────────────────────────
    # These look at *where content came from*, which is what a single-event
    # guardrail structurally cannot see.
    UNTRUSTED_INSTRUCTION = "untrusted_instruction"
    DESTINATION_PROVENANCE = "destination_provenance"
    INTENT_ORIGIN_MISMATCH = "intent_origin_mismatch"
    SENSITIVE_TO_EXTERNAL_FLOW = "sensitive_to_external_flow"
    UNTRUSTED_TO_PRIVILEGED_ACTION = "untrusted_to_privileged_action"
    # ── Trust calibration signals (v0.4) ────────────────────────────────
    # These *suppress* risk rather than raise it: they record why a call the
    # presence-based rules would flag is in fact authorised or benign.
    USER_AUTHORIZED_ACTION = "user_authorized_action"
    TRUSTED_ENTITY_RESOLUTION = "trusted_entity_resolution"


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
    # Artifacts this signal was derived from. Provenance signals use it so a
    # decision can be explained as "destination X first appeared in artifact Y".
    artifact_ids: List[str] = field(default_factory=list)
    # When set, this signal *caps* the combined risk instead of contributing to
    # it. Used by the v0.4 trust-calibration signals: without it, a low-scoring
    # "this looks authorised" signal is simply maxed away by the 0.9 presence
    # alarm it is meant to temper, and the tempering has no effect at all.
    caps_risk: Optional[float] = None

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

        The score is the **maximum** of the individual components, so a single
        decisive signal is never diluted by unrelated ones that happen to be
        zero. The previous weighted sum gave local_risk only 0.35 of the total
        and then multiplied by ``confidence``, which is a measure of *how much
        evidence* was seen, not of how dangerous the event is. A lone bulk
        delete scored local_risk=0.5 and came out at 0.14 -- under the 0.60
        review threshold -- so destructive operations were allowed.

        ``confidence`` now scales the result only mildly and never below the
        floor implied by the evidence: with no signals at all the score is 0
        regardless of confidence.

        Preserved invariant: when every component equals ``x`` and
        ``confidence == 1.0``, ``combined_risk == x``.
        """
        # ``signals`` is part of the max, not decoration. Provenance signals
        # (untrusted instruction, destination provenance) are appended by the
        # engine after the graph-context state is built; leaving them out of the
        # aggregate meant a 0.95 injection signal could accompany a 0.0 score.
        components = [
            self.local_risk,
            self.inherited_risk,
            self.path_risk,
            self.downstream_exposure,
        ]
        if self.signals:
            components.append(max(s.score for s in self.signals))
        peak = max(components) if components else 0.0

        if peak <= 0.0:
            return 0.0

        # v0.4: explicit operator authorisation caps the score.
        #
        # Authorisation is not just another signal to be maxed against -- the
        # whole point is that it *suppresses* the presence-based alarms. A task
        # that says "pay Apple the missing VAT" would otherwise be blocked
        # because the agent read transactions and then sent money, which is
        # exactly the 41.2% benign trace-block rate v0.3 measured.
        #
        # The cap is deliberately partial rather than zero: authorisation from
        # the operator's request does not erase a hard structural violation
        # (a bulk delete still reads as dangerous), it only bounds how high the
        # presence-based evidence may push the score.
        # Any signal carrying `caps_risk` bounds the peak. The lowest cap wins,
        # so an explicit authorisation still overrides a weaker trusted-entity
        # ceiling when both are present.
        caps = [s.caps_risk for s in self.signals if s.caps_risk is not None]
        if caps:
            peak = min(peak, *caps)

        # No confidence discount and no intervention bonus in the base case, so
        # that "all components equal x, confidence 1.0" yields exactly x -- the
        # invariant test_api_routes._make_risk_state relies on.
        score = peak
        if self.intervention_value > peak:
            # A very high intervention value can lift the score, but never by
            # more than the intervention value itself.
            score = self.intervention_value

        # ``confidence`` measures how much evidence was seen, not how dangerous
        # the event is. Discounting by it meant a single decisive signal
        # (confidence 0.6, i.e. "one signal, short chain") could never reach
        # the BLOCK threshold, which is exactly the thin-evidence case where
        # over-blocking is the safer error. It is therefore reported but does
        # not reduce the score.
        return max(0.0, min(1.0, score))

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
