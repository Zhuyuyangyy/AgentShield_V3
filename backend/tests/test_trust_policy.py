"""Tests for the v0.4 trust policy and explicit user authorisation.

The v0.4 experiment was a negative result (see BENCHMARK_STATUS.md), but two
mechanisms in it are worth keeping and worth pinning:

* the tool-semantics trust classification, which is a real improvement over the
  binary "all output is untrusted" policy;
* the authorisation rule, whose *strictness* was validated empirically -- the
  loose leading-label match it originally used authorised 14 of 14 attack
  trajectories that v0.3 had blocked.

These tests pin the strict behaviour so the loose variant cannot come back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


class TestToolSemanticsTrustPolicy:
    def test_structured_stores_are_structured(self):
        from app.shield.trust_policy import TRUST_STRUCTURED, classify_tool

        for tool in ("get_day_calendar_events", "search_calendar_events",
                     "read_file", "list_files", "search_emails",
                     "get_unread_emails", "read_channel_messages"):
            assert classify_tool(tool) == TRUST_STRUCTURED, tool

    def test_external_fetches_are_external(self):
        from app.shield.trust_policy import TRUST_EXTERNAL, classify_tool

        for tool in ("get_webpage", "get_rating_reviews_for_hotels",
                     "get_all_restaurants_in_city", "download_from_url"):
            assert classify_tool(tool) == TRUST_EXTERNAL, tool

    def test_financial_tools_are_financial(self):
        from app.shield.trust_policy import TRUST_FINANCIAL, classify_tool

        for tool in ("get_most_recent_transactions", "send_money",
                     "get_account_balance", "create_invoice"):
            assert classify_tool(tool) == TRUST_FINANCIAL, tool

    def test_outbound_send_is_not_structured(self):
        """Sending is an action, not a store: it must not inherit a source prior."""
        from app.shield.trust_policy import TRUST_STRUCTURED, classify_tool

        assert classify_tool("send_email") != TRUST_STRUCTURED

    def test_unknown_tool_keeps_label_but_external_prior(self):
        from app.shield.trust_policy import (
            TRUST_EXTERNAL,
            TRUST_UNKNOWN,
            classify_tool,
            trust_prior,
        )

        result = classify_tool("totally_unheard_of_tool")
        assert result == TRUST_UNKNOWN
        # Same risk weight as a known external tool: never assume trust.
        assert trust_prior(result) == trust_prior(TRUST_EXTERNAL) == 1.0

    def test_priors_are_ordered_by_trust(self):
        from app.shield.trust_policy import (
            TRUST_EXTERNAL,
            TRUST_FINANCIAL,
            TRUST_STRUCTURED,
            trust_prior,
        )

        assert trust_prior(TRUST_STRUCTURED) < trust_prior(TRUST_FINANCIAL)
        assert trust_prior(TRUST_FINANCIAL) < trust_prior(TRUST_EXTERNAL)
        assert trust_prior(TRUST_EXTERNAL) == 1.0

    def test_policy_declares_itself_frozen(self):
        from app.shield.trust_policy import describe_policy

        policy = describe_policy()
        assert policy["frozen_before_measurement"] is True
        assert set(policy["classes"]) == {
            "structured", "financial", "external", "unknown"
        }


class TestUserAuthorisationIsStrict:
    """The loose leading-label match authorised 14/14 attack trajectories."""

    @staticmethod
    def _check(intent, tool, tool_input):
        from app.shield.authorization import user_authorises

        return user_authorises(intent, tool, tool_input)

    def test_exact_entity_is_authorised(self):
        result = self._check(
            "Please send the attendee list to reports@partner-example.com.",
            "send_email",
            {"to": "reports@partner-example.com", "body": "list"},
        )
        assert result["authorised"] is True
        assert result["family"] == "send"

    def test_leading_label_does_not_authorise(self):
        """reports@internal.com must not authorise reports@partner-example.com.

        The first implementation matched on ``entity.split("@")[0]``, so both
        reduced to "reports" and every injected destination whose local part
        resembled a legitimately-mentioned one was waved through.
        """
        result = self._check(
            "Send the report to reports@internal.com please.",
            "send_email",
            {"to": "reports@partner-example.com"},
        )
        assert result["authorised"] is False

    def test_action_family_must_match(self):
        """Naming one action does not authorise a different one."""
        result = self._check(
            "Send the summary to reports@partner-example.com.",
            "delete_file",
            {"file_id": "reports@partner-example.com"},
        )
        assert result["authorised"] is False

    def test_entity_must_appear_in_request(self):
        result = self._check(
            "Send the summary to my manager.",
            "send_email",
            {"to": "attacker@evil.example"},
        )
        assert result["authorised"] is False

    def test_empty_request_is_never_authorising(self):
        result = self._check("", "send_email", {"to": "a@b.com"})
        assert result["authorised"] is False

    def test_unclassified_tool_is_not_authorised(self):
        result = self._check(
            "Send it to reports@partner-example.com.",
            "some_unknown_tool",
            {"to": "reports@partner-example.com"},
        )
        assert result["authorised"] is False

    def test_evidence_explains_the_decision(self):
        result = self._check(
            "Please send the list to reports@partner-example.com.",
            "send_email",
            {"to": "reports@partner-example.com"},
        )
        assert "reports@partner-example.com" in result["matched_entities"]
        assert "reason" not in result


class TestAuthorisationCapsRisk:
    """An authorised action must suppress the presence-based alarm."""

    def test_ceiling_is_applied(self):
        from app.shield.risk_signals import (
            AUTHORISED_ACTION_CEILING,
            GraphRiskState,
            RiskSignalType,
        )

        state = GraphRiskState(
            local_risk=0.95,
            signals=[
                type(
                    "S",
                    (),
                    {"signal_type": RiskSignalType.USER_AUTHORIZED_ACTION,
                     "score": 0.20, "evidence": [], "artifact_ids": []},
                )()
            ],
            confidence=1.0,
        )
        assert state.combined_risk == pytest.approx(AUTHORISED_ACTION_CEILING)

    def test_without_authorisation_the_signal_still_dominates(self):
        from app.shield.risk_signals import GraphRiskState, RiskSignalType

        state = GraphRiskState(
            local_risk=0.95,
            signals=[
                type(
                    "S",
                    (),
                    {"signal_type": RiskSignalType.UNTRUSTED_INSTRUCTION,
                     "score": 0.95, "evidence": [], "artifact_ids": []},
                )()
            ],
            confidence=1.0,
        )
        assert state.combined_risk == pytest.approx(0.95)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
