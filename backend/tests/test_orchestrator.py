"""
Tests for the ElderBridge agent pipeline.

Four test cases covering:
  1. SMS with scam-like OTP text → guardrail blocks → STOP_AND_VERIFY
  2. FORM_SCREEN event → RouterAgent routes to FormAgent
  3. Specialist output containing "you qualify" → CriticAgent rewrites it
  4. Benign FORM_SCREEN with no risk signals → NONE risk level

All tests run fully offline — no external API calls, no LLM calls.

Run from the backend/ directory:
    pytest tests/ -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.critic_agent import CriticAgent
from agents.router_agent import RouterAgent
from orchestrator import run_pipeline
from schemas.decision_schema import AgentResponse, RiskLevel
from schemas.event_schema import EventType, IncomingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_type: EventType,
    redacted_text: str,
    source_app: str = "test.app",
    user_id: str = "usr_test_001",
) -> IncomingEvent:
    """Construct a minimal IncomingEvent for testing."""
    return IncomingEvent(
        event_type=event_type,
        source_app=source_app,
        redacted_text=redacted_text,
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )


def _make_agent_response(output_text: str, agent_name: str = "MockAgent") -> AgentResponse:
    """Construct a minimal AgentResponse for direct agent unit tests."""
    return AgentResponse(
        agent_name=agent_name,
        output_text=output_text,
        confidence=0.8,
        sources=[],
        requires_human_review=False,
    )


# ---------------------------------------------------------------------------
# Test 1 — Guardrail blocks a scam SMS with OTP instruction
# ---------------------------------------------------------------------------

class TestGuardrailBlocksScamSms:
    """
    An SMS containing 'Enter your OTP' is a high-risk input risk signal.
    The guardrail should detect it and the pipeline should return STOP_AND_VERIFY.
    The response text must come from the safe replacement (not the baseline).
    """

    def test_stop_and_verify_risk_flag(self):
        event = _make_event(
            EventType.SMS,
            redacted_text=(
                "Govt health grant approved. "
                "Enter your OTP to verify and claim your benefit at senior-grant.info."
            ),
        )
        decision = run_pipeline(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY, (
            f"Expected STOP_AND_VERIFY, got {decision.risk_flag}"
        )

    def test_response_text_is_safe_replacement(self):
        """When the guardrail blocks, the safe replacement text must be used."""
        event = _make_event(
            EventType.SMS,
            redacted_text="Enter your OTP immediately to avoid account suspension.",
        )
        decision = run_pipeline(event)
        # Safe replacement language from guardrail — no "placeholder" language
        assert "placeholder" not in decision.response_text.lower()
        assert "do not share" in decision.response_text.lower()

    def test_next_steps_are_non_empty_on_block(self):
        event = _make_event(
            EventType.SMS,
            redacted_text="Send your OTP now to receive the healthcare benefit.",
        )
        decision = run_pipeline(event)
        assert len(decision.next_steps) > 0, "Blocked decision must include next steps"


# ---------------------------------------------------------------------------
# Test 2 — FORM_SCREEN routes through FormAgent
# ---------------------------------------------------------------------------

class TestFormScreenRouting:
    """
    A FORM_SCREEN event must cause RouterAgent to include 'FormAgent' in its
    routing output.  This validates that the routing map correctly handles
    form/screen events without relying on the full pipeline.
    """

    def test_form_agent_in_route(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="Annual household income: ___  Number of dependants: ___",
        )
        router = RouterAgent()
        agents = router.route(event)
        assert "FormAgent" in agents, (
            f"Expected FormAgent in routing for FORM_SCREEN, got: {agents}"
        )

    def test_benefits_agent_in_route_for_form(self):
        """BenefitsAgent should also be included for form screens (eligibility help)."""
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="Please provide your pension details and income range.",
        )
        router = RouterAgent()
        agents = router.route(event)
        assert "BenefitsAgent" in agents, (
            f"Expected BenefitsAgent in route for form with income/pension text, got: {agents}"
        )

    def test_critic_and_guardrail_not_in_route(self):
        """Critic and Guardrail must not be listed by the router — orchestrator adds them."""
        event = _make_event(EventType.FORM_SCREEN, redacted_text="Please enter your name.")
        router = RouterAgent()
        agents = router.route(event)
        assert "CriticAgent" not in agents
        assert "GuardrailAgent" not in agents

    def test_pipeline_returns_decision_for_form_screen(self):
        """Full pipeline must complete and return a FinalDecision for a FORM_SCREEN event."""
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="What is your date of birth? Field: DD / MM / YYYY",
        )
        decision = run_pipeline(event)
        assert decision.risk_flag is not None
        assert len(decision.response_text) > 0


# ---------------------------------------------------------------------------
# Test 3 — CriticAgent rewrites "you qualify" language
# ---------------------------------------------------------------------------

class TestCriticRewritesOverclaim:
    """
    The CriticAgent must catch and rewrite overclaiming phrases such as
    'you qualify', 'you will receive', and 'guaranteed' from specialist outputs.
    This enforces the RESPONSIBLE_AI.md §3 hard rule.
    """

    def test_you_qualify_is_rewritten(self):
        event = _make_event(EventType.NOTIFICATION, redacted_text="Benefit notice received.")
        draft = [_make_agent_response("Based on your details, you qualify for this benefit.")]
        critic = CriticAgent()
        result = critic.run(event, draft)

        assert "you qualify" not in result.output_text.lower(), (
            "Critic must remove 'you qualify' from output"
        )
        assert "you may qualify" in result.output_text.lower(), (
            "Critic must replace with 'you may qualify based on the information provided'"
        )

    def test_guaranteed_is_rewritten(self):
        event = _make_event(EventType.DOCUMENT, redacted_text="Government letter.")
        draft = [_make_agent_response("This benefit is guaranteed for seniors over 65.")]
        critic = CriticAgent()
        result = critic.run(event, draft)

        assert "guaranteed" not in result.output_text.lower()
        assert "possibly available" in result.output_text.lower()

    def test_you_will_receive_is_rewritten(self):
        event = _make_event(EventType.SMS, redacted_text="Benefit SMS.")
        draft = [_make_agent_response("You will receive PKR 5000 monthly.")]
        critic = CriticAgent()
        result = critic.run(event, draft)

        assert "you will receive" not in result.output_text.lower()
        assert "you may receive" in result.output_text.lower()

    def test_requires_human_review_true_when_rewritten(self):
        """Critic must set requires_human_review=True when it rewrote something."""
        event = _make_event(EventType.NOTIFICATION, redacted_text="Eligibility notice.")
        draft = [_make_agent_response("Congratulations, you qualify for senior healthcare.")]
        critic = CriticAgent()
        result = critic.run(event, draft)

        assert result.requires_human_review is True

    def test_clean_output_passes_through(self):
        """Output with no overclaiming must pass with requires_human_review=False."""
        event = _make_event(EventType.NOTIFICATION, redacted_text="Document notice.")
        draft = [_make_agent_response(
            "You may qualify based on the information provided. "
            "Please verify with the official agency."
        )]
        critic = CriticAgent()
        result = critic.run(event, draft)

        assert result.requires_human_review is False


# ---------------------------------------------------------------------------
# Test 4 — Benign event returns NONE risk
# ---------------------------------------------------------------------------

class TestBenignEventReturnsNoneRisk:
    """
    A FORM_SCREEN event with purely neutral text (no risk keywords, no OTP,
    no benefit claims) must return RiskLevel.NONE — the lowest possible level,
    indicating the system is ready to help but has no concerns.
    """

    def test_none_risk_for_plain_form_screen(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="Please enter your full name in the field below.",
        )
        decision = run_pipeline(event)
        assert decision.risk_flag == RiskLevel.NONE, (
            f"Expected NONE risk for a benign name field, got {decision.risk_flag}"
        )

    def test_none_risk_for_date_of_birth_field(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="Date of birth: Day, Month, Year",
        )
        decision = run_pipeline(event)
        assert decision.risk_flag == RiskLevel.NONE

    def test_benign_document_also_low_risk(self):
        """A DOCUMENT event with no risk signals must also return NONE."""
        event = _make_event(
            EventType.DOCUMENT,
            redacted_text="Dear resident, please find enclosed your updated address record.",
        )
        decision = run_pipeline(event)
        assert decision.risk_flag == RiskLevel.NONE

    def test_benign_response_text_is_helpful(self):
        """Benign event response text must be helpful and calming, not alarmist."""
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="Select your preferred language from the list.",
        )
        decision = run_pipeline(event)
        # Response text must not contain alarming language
        alarming = ["stop", "danger", "risk", "scam", "fraud", "do not"]
        response_lower = decision.response_text.lower()
        for word in alarming:
            assert word not in response_lower, (
                f"Benign event response should not contain '{word}': {decision.response_text}"
            )
