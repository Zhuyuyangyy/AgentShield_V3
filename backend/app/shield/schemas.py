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
    """Create an ObservedToolEvent from a raw dict, stripping forbidden fields.

    Also filters out any keys that are not valid ObservedToolEvent fields,
    so datasets with extra columns (e.g. 'id', 'description') don't break.
    """
    import dataclasses as _dc
    forbidden = FORBIDDEN_FIELDS
    valid_fields = {f.name for f in _dc.fields(ObservedToolEvent)}
    # Map common dataset aliases to schema field names
    alias_map = {
        "id": "event_id",
        "case_id": "event_id",
        "tool": "tool_name",
        "params": "tool_input",
        "arguments": "tool_input",
        "input": "tool_input",
        "agent": "agent_id",
    }
    safe: Dict[str, Any] = {}
    for k, v in data.items():
        if k in forbidden:
            continue
        mapped = alias_map.get(k, k)
        if mapped in valid_fields:
            # Don't overwrite an explicitly-provided schema field with an alias
            if mapped not in safe or k == mapped:
                safe[mapped] = v
    # Ensure required fields have values
    safe.setdefault("event_id", data.get("id", data.get("case_id", "unknown")))
    safe.setdefault("session_id", data.get("session_id", data.get("chain_id", "default")))
    safe.setdefault("tool_name", data.get("tool_name", data.get("tool", "")))
    safe.setdefault("tool_input", data.get("tool_input", data.get("params", data.get("input", {}))))
    safe.setdefault("agent_id", data.get("agent_id", data.get("agent", "unknown")))
    return ObservedToolEvent(**safe)


def ground_truth_from_dict(data: dict) -> HiddenGroundTruth:
    """Create a HiddenGroundTruth from a raw dict."""
    event_id = data.get("event_id", data.get("id", data.get("case_id", "")))
    return HiddenGroundTruth(
        event_id=event_id,
        attack_stage=data.get("attack_stage", "unknown"),
        chain_id=data.get("chain_id", ""),
        step_index=data.get("step_index", 0),
        label=data.get("label", "ALLOW"),
        rationale=data.get("rationale", ""),
    )
