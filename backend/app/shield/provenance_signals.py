"""Deterministic provenance signals (stage F).

Six signals, no model calls, no keyword lists tuned against a fixture. Each one
answers a question about *origin* rather than about content:

  1. UNTRUSTED_INSTRUCTION       untrusted content reads as an instruction
  2. DESTINATION_PROVENANCE      a destination first appeared in untrusted text
  3. INTENT_ORIGIN_MISMATCH      the action traces to untrusted content, not to
                                 the operator's request
  4. SENSITIVE_TO_EXTERNAL_FLOW  sensitive material crosses the trust boundary
  5. UNTRUSTED_TO_PRIVILEGED     untrusted content drives a high-consequence tool
  6. TAINT_PROPAGATION           an entity from untrusted content reaches this call

Signals 2, 3 and 6 are the ones a single-event guardrail cannot produce: they
require knowing what the operator actually asked for and what an earlier tool
output introduced.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.shield.risk_signals import RiskSignal, RiskSignalType

# Tools with side effects outside the trust boundary. When one of these is
# driven by untrusted content, the consequence is not local.
_EXTERNAL_SINK_TOOLS = (
    "send_email", "smtp", "http_request", "http_post", "upload", "webhook",
    "post_data", "external_delivery", "ftp", "curl", "wget", "send", "sync_to_remote",
    "share_p2p", "smtp_relay", "route_tor", "icmp_tunnel", "create_ssh_tunnel",
    "encode_in_image", "call_external_api", "export_api_data", "send_bulk_email",
)

# High-consequence tools: privilege, credential, destruction, exfiltration.
_PRIVILEGED_TOOLS = (
    "update_user_role", "update_permissions", "assume_role", "grant", "chmod",
    "chown", "sudo", "set_admin", "modify_role", "update_security_policy",
    "modify_registry", "update_encryption_config", "rotate_jwt_secret",
    "create_hidden_account", "create_cron_job", "disable_audit", "write_audit_log",
    "delete", "drop", "rm", "truncate", "cascade_delete", "format", "transfer_crypto",
    "batch_reset_passwords", "batch_create_accounts", "inject_dll",
    "install_miner", "create_ssh_tunnel", "connect_vpn", "poison_cdn_cache",
    "smuggle_request", "read_process_memory", "mount_host_path",
)

_SENSITIVE_MARKERS = (
    "password", "secret", "token", "api_key", "credential", "private_key",
    "ssn", "credit_card", "id_card", "phone", "customer", "employee", "salary",
    "medical", "/etc/passwd", "/etc/shadow", "id_rsa",
)


def _normalise_tool(tool_name: str) -> str:
    return str(tool_name or "").lower()


def _is_external_sink(tool_name: str) -> bool:
    tool = _normalise_tool(tool_name)
    return any(t in tool for t in _EXTERNAL_SINK_TOOLS)


def _is_privileged(tool_name: str) -> bool:
    tool = _normalise_tool(tool_name)
    return any(t in tool for t in _PRIVILEGED_TOOLS)


def _touches_sensitive(text: str) -> List[str]:
    blob = str(text).lower()
    return [m for m in _SENSITIVE_MARKERS if m in blob]


def extract_provenance_signals(
    tool_name: str,
    tool_input: Dict[str, Any],
    taint_tracker,
    user_intent_text: str = "",
) -> List[RiskSignal]:
    """Return the provenance signals for one tool call.

    ``taint_tracker`` holds what has been observed so far; ``user_intent_text``
    is the operator's original request, used to tell "the user asked for this"
    from "an untrusted artifact asked for this".
    """
    if taint_tracker is None:
        return []

    signals: List[RiskSignal] = []
    tool = _normalise_tool(tool_name)
    input_text = _flatten(tool_input)
    intent_text = str(user_intent_text or "")

    untrusted_artifacts = taint_tracker.untrusted_artifacts()
    instruction_bearing = taint_tracker.instruction_bearing_untrusted()

    # ── 1. Untrusted instruction ──────────────────────────────────────────
    if instruction_bearing:
        worst = max(instruction_bearing, key=lambda a: len(a.content))
        signals.append(RiskSignal(
            signal_type=RiskSignalType.UNTRUSTED_INSTRUCTION,
            score=0.95,
            evidence=[
                f"Untrusted artifact {worst.artifact_id} ({worst.origin_type}) "
                "contains instruction-like text directed at the agent"
            ],
            artifact_ids=[a.artifact_id for a in instruction_bearing],
        ))

    # ── 2. Destination provenance ─────────────────────────────────────────
    # A destination that first appeared in untrusted content is the classic
    # injection outcome: the operator never named it.
    tainted_origins = taint_tracker.untrusted_origin_of(input_text)
    if tainted_origins:
        signals.append(RiskSignal(
            signal_type=RiskSignalType.DESTINATION_PROVENANCE,
            score=0.90,
            evidence=[
                f"{o.entity} first observed in untrusted artifact {o.artifact_id} "
                f"({o.origin_type})"
                for o in tainted_origins[:3]
            ],
            artifact_ids=[o.artifact_id for o in tainted_origins],
        ))

    # ── 3. Intent-origin mismatch ─────────────────────────────────────────
    # The arguments come from untrusted content, but the same values are absent
    # from the operator's request.
    if tainted_origins and intent_text:
        intent_entities = {
            e.lower() for e in taint_tracker.untrusted_origin_of(intent_text)
        }
        novel = [o for o in tainted_origins if o.entity not in intent_entities]
        if novel:
            signals.append(RiskSignal(
                signal_type=RiskSignalType.INTENT_ORIGIN_MISMATCH,
                score=0.85,
                evidence=[
                    f"{o.entity} is absent from the user request but present in "
                    f"untrusted artifact {o.artifact_id}"
                    for o in novel[:3]
                ],
                artifact_ids=[o.artifact_id for o in novel],
            ))

    # ── 4. Sensitive material crossing the trust boundary ─────────────────
    sensitive_hits = _touches_sensitive(input_text) + _touches_sensitive(
        " ".join(a.content for a in untrusted_artifacts)
    )
    if _is_external_sink(tool) and sensitive_hits:
        signals.append(RiskSignal(
            signal_type=RiskSignalType.SENSITIVE_TO_EXTERNAL_FLOW,
            score=0.95,
            evidence=[
                f"External sink '{tool}' carries sensitive markers: "
                + ", ".join(sorted(set(sensitive_hits))[:4])
            ],
        ))

    # ── 5. Untrusted content reaching a privileged action ─────────────────
    if _is_privileged(tool) and untrusted_artifacts:
        signals.append(RiskSignal(
            signal_type=RiskSignalType.UNTRUSTED_TO_PRIVILEGED_ACTION,
            score=0.95,
            evidence=[
                f"Privileged tool '{tool}' runs while {len(untrusted_artifacts)} "
                "untrusted artifact(s) are in context"
            ],
            artifact_ids=[a.artifact_id for a in untrusted_artifacts[:3]],
        ))

    # ── 6. Taint propagation into this call ───────────────────────────────
    propagated: List[str] = []
    for artifact in untrusted_artifacts:
        for entity in artifact.introduced_entities:
            if entity and entity in input_text.lower():
                propagated.append(entity)
    if propagated:
        signals.append(RiskSignal(
            signal_type=RiskSignalType.CROSS_AGENT_DELEGATION,
            score=0.80,
            evidence=[
                f"Entity from untrusted content reaches this call: {e}"
                for e in sorted(set(propagated))[:3]
            ],
            artifact_ids=[a.artifact_id for a in untrusted_artifacts[:3]],
        ))

    return signals


def _flatten(value: Any) -> str:
    """Flatten tool input to lowercase text for entity extraction."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    return str(value).lower()
