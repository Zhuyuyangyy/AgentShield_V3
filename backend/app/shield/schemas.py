"""AgentShield V3 - Data Schemas for Fair Evaluation.

Separates observable fields (available to detector/scorer) from hidden
ground-truth labels (only available to evaluator).

HARD RULE:
  - scorer / detector can ONLY read ObservedToolEvent
  - evaluator can read HiddenGroundTruth
  - if a detector reads attack_stage / chain_id / step_index / label, the test MUST fail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class ObservedToolEvent:
    """Fields that a detector/scorer is allowed to observe.

    These are the only fields that should be passed to risk scoring functions.
    No ground-truth metadata (attack_stage, chain_id, step_index, label) is included.
    """
    event_id: str
    session_id: str
    parent_event_id: Optional[str] = None
    timestamp: float = 0.0
    agent_id: str = "unknown"
    agent_role: Optional[str] = None
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output_summary: Optional[str] = None
    resource_type: Optional[str] = None
    destination: Optional[str] = None
    # Computed fields from behavior graph (NOT ground truth)
    inherited_risk: float = 0.0
    downstream_exposure: float = 0.0
    chain_length: int = 0
    previous_tools: List[str] = field(default_factory=list)
    risk_signals: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HiddenGroundTruth:
    """Ground-truth labels for evaluation ONLY.

    These fields MUST NOT be accessed by any detector or scorer.
    Only the evaluator module may read these.
    """
    event_id: str
    attack_stage: str = "unknown"
    chain_id: str = ""
    step_index: int = 0
    label: Literal["ALLOW", "HUMAN_REVIEW", "BLOCK"] = "ALLOW"
    rationale: str = ""


# Fields that are strictly forbidden for detectors to access
FORBIDDEN_FIELDS: set = {"attack_stage", "chain_id", "step_index", "label", "rationale"}


def event_from_dict(data: dict) -> ObservedToolEvent:
    """Create an ObservedToolEvent from a raw dict, stripping forbidden fields."""
    forbidden = FORBIDDEN_FIELDS
    safe = {k: v for k, v in data.items() if k not in forbidden}
    return ObservedToolEvent(**safe)


def ground_truth_from_dict(data: dict) -> HiddenGroundTruth:
    """Create a HiddenGroundTruth from a raw dict."""
    return HiddenGroundTruth(
        event_id=data.get("event_id", ""),
        attack_stage=data.get("attack_stage", "unknown"),
        chain_id=data.get("chain_id", ""),
        step_index=data.get("step_index", 0),
        label=data.get("label", "ALLOW"),
        rationale=data.get("rationale", ""),
    )
