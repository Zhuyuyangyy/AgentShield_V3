"""
AgentShield V3 Benchmark Module Tests
======================================
Tests for the benchmark evaluation pipeline:
- Baseline risk scoring functions
- Evaluation metrics computation
- Trace schema validation
- Report generation
"""

import sys
from pathlib import Path

import pytest

_CURRENT_DIR = Path(__file__).parent.resolve()
_BACKEND_DIR = _CURRENT_DIR.parent
ROOT = str(_BACKEND_DIR.parent)
for path in [ROOT]:
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)


# ─── Baseline Risk Scoring Tests ─────────────────────────────────────────────

class TestBaselineRiskScoring:
    """Test the baseline risk scoring functions from benchmark/baselines.py."""

    def test_action_for_score_boundaries(self):
        from benchmark.baselines import action_for_score
        assert action_for_score(0.0) == "ALLOW"
        assert action_for_score(0.59) == "ALLOW"
        assert action_for_score(0.60) == "HUMAN_REVIEW"
        assert action_for_score(0.89) == "HUMAN_REVIEW"
        assert action_for_score(0.90) == "BLOCK"
        assert action_for_score(1.0) == "BLOCK"

    def test_clamp_function(self):
        from benchmark.baselines import clamp
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0

    def test_risk_tool_name_basic(self):
        """risk_tool_name returns a score in [0, 1] for various tools."""
        from benchmark.baselines import risk_tool_name
        for tool in ["read_file", "send_email", "cursor.execute", "http_request", "export_csv"]:
            score = risk_tool_name({"tool_name": tool})
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {tool}"

    def test_risk_content_keyword_sensitive(self):
        """Content with sensitive keywords scores higher than plain content."""
        from benchmark.baselines import risk_content_keyword
        safe = risk_content_keyword({"tool_input": {"path": "/tmp/report.txt"}})
        risky = risk_content_keyword({"tool_input": {"query": "SELECT password FROM users WHERE admin"}})
        assert risky > safe

    def test_risk_local_context_category_priors(self):
        """Different categories get different prior scores."""
        from benchmark.baselines import risk_local_context
        normal = risk_local_context({"category": "sensitive_data_access", "tool_name": "read", "tool_input": {}})
        escalation = risk_local_context({"category": "privilege_escalation", "tool_name": "read", "tool_input": {}})
        assert escalation > normal

    def test_risk_agent_shield_chain_aware(self):
        """AgentShield chain-aware baseline uses chain metadata for scoring."""
        from benchmark.baselines import risk_agent_shield
        case_no_chain = {
            "category": "behavior_chain_risk",
            "tool_name": "cursor.execute",
            "tool_input": {"sql": "SELECT * FROM users"},
            "attack_stage": "collect",
            "chain_id": "",
            "step_index": 0,
        }
        case_with_chain = dict(case_no_chain)
        case_with_chain["chain_id"] = "chain_001"
        case_with_chain["step_index"] = 3

        score_no_chain = risk_agent_shield(case_no_chain)
        score_with_chain = risk_agent_shield(case_with_chain)
        assert score_with_chain >= score_no_chain


# ─── Evaluation Metrics Tests ────────────────────────────────────────────────

class TestEvaluationMetrics:
    """Test the evaluate() function and metric computation."""

    def test_evaluate_returns_required_keys(self):
        """evaluate() returns all required metric keys."""
        from benchmark.baselines import evaluate, action_for_score

        def mock_predictor(case):
            return 0.5

        cases = [
            {"id": "c1", "expected_action": "ALLOW", "expected_risk_score": 0.3},
            {"id": "c2", "expected_action": "BLOCK", "expected_risk_score": 0.9},
        ]
        result = evaluate("test_model", mock_predictor, cases)
        assert "name" in result
        assert "total" in result
        assert "action_accuracy" in result
        assert "macro_f1" in result
        assert "block_recall" in result
        assert "false_allow_rate" in result
        assert "false_block_rate" in result
        assert "per_label" in result
        assert "confusion_matrix" in result

    def test_evaluate_perfect_predictor(self):
        """A perfect predictor achieves 100% accuracy."""
        from benchmark.baselines import evaluate

        cases = [
            {"id": "c1", "expected_action": "ALLOW", "expected_risk_score": 0.3},
            {"id": "c2", "expected_action": "HUMAN_REVIEW", "expected_risk_score": 0.7},
            {"id": "c3", "expected_action": "BLOCK", "expected_risk_score": 0.95},
        ]

        def perfect_predictor(case):
            return float(case["expected_risk_score"])

        result = evaluate("perfect", perfect_predictor, cases)
        assert result["action_accuracy"] == pytest.approx(1.0)
        assert result["macro_f1"] == pytest.approx(1.0)

    def test_evaluate_empty_cases(self):
        """evaluate() handles empty case list gracefully."""
        from benchmark.baselines import evaluate
        result = evaluate("empty", lambda c: 0.5, [])
        assert result["total"] == 0
        assert result["action_accuracy"] == 0.0

    def test_precision_recall_f1_formula(self):
        """precision_recall_f1 computes correct values."""
        from benchmark.baselines import precision_recall_f1
        p, r, f1 = precision_recall_f1(tp=8, fp=2, fn=1)
        assert p == pytest.approx(8 / 10)
        assert r == pytest.approx(8 / 9)
        expected_f1 = 2 * (8 / 10) * (8 / 9) / ((8 / 10) + (8 / 9))
        assert f1 == pytest.approx(expected_f1)

    def test_precision_recall_f1_zero_division(self):
        """precision_recall_f1 handles zero division gracefully."""
        from benchmark.baselines import precision_recall_f1
        p, r, f1 = precision_recall_f1(tp=0, fp=0, fn=0)
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0


# ─── Trace Schema Validation Tests ───────────────────────────────────────────

class TestTraceSchemaValidation:
    """Test the trace schema validation from benchmark/trace_schema.py."""

    def test_validate_trace_valid(self):
        from benchmark.trace_schema import validate_trace
        trace = {
            "trace_id": "t_001",
            "scenario_type": "normal_business_query",
            "chain_label": "ALLOW",
            "risk_path": [0],
            "critical_step": 0,
            "expected_intervention_step": -1,
            "source": "controlled_semireal",
            "human_reviewed": True,
            "steps": [
                {
                    "trace_id": "t_001",
                    "session_id": "s_001",
                    "agent_id": "agent_1",
                    "step": 0,
                    "parent_step": None,
                    "tool_name": "read_file",
                    "tool_input": {"path": "/tmp"},
                    "tool_output_summary": "ok",
                    "timestamp": "2026-01-01T00:00:00",
                    "local_risk_type": "safe",
                    "local_risk_score": 0.1,
                    "label": "ALLOW",
                }
            ],
        }
        validate_trace(trace)  # Should not raise

    def test_validate_trace_missing_key(self):
        from benchmark.trace_schema import validate_trace
        trace = {"trace_id": "t_001"}  # Missing many keys
        with pytest.raises(ValueError, match="missing keys"):
            validate_trace(trace)

    def test_validate_trace_invalid_label(self):
        from benchmark.trace_schema import validate_trace
        trace = {
            "trace_id": "t_001",
            "scenario_type": "test",
            "chain_label": "INVALID",
            "risk_path": [0],
            "critical_step": 0,
            "expected_intervention_step": 0,
            "source": "test",
            "human_reviewed": True,
            "steps": [
                {
                    "trace_id": "t_001", "session_id": "s", "agent_id": "a",
                    "step": 0, "parent_step": None, "tool_name": "t",
                    "tool_input": {}, "tool_output_summary": "ok",
                    "timestamp": "2026-01-01", "local_risk_type": "safe",
                    "local_risk_score": 0.1, "label": "ALLOW",
                }
            ],
        }
        with pytest.raises(ValueError, match="Invalid chain label"):
            validate_trace(trace)

    def test_validate_trace_empty_steps(self):
        from benchmark.trace_schema import validate_trace
        trace = {
            "trace_id": "t_001",
            "scenario_type": "test",
            "chain_label": "ALLOW",
            "risk_path": [],
            "critical_step": 0,
            "expected_intervention_step": 0,
            "source": "test",
            "human_reviewed": True,
            "steps": [],
        }
        with pytest.raises(ValueError, match="at least one step"):
            validate_trace(trace)

    def test_validate_trace_score_out_of_range(self):
        from benchmark.trace_schema import validate_trace
        trace = {
            "trace_id": "t_001",
            "scenario_type": "test",
            "chain_label": "ALLOW",
            "risk_path": [0],
            "critical_step": 0,
            "expected_intervention_step": 0,
            "source": "test",
            "human_reviewed": True,
            "steps": [
                {
                    "trace_id": "t_001", "session_id": "s", "agent_id": "a",
                    "step": 0, "parent_step": None, "tool_name": "t",
                    "tool_input": {}, "tool_output_summary": "ok",
                    "timestamp": "2026-01-01", "local_risk_type": "safe",
                    "local_risk_score": 1.5,  # Out of range
                    "label": "ALLOW",
                }
            ],
        }
        with pytest.raises(ValueError, match="between 0 and 1"):
            validate_trace(trace)

    def test_trace_label_enum_values(self):
        from benchmark.trace_schema import TraceLabel
        assert TraceLabel.ALLOW.value == "ALLOW"
        assert TraceLabel.HUMAN_REVIEW.value == "HUMAN_REVIEW"
        assert TraceLabel.BLOCK.value == "BLOCK"


# ─── Semireal Trace-to-Case Tests ────────────────────────────────────────────

class TestTraceToCaseConversion:
    """Test the trace_to_case conversion in evaluate_semireal.py."""

    def test_trace_to_case_basic(self):
        from benchmark.evaluate_semireal import trace_to_case
        trace = {
            "trace_id": "t_001",
            "scenario_type": "normal_business_query",
            "chain_label": "ALLOW",
            "critical_step": 0,
            "steps": [
                {
                    "step": 0,
                    "agent_id": "agent_1",
                    "tool_name": "read_file",
                    "tool_input": {"path": "/tmp"},
                    "local_risk_type": "safe",
                    "local_risk_score": 0.1,
                }
            ],
        }
        case = trace_to_case(trace)
        assert case["id"] == "t_001"
        assert case["expected_action"] == "ALLOW"
        assert case["agent_id"] == "agent_1"
        assert case["tool_name"] == "read_file"
        assert case["v3_specific"] is True
        assert case["semi_realistic_trace"] is True

    def test_trace_to_case_block_label(self):
        from benchmark.evaluate_semireal import trace_to_case
        trace = {
            "trace_id": "t_002",
            "scenario_type": "privilege_escalation",
            "chain_label": "BLOCK",
            "critical_step": 1,
            "steps": [
                {"step": 0, "agent_id": "a", "tool_name": "query", "tool_input": {}, "local_risk_type": "collect", "local_risk_score": 0.3},
                {"step": 1, "agent_id": "a", "tool_name": "send_email", "tool_input": {}, "local_risk_type": "exfiltrate", "local_risk_score": 0.95},
            ],
        }
        case = trace_to_case(trace)
        assert case["expected_action"] == "BLOCK"
        assert case["expected_risk_score"] >= 0.90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
