"""
Tests for BenefitsAgent LLM integration (Task 5).

All tests are offline — no real API key or network calls required.
The Anthropic API is mocked via unittest.mock.patch throughout.

Test groups:
  1. LLM success path        — clean response passes through unchanged
  2. Overclaim rewrite       — LLM output with overclaims is cleaned before return
  3. LLM fallback            — LLMUnavailableError triggers rule-based fallback
  4. Missing API key         — RuntimeError propagates (not swallowed by agent)
  5. Prompt content          — evidence items and hard rules appear in the prompt
  6. node_benefits graph     — fallback flag is reflected in pipeline state

Run from backend/:
    pytest tests/test_benefits_agent_llm.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from agents.benefits_agent import BenefitsAgent, _SYSTEM_PROMPT
from graph.nodes import node_benefits
from graph.state import make_initial_state
from llm.client import LLMUnavailableError
from schemas.decision_schema import AgentResponse, EvidenceItem
from schemas.event_schema import EventType, IncomingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    text: str = "Apply for senior pension benefit eligibility.",
    event_type: EventType = EventType.FORM_SCREEN,
) -> IncomingEvent:
    return IncomingEvent(
        event_type=event_type,
        source_app="test.app",
        redacted_text=text,
        timestamp=datetime.now(timezone.utc),
        user_id="usr_test_llm",
    )


def _make_evidence(tier: int = 1, title: str = "Official Pension Guide") -> EvidenceItem:
    return EvidenceItem(
        source_id="src_001",
        title=title,
        tier=tier,
        snippet="Persons aged 60 and above may apply for the senior pension program.",
        relevance_score=0.85,
    )


# ---------------------------------------------------------------------------
# Test Group 1 — LLM success path
# ---------------------------------------------------------------------------

class TestLLMSuccessPath:
    """When the LLM responds normally, used_fallback must be False and
    the response text must come from the LLM (post-rewrite)."""

    @patch("agents.benefits_agent.call_llm_race")
    def test_used_fallback_is_false_on_success(self, mock_call_llm):
        mock_call_llm.return_value = (
            "You may qualify based on the information provided for the senior pension program. "
            "Please verify with the official agency."
        )
        resp = BenefitsAgent().run(_make_event())
        assert resp.used_fallback is False

    @patch("agents.benefits_agent.call_llm_race")
    def test_output_text_comes_from_llm(self, mock_call_llm):
        expected = "You may be eligible for housing support. Please verify with the agency."
        mock_call_llm.return_value = expected
        resp = BenefitsAgent().run(_make_event())
        assert resp.output_text == expected

    @patch("agents.benefits_agent.call_llm_race")
    def test_confidence_is_0_75_on_llm_success(self, mock_call_llm):
        mock_call_llm.return_value = "You may qualify based on the information provided."
        resp = BenefitsAgent().run(_make_event())
        assert resp.confidence == 0.75

    @patch("agents.benefits_agent.call_llm_race")
    def test_requires_human_review_always_true(self, mock_call_llm):
        """Benefits guidance always requires human review per policy."""
        mock_call_llm.return_value = "You may be eligible. Please verify."
        resp = BenefitsAgent().run(_make_event())
        assert resp.requires_human_review is True

    @patch("agents.benefits_agent.call_llm_race")
    def test_agent_name_is_benefits_agent(self, mock_call_llm):
        mock_call_llm.return_value = "You may be eligible for assistance."
        resp = BenefitsAgent().run(_make_event())
        assert resp.agent_name == "BenefitsAgent"

    @patch("agents.benefits_agent.call_llm_race")
    def test_returns_agent_response_instance(self, mock_call_llm):
        mock_call_llm.return_value = "You may qualify based on the information provided."
        resp = BenefitsAgent().run(_make_event())
        assert isinstance(resp, AgentResponse)


# ---------------------------------------------------------------------------
# Test Group 2 — Overclaim rewrite applied to LLM output
# ---------------------------------------------------------------------------

class TestOverclaimRewriteOnLLMOutput:
    """The critic-style _rewrite() must be applied to LLM output before
    returning, using the same rules from critic_agent.py (no duplication)."""

    @patch("agents.benefits_agent.call_llm_race")
    def test_you_qualify_is_rewritten(self, mock_call_llm):
        mock_call_llm.return_value = "You qualify for the senior pension program."
        resp = BenefitsAgent().run(_make_event())
        assert "you qualify" not in resp.output_text.lower()
        assert "may qualify" in resp.output_text.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_you_are_eligible_is_rewritten(self, mock_call_llm):
        mock_call_llm.return_value = "You are eligible for the emergency housing benefit."
        resp = BenefitsAgent().run(_make_event())
        assert "you are eligible" not in resp.output_text.lower()
        assert "may be eligible" in resp.output_text.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_guaranteed_is_rewritten(self, mock_call_llm):
        mock_call_llm.return_value = "This benefit amount is guaranteed for seniors over 60."
        resp = BenefitsAgent().run(_make_event())
        assert "guaranteed" not in resp.output_text.lower()
        assert "possibly available" in resp.output_text.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_you_will_receive_is_rewritten(self, mock_call_llm):
        mock_call_llm.return_value = "You will receive PKR 2000 per month under this scheme."
        resp = BenefitsAgent().run(_make_event())
        assert "you will receive" not in resp.output_text.lower()
        assert "may receive" in resp.output_text.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_clean_llm_output_passes_unchanged(self, mock_call_llm):
        """Clean, already-hedged LLM output must not be altered."""
        clean = (
            "You may be eligible for support programs based on your circumstances. "
            "Please contact the official helpline to verify your situation."
        )
        mock_call_llm.return_value = clean
        resp = BenefitsAgent().run(_make_event())
        assert resp.output_text == clean
        assert resp.used_fallback is False

    @patch("agents.benefits_agent.call_llm_race")
    def test_multiple_overclaims_all_rewritten(self, mock_call_llm):
        mock_call_llm.return_value = (
            "You qualify and you are eligible. This is guaranteed and confirmed."
        )
        resp = BenefitsAgent().run(_make_event())
        out = resp.output_text.lower()
        assert "you qualify" not in out
        assert "you are eligible" not in out
        assert "guaranteed" not in out
        assert "confirmed" not in out


# ---------------------------------------------------------------------------
# Test Group 3 — LLMUnavailableError triggers rule-based fallback
# ---------------------------------------------------------------------------

class TestLLMFallback:
    """On LLMUnavailableError the agent must return a safe rule-based response
    with used_fallback=True.  The fallback must never contain overclaims."""

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("timeout"))
    def test_fallback_sets_used_fallback_true(self, _):
        resp = BenefitsAgent().run(_make_event())
        assert resp.used_fallback is True

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("timeout"))
    def test_fallback_confidence_is_low(self, _):
        resp = BenefitsAgent().run(_make_event())
        assert resp.confidence == 0.1

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("connection refused"))
    def test_fallback_output_text_is_non_empty(self, _):
        resp = BenefitsAgent().run(_make_event())
        assert len(resp.output_text.strip()) > 20

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("rate limit"))
    def test_fallback_requires_human_review_true(self, _):
        resp = BenefitsAgent().run(_make_event())
        assert resp.requires_human_review is True

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("timeout"))
    def test_fallback_output_contains_no_overclaims(self, _):
        """Fallback text must not make eligibility guarantees."""
        resp = BenefitsAgent().run(_make_event())
        out = resp.output_text.lower()
        assert "you qualify" not in out
        assert "guaranteed" not in out
        assert "you are approved" not in out

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("timeout"))
    def test_fallback_agent_name_unchanged(self, _):
        resp = BenefitsAgent().run(_make_event())
        assert resp.agent_name == "BenefitsAgent"


# ---------------------------------------------------------------------------
# Test Group 4 — Missing API key falls back gracefully
# ---------------------------------------------------------------------------

class TestMissingAPIKeyFallsBack:
    """A missing ANTHROPIC_API_KEY now raises LLMUnavailableError from client.py,
    and BenefitsAgent catches both LLMUnavailableError and RuntimeError, so the
    agent always returns a safe fallback response regardless of which exception
    the LLM layer raises."""

    @patch(
        "agents.benefits_agent.call_llm_race",
        side_effect=RuntimeError("ANTHROPIC_API_KEY is not set or empty."),
    )
    def test_runtime_error_triggers_fallback(self, _):
        """RuntimeError from call_llm must be caught and return used_fallback=True."""
        resp = BenefitsAgent().run(_make_event())
        assert resp.used_fallback is True

    @patch(
        "agents.benefits_agent.call_llm_race",
        side_effect=LLMUnavailableError("ANTHROPIC_API_KEY is not set or empty."),
    )
    def test_missing_key_as_llm_error_triggers_fallback(self, _):
        """client.py now raises LLMUnavailableError for a missing key;
        agent must catch it and return a safe rule-based response."""
        resp = BenefitsAgent().run(_make_event())
        assert resp.used_fallback is True
        assert resp.requires_human_review is True
        assert len(resp.output_text) > 20


# ---------------------------------------------------------------------------
# Test Group 5 — Prompt content checks
# ---------------------------------------------------------------------------

class TestPromptContent:
    """The user message passed to call_llm must include evidence items and
    event details.  The system prompt must encode the RESPONSIBLE_AI hard rules."""

    @patch("agents.benefits_agent.call_llm_race")
    def test_evidence_title_appears_in_user_message(self, mock_call_llm):
        mock_call_llm.return_value = "You may qualify based on the information provided."
        evidence = [_make_evidence(tier=1, title="Senior Pension Official Guide")]

        BenefitsAgent().run(_make_event(), evidence_items=evidence)

        user_message = mock_call_llm.call_args[0][1]
        assert "Senior Pension Official Guide" in user_message

    @patch("agents.benefits_agent.call_llm_race")
    def test_redacted_text_appears_in_user_message(self, mock_call_llm):
        mock_call_llm.return_value = "You may be eligible."
        event = _make_event(text="Elderly housing assistance program application form.")

        BenefitsAgent().run(event)

        user_message = mock_call_llm.call_args[0][1]
        assert "Elderly housing assistance program" in user_message

    @patch("agents.benefits_agent.call_llm_race")
    def test_system_prompt_contains_hard_rule_1(self, mock_call_llm):
        """System prompt must encode the 'may qualify' rule."""
        mock_call_llm.return_value = "You may be eligible."
        BenefitsAgent().run(_make_event())
        system_prompt = mock_call_llm.call_args[0][0]
        assert "you may qualify based on the information provided" in system_prompt.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_system_prompt_contains_verify_instruction(self, mock_call_llm):
        """System prompt must instruct the model to recommend official verification."""
        mock_call_llm.return_value = "You may be eligible."
        BenefitsAgent().run(_make_event())
        system_prompt = mock_call_llm.call_args[0][0]
        assert "verify" in system_prompt.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_system_prompt_bans_otp_requests(self, mock_call_llm):
        """System prompt must explicitly prohibit requesting OTPs/PINs."""
        mock_call_llm.return_value = "You may be eligible."
        BenefitsAgent().run(_make_event())
        system_prompt = mock_call_llm.call_args[0][0]
        assert "otp" in system_prompt.lower() or "pin" in system_prompt.lower()

    @patch("agents.benefits_agent.call_llm_race")
    def test_no_evidence_items_does_not_crash(self, mock_call_llm):
        """run() must succeed when evidence_items is None."""
        mock_call_llm.return_value = "You may qualify based on the information provided."
        resp = BenefitsAgent().run(_make_event(), evidence_items=None)
        assert resp.used_fallback is False

    @patch("agents.benefits_agent.call_llm_race")
    def test_evidence_capped_at_five_items(self, mock_call_llm):
        """Only the first 5 evidence items must be included in the prompt."""
        mock_call_llm.return_value = "You may be eligible."
        # 8 items — tiers capped at 5 (EvidenceItem.tier ge=1 le=5)
        evidence = [
            _make_evidence(tier=min(i, 5), title=f"Source {i}") for i in range(1, 9)
        ]
        BenefitsAgent().run(_make_event(), evidence_items=evidence)
        user_message = mock_call_llm.call_args[0][1]
        # Items 6, 7, 8 exceed the 5-item cap and must be absent
        assert "Source 6" not in user_message
        assert "Source 7" not in user_message
        assert "Source 8" not in user_message


# ---------------------------------------------------------------------------
# Test Group 6 — node_benefits pipeline integration
# ---------------------------------------------------------------------------

class TestNodeBenefitsIntegration:
    """node_benefits wraps BenefitsAgent.run() and must correctly thread the
    response through PipelineState, passing evidence_items as context."""

    @patch("agents.benefits_agent.call_llm_race")
    def test_node_appends_response_to_state(self, mock_call_llm):
        mock_call_llm.return_value = "You may be eligible for this program."
        state = make_initial_state(_make_event())
        new_state = node_benefits(state)

        assert len(new_state["agent_responses"]) == 1
        assert new_state["agent_responses"][0].agent_name == "BenefitsAgent"

    @patch("agents.benefits_agent.call_llm_race")
    def test_node_preserves_existing_agent_responses(self, mock_call_llm):
        """node_benefits must append, not overwrite, existing agent_responses."""
        mock_call_llm.return_value = "You may be eligible."
        from schemas.decision_schema import AgentResponse as AR
        existing = AR(
            agent_name="FormAgent", output_text="Form OK",
            confidence=0.5, requires_human_review=False,
        )
        state = make_initial_state(_make_event())
        state = {**state, "agent_responses": [existing]}
        new_state = node_benefits(state)

        assert len(new_state["agent_responses"]) == 2
        assert new_state["agent_responses"][0].agent_name == "FormAgent"
        assert new_state["agent_responses"][1].agent_name == "BenefitsAgent"

    @patch("agents.benefits_agent.call_llm_race", side_effect=LLMUnavailableError("down"))
    def test_node_fallback_used_fallback_true_in_state(self, _):
        """When LLM is unavailable, the state response must have used_fallback=True."""
        state = make_initial_state(_make_event())
        new_state = node_benefits(state)

        assert new_state["agent_responses"][0].used_fallback is True

    @patch("agents.benefits_agent.call_llm_race")
    def test_node_passes_evidence_items_from_state(self, mock_call_llm):
        """node_benefits must forward state['evidence_items'] to the agent."""
        mock_call_llm.return_value = "You may qualify based on the information provided."
        evidence = [_make_evidence(tier=1, title="Pension Act Official Summary")]
        state = make_initial_state(_make_event())
        state = {**state, "evidence_items": evidence}

        node_benefits(state)

        user_message = mock_call_llm.call_args[0][1]
        assert "Pension Act Official Summary" in user_message
