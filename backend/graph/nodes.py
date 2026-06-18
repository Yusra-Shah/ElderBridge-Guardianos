"""
ElderBridge GuardianOS — Graph node functions.

Each function wraps an existing agent class and has the signature:
    node_fn(state: PipelineState) -> PipelineState

Nodes read what they need from state and return a new dict that extends
the incoming state (LangGraph's partial-update / reducer pattern).

No business logic lives here — all reasoning stays in the agent classes.
This file is purely the wiring layer between the graph and the agents.

Node execution order (set in build_graph.py):
    baseline → router → [benefits | form | research] → critic → guardrail
"""
from __future__ import annotations

import logging

from agents.benefits_agent import BenefitsAgent
from agents.critic_agent import CriticAgent
from agents.form_agent import FormAgent
from agents.guardrail_agent import GuardrailAgent
from agents.research_agent import ResearchAgent
from agents.router_agent import RouterAgent
from graph.state import PipelineState
from orchestrator import compute_baseline
from schemas.decision_schema import EvidenceItem, FinalDecision, RiskLevel

logger = logging.getLogger("elderbridge.graph.nodes")

# ---------------------------------------------------------------------------
# Singleton agent instances — stateless, safe to share across requests
# ---------------------------------------------------------------------------

_router = RouterAgent()
_benefits = BenefitsAgent()
_form = FormAgent()
_research = ResearchAgent()
_critic = CriticAgent()
_guardrail = GuardrailAgent()


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_baseline(state: PipelineState) -> PipelineState:
    """
    Compute the rule-based risk baseline.

    Sets: draft_response, risk_flag, next_steps.
    Reads: event.
    """
    event = state["event"]
    risk_flag, response_text, next_steps = compute_baseline(event)
    logger.debug(
        "node_baseline | risk_flag=%s text_len=%d",
        risk_flag.value,
        len(response_text),
    )
    return {
        **state,
        "draft_response": response_text,
        "risk_flag": risk_flag,
        "next_steps": next_steps,
    }


def node_router(state: PipelineState) -> PipelineState:
    """
    Determine which specialist agents to invoke.

    Sets: routed_agents (list of agent name strings, e.g. ["FormAgent", "BenefitsAgent"]).
    Reads: event.

    CriticAgent and GuardrailAgent are NOT included — they are always wired
    as fixed downstream nodes in the graph regardless of event type.
    """
    event = state["event"]
    routed = _router.route(event)
    logger.debug("node_router | routed_agents=%s", routed)
    return {**state, "routed_agents": routed}


def node_benefits(state: PipelineState) -> PipelineState:
    """
    Run the Benefits Navigator Agent.

    Appends to: agent_responses.
    Reads: event, evidence_items (passed as supporting context to the LLM).
    """
    resp = _benefits.run(state["event"], evidence_items=state.get("evidence_items", []))
    if resp.used_fallback:
        logger.warning("node_benefits | LLM unavailable — rule-based fallback response used")
    else:
        logger.debug("node_benefits | confidence=%.2f", resp.confidence)
    return {
        **state,
        "agent_responses": [*state.get("agent_responses", []), resp],
    }


def node_form(state: PipelineState) -> PipelineState:
    """
    Run the Screen / Form Agent.

    Appends to: agent_responses.
    Reads: event.

    FormAgent now calls the LLM for FORM_SCREEN events to explain each
    visible field in plain language.  Falls back to a rule-based stub on
    LLMUnavailableError (used_fallback=True on the response).
    """
    resp = _form.run(state["event"])
    if resp.used_fallback:
        logger.warning("node_form | LLM unavailable — rule-based fallback used")
    else:
        logger.debug("node_form | confidence=%.2f", resp.confidence)
    return {
        **state,
        "agent_responses": [*state.get("agent_responses", []), resp],
    }


def node_research(state: PipelineState) -> PipelineState:
    """
    Run the Research Verification Agent.

    Appends to: agent_responses, evidence_items.
    Reads: event.

    ResearchAgent is the only node that populates evidence_items — it
    carries EvidenceItem objects from the mock source database (or, in a
    future milestone, from a live RAG / web-search backend).
    """
    resp = _research.run(state["event"])
    logger.debug(
        "node_research | confidence=%.2f evidence=%d requires_review=%s",
        resp.confidence,
        len(resp.evidence_items),
        resp.requires_human_review,
    )

    # Deduplicate evidence by source_id before extending state
    existing_ids = {e.source_id for e in state.get("evidence_items", [])}
    new_evidence = [e for e in resp.evidence_items if e.source_id not in existing_ids]

    return {
        **state,
        "agent_responses": [*state.get("agent_responses", []), resp],
        "evidence_items": [*state.get("evidence_items", []), *new_evidence],
    }


def node_critic(state: PipelineState) -> PipelineState:
    """
    Run the Critic / Judge Agent over all specialist responses accumulated so far.

    Sets: last_critic_response (for introspection / testing / logging).
    Reads: event, agent_responses.

    The critic's cleaned output is stored in last_critic_response.output_text.
    In this milestone the baseline draft_response is still used as the final
    user-facing text (specialists return stubs); when specialists produce real
    LLM output in a later milestone, this node will update draft_response from
    the critic's cleaned combined text.
    """
    event = state["event"]
    responses = state.get("agent_responses", [])
    critic_resp = _critic.run(event, responses)

    logger.debug(
        "node_critic | reviewed=%d rewrote=%s confidence=%.2f",
        len(responses),
        critic_resp.requires_human_review,
        critic_resp.confidence,
    )
    return {**state, "last_critic_response": critic_resp}


def node_guardrail(state: PipelineState) -> PipelineState:
    """
    Run the Safety Guardrail Agent — final veto before user delivery.

    Sets: final_decision.
    Reads: event, draft_response, risk_flag, next_steps, evidence_items,
           last_critic_response (combined agent output).

    Three outcomes:
      BLOCKED (requires_human_review=True):
        Uses safe replacement text and STOP_AND_VERIFY. Source citations dropped.
      CAUTION (requires_human_review=False, guardrail_resp.output_text non-empty):
        Prepends caution note to combined agent/critic output.
        Risk flag and next_steps come from baseline.
      PASSED (requires_human_review=False, guardrail_resp.output_text empty):
        Uses combined agent/critic output as response_text.
        Falls back to baseline draft_response if no agent output is available.
    """
    event = state["event"]
    draft = state.get("draft_response", "")

    guardrail_resp = _guardrail.run(event, draft)
    logger.debug(
        "node_guardrail | result=%s",
        "BLOCKED" if guardrail_resp.requires_human_review else (
            "CAUTION" if guardrail_resp.output_text else "PASS"
        ),
    )

    if guardrail_resp.requires_human_review and guardrail_resp.output_text:
        # HARD BLOCK — AI output itself is dangerous; use safe replacement text.
        decision = FinalDecision(
            response_text=guardrail_resp.output_text,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )
    elif guardrail_resp.requires_human_review:
        # SCAM FLAG — scam detected in input; pass through AI-generated explanation
        # but override risk_flag to STOP_AND_VERIFY and clear source citations.
        critic_resp = state.get("last_critic_response")
        agent_text = (
            critic_resp.output_text
            if (
                critic_resp
                and critic_resp.output_text
                and "No specialist outputs to review." not in critic_resp.output_text
            )
            else ""
        )
        decision = FinalDecision(
            response_text=agent_text or state.get("draft_response", ""),
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )
    else:
        # Prefer the critic-cleaned combined agent output over the rule-based baseline.
        # The critic joins all specialist outputs with " | " after overclaim rewriting.
        # Falls back to baseline if agents produced no meaningful text.
        critic_resp = state.get("last_critic_response")
        agent_text = (
            critic_resp.output_text
            if (
                critic_resp
                and critic_resp.output_text
                and "No specialist outputs to review." not in critic_resp.output_text
            )
            else ""
        )

        # Guardrail caution note: non-empty only for CAUTION-level events
        caution_note = guardrail_resp.output_text  # "" for clean pass

        if caution_note and agent_text:
            final_text = f"{caution_note}\n\n{agent_text}"
        elif caution_note:
            final_text = f"{caution_note}\n\n{draft}" if draft else caution_note
        elif agent_text:
            final_text = agent_text
        else:
            final_text = draft  # baseline fallback

        decision = FinalDecision(
            response_text=final_text,
            risk_flag=state.get("risk_flag", RiskLevel.SOFT_HELP),
            next_steps=state.get("next_steps", []),
            source_citations=state.get("evidence_items", []),
        )

    return {**state, "final_decision": decision}
