"""
Tests for the LangGraph-style pipeline graph.

Four test groups mirroring test_orchestrator.py but running through run_graph():
  1. Scam SMS blocked — guardrail BLOCKS, returns STOP_AND_VERIFY
  2. FORM_SCREEN routing — router fan-out includes FormAgent
  3. Critic rewrite — node_critic rewrites "you qualify" in specialist outputs
  4. Benign event — run_graph() returns NONE risk for harmless form text

Additional tests:
  5. Graph / orchestrator equivalence — run_graph() and run_pipeline() produce
     equivalent risk_flag for the same inputs
  6. Graph state integrity — intermediate state fields are correctly populated

All tests are offline. No LLM, no API, no network calls.

Run from backend/:
    pytest tests/test_graph.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from agents.benefits_agent import BenefitsAgent
from graph.build_graph import (
    CompiledGraph,
    PipelineGraph,
    _route_to_specialists,
    build_pipeline_graph,
    run_graph,
)
from graph.nodes import node_critic, node_baseline, node_router
from graph.state import PipelineState, make_initial_state
from orchestrator import run_pipeline
from schemas.decision_schema import AgentResponse, EvidenceItem, RiskLevel
from schemas.event_schema import EventType, IncomingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_type: EventType,
    redacted_text: str,
    source_app: str = "test.app",
    user_id: str = "usr_graph_test",
) -> IncomingEvent:
    return IncomingEvent(
        event_type=event_type,
        source_app=source_app,
        redacted_text=redacted_text,
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )


def _make_agent_resp(text: str, name: str = "MockAgent") -> AgentResponse:
    return AgentResponse(
        agent_name=name,
        output_text=text,
        confidence=0.8,
        sources=[],
        evidence_items=[],
        requires_human_review=False,
    )


# ---------------------------------------------------------------------------
# Test Group 1 — Guardrail blocks scam SMS through run_graph()
# ---------------------------------------------------------------------------

class TestGuardrailBlocksThroughGraph:
    """
    The guardrail node must intercept dangerous events and override the
    FinalDecision with a safe replacement, regardless of which path
    through the graph the event took.
    """

    def test_otp_sms_returns_stop_and_verify(self):
        event = _make_event(
            EventType.SMS,
            "Govt healthcare grant approved. Enter your OTP to claim benefits now.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY, (
            f"Expected STOP_AND_VERIFY for OTP SMS, got {decision.risk_flag}"
        )

    def test_blocked_response_text_is_non_empty_and_safe(self):
        event = _make_event(
            EventType.SMS,
            "Enter your OTP immediately. Your account will be closed.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY
        assert len(decision.response_text) > 0, (
            "Scam-flagged response must not be empty"
        )
        # The AI explanation must not instruct the user to share sensitive data
        text = decision.response_text.lower()
        assert "enter your otp" not in text
        assert "share your otp" not in text

    def test_blocked_decision_has_next_steps(self):
        event = _make_event(
            EventType.NOTIFICATION,
            "Send your OTP now to verify your pension eligibility.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY
        assert len(decision.next_steps) > 0

    def test_blocked_source_citations_empty(self):
        """Guardrail block must not attach any evidence citations."""
        event = _make_event(
            EventType.SMS,
            "Enter your OTP to claim your senior healthcare benefit grant.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.STOP_AND_VERIFY
        assert decision.source_citations == []


# ---------------------------------------------------------------------------
# Test Group 2 — FORM_SCREEN routing through the graph
# ---------------------------------------------------------------------------

class TestFormScreenRoutingThroughGraph:
    """
    The graph's router node must dispatch FORM_SCREEN events through the
    form node (and benefits node), not just return a generic result.
    """

    def test_form_screen_completes_successfully(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "Please enter your full name and date of birth.",
        )
        decision = run_graph(event)
        assert decision is not None
        assert decision.risk_flag is not None
        assert len(decision.response_text) > 0

    def test_node_router_includes_form_agent_for_form_screen(self):
        """node_router must populate routed_agents with FormAgent for FORM_SCREEN."""
        event = _make_event(
            EventType.FORM_SCREEN,
            "Annual household income: ___  Number of dependants: ___",
        )
        state = make_initial_state(event)
        state = node_router(state)
        assert "FormAgent" in state["routed_agents"], (
            f"Expected FormAgent in routed_agents, got: {state['routed_agents']}"
        )

    def test_route_to_specialists_maps_correctly(self):
        """_route_to_specialists must convert agent names to graph node names."""
        event = _make_event(EventType.FORM_SCREEN, "Income field")
        state = make_initial_state(event)
        state = {**state, "routed_agents": ["FormAgent", "BenefitsAgent"]}
        node_names = _route_to_specialists(state)
        assert "form" in node_names
        assert "benefits" in node_names
        # Critic and guardrail must NOT be in the fan-out
        assert "critic" not in node_names
        assert "guardrail" not in node_names

    def test_unknown_agent_names_ignored_in_fan_out(self):
        """_route_to_specialists must silently skip unknown agent names."""
        event = _make_event(EventType.SMS, "test")
        state = make_initial_state(event)
        state = {**state, "routed_agents": ["UnknownAgent", "FormAgent"]}
        node_names = _route_to_specialists(state)
        assert "form" in node_names
        assert len(node_names) == 1  # UnknownAgent dropped


# ---------------------------------------------------------------------------
# Test Group 3 — Critic rewrite flows through the graph
# ---------------------------------------------------------------------------

class TestCriticRewriteThroughGraph:
    """
    node_critic must detect and rewrite overclaiming language in specialist
    outputs.  Since run_graph() only exposes FinalDecision, we test the node
    directly via PipelineState to verify the rewrite and last_critic_response.
    """

    def test_node_critic_rewrites_you_qualify(self):
        """node_critic rewrites 'you qualify' in agent_responses."""
        event = _make_event(EventType.NOTIFICATION, "benefit notice")
        state = make_initial_state(event)
        state = {
            **state,
            "agent_responses": [
                _make_agent_resp(
                    "Based on your details, you qualify for this benefit.",
                    "BenefitsAgent",
                )
            ],
        }
        new_state = node_critic(state)
        critic_resp = new_state.get("last_critic_response")

        assert critic_resp is not None, "node_critic must set last_critic_response"
        assert "you qualify" not in critic_resp.output_text.lower(), (
            f"Critic must rewrite 'you qualify': {critic_resp.output_text}"
        )
        assert "you may qualify" in critic_resp.output_text.lower()

    def test_node_critic_sets_requires_human_review_on_rewrite(self):
        """Critic must flag requires_human_review when it rewrote something."""
        event = _make_event(EventType.DOCUMENT, "document")
        state = make_initial_state(event)
        state = {
            **state,
            "agent_responses": [
                _make_agent_resp("Congratulations, you qualify for senior healthcare.")
            ],
        }
        new_state = node_critic(state)
        assert new_state["last_critic_response"].requires_human_review is True

    def test_node_critic_passes_clean_output(self):
        """Critic must not flag clean (already hedged) specialist output."""
        event = _make_event(EventType.NOTIFICATION, "eligibility notice")
        state = make_initial_state(event)
        state = {
            **state,
            "agent_responses": [
                _make_agent_resp(
                    "You may qualify based on the information provided. "
                    "Please verify with the official agency."
                )
            ],
        }
        new_state = node_critic(state)
        assert new_state["last_critic_response"].requires_human_review is False

    def test_node_critic_rewrites_guaranteed(self):
        """Critic must replace 'guaranteed' with 'possibly available'."""
        event = _make_event(EventType.SMS, "benefit sms")
        state = make_initial_state(event)
        state = {
            **state,
            "agent_responses": [_make_agent_resp("This benefit is guaranteed for all seniors.")],
        }
        new_state = node_critic(state)
        out = new_state["last_critic_response"].output_text.lower()
        assert "guaranteed" not in out
        assert "possibly available" in out

    def test_run_graph_does_not_crash_with_overclaiming_specialist(self):
        """
        Even if a specialist (mocked) returns overclaiming text, run_graph()
        must complete and return a valid FinalDecision without raising.
        """
        overclaim_resp = _make_agent_resp("you qualify for all benefits")
        event = _make_event(EventType.FORM_SCREEN, "income and eligibility form")

        with patch.object(BenefitsAgent, "run", return_value=overclaim_resp):
            decision = run_graph(event)

        assert decision is not None
        assert decision.risk_flag is not None
        # Final response_text comes from baseline (not specialist stub),
        # so no overclaim phrase should appear in the user-facing text.
        assert "you qualify" not in decision.response_text.lower()


# ---------------------------------------------------------------------------
# Test Group 4 — Benign event returns NONE risk through run_graph()
# ---------------------------------------------------------------------------

class TestBenignEventThroughGraph:
    """
    FORM_SCREEN / DOCUMENT events with no risk signals must return NONE
    risk level — the system is ready to help but has no concerns.
    """

    def test_plain_name_field_returns_none(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "Please enter your full name in the field below.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.NONE, (
            f"Expected NONE for benign name field, got {decision.risk_flag}"
        )

    def test_date_of_birth_field_returns_none(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "Date of birth: Day / Month / Year",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.NONE

    def test_benign_document_returns_none(self):
        event = _make_event(
            EventType.DOCUMENT,
            "Dear resident, please find enclosed your updated address record.",
        )
        decision = run_graph(event)
        assert decision.risk_flag == RiskLevel.NONE

    def test_benign_response_contains_no_alarm_language(self):
        event = _make_event(
            EventType.FORM_SCREEN,
            "Select your preferred language from the dropdown menu.",
        )
        decision = run_graph(event)
        alarming = ["stop", "danger", "risk", "scam", "fraud", "do not"]
        text = decision.response_text.lower()
        for word in alarming:
            assert word not in text, (
                f"Benign event response must not contain '{word}': {decision.response_text}"
            )


# ---------------------------------------------------------------------------
# Test Group 5 — run_graph() / run_pipeline() equivalence
# ---------------------------------------------------------------------------

class TestGraphPipelineEquivalence:
    """
    run_graph() must produce the same risk_flag as run_pipeline() for the
    same inputs.  This verifies that the graph is a correct re-implementation
    of the manual pipeline in orchestrator.py.
    """

    _SCENARIOS = [
        (EventType.SMS, "Enter your OTP to claim your benefit now."),
        (EventType.FORM_SCREEN, "Annual household income and number of dependants."),
        (EventType.DOCUMENT, "Dear applicant, please submit your pension documents."),
        (EventType.NOTIFICATION, "Your benefit application has been received."),
        (EventType.FORM_SCREEN, "Please enter your full name."),
    ]

    @pytest.mark.parametrize("event_type,text", _SCENARIOS)
    def test_risk_flag_matches_pipeline(self, event_type: EventType, text: str):
        event = _make_event(event_type, text)
        graph_decision = run_graph(event)
        pipe_decision = run_pipeline(event)
        assert graph_decision.risk_flag == pipe_decision.risk_flag, (
            f"risk_flag mismatch for '{text}': "
            f"run_graph={graph_decision.risk_flag} run_pipeline={pipe_decision.risk_flag}"
        )

    def test_both_return_final_decision_type(self):
        from schemas.decision_schema import FinalDecision
        event = _make_event(EventType.NOTIFICATION, "Benefit notice from official agency.")
        assert isinstance(run_graph(event), FinalDecision)
        assert isinstance(run_pipeline(event), FinalDecision)


# ---------------------------------------------------------------------------
# Test Group 6 — PipelineGraph / CompiledGraph structural tests
# ---------------------------------------------------------------------------

class TestGraphStructure:
    """
    Tests for the PipelineGraph builder itself, verifying that the
    LangGraph-style API works correctly independent of agent logic.
    """

    def test_build_pipeline_graph_returns_compiled_graph(self):
        graph = build_pipeline_graph()
        assert isinstance(graph, CompiledGraph)

    def test_pipeline_graph_compile_requires_entry_point(self):
        """compile() must raise if no entry point is set."""
        g = PipelineGraph(state_schema=PipelineState)
        g.add_node("a", lambda s: s)
        with pytest.raises(ValueError, match="entry point"):
            g.compile()

    def test_make_initial_state_has_all_keys(self):
        event = _make_event(EventType.SMS, "test")
        state = make_initial_state(event)
        required_keys = {
            "event", "routed_agents", "agent_responses", "evidence_items",
            "draft_response", "risk_flag", "next_steps",
            "last_critic_response", "final_decision",
        }
        missing = required_keys - set(state.keys())
        assert not missing, f"make_initial_state missing keys: {missing}"

    def test_node_baseline_writes_draft_response(self):
        event = _make_event(EventType.FORM_SCREEN, "Enter your name")
        state = make_initial_state(event)
        new_state = node_baseline(state)
        assert isinstance(new_state["draft_response"], str)
        assert len(new_state["draft_response"]) > 0
        assert isinstance(new_state["risk_flag"], RiskLevel)

    def test_source_citations_are_evidence_items(self):
        """source_citations in FinalDecision must be EvidenceItem objects."""
        event = _make_event(
            EventType.FORM_SCREEN,
            "annual household income pension eligibility benefit",
        )
        decision = run_graph(event)
        for citation in decision.source_citations:
            assert isinstance(citation, EvidenceItem), (
                f"source_citations must contain EvidenceItem, got {type(citation)}"
            )
