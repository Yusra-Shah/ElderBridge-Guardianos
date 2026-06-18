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
import re

from agents.benefits_agent import BenefitsAgent
from agents.critic_agent import CriticAgent, _rewrite as _critic_rewrite
from agents.form_agent import FormAgent
from agents.guardrail_agent import GuardrailAgent
from agents.research_agent import ResearchAgent
from agents.router_agent import RouterAgent
from graph.state import PipelineState
from orchestrator import compute_baseline
from schemas.decision_schema import AgentResponse, EvidenceItem, FinalDecision, RiskLevel

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
# Response assembly helpers
# ---------------------------------------------------------------------------

# Agent names whose output_text is user-facing explanation.
# ResearchAgent output is metadata only — it goes into source_citations.
_PRIMARY_AGENTS = ("BenefitsAgent", "FormAgent")


def _select_primary_text(agent_responses: list[AgentResponse]) -> str:
    """Return the critic-cleaned output of the primary user-facing agent.

    Prefers BenefitsAgent, then FormAgent. Excludes ResearchAgent because its
    boilerplate ("I found N sources...") belongs in source_citations, not in
    the response_text shown to the user.
    """
    for name in _PRIMARY_AGENTS:
        for resp in agent_responses:
            if resp.agent_name == name and resp.output_text:
                cleaned, _ = _critic_rewrite(resp.output_text)
                return cleaned
    return ""


def _parse_steps(text: str) -> tuple[str, list[str]]:
    """Split LLM output into (main_text, next_steps).

    Lines that start with 'Step:' (case-insensitive) are stripped from the
    main response and returned as a next_steps list.  Content before the first
    Step: line becomes the plain response_text.
    """
    lines = text.strip().splitlines()
    content: list[str] = []
    steps: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^step\s*:", stripped, re.IGNORECASE):
            body = re.sub(r"^step\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            if body:
                steps.append(body)
        elif not steps:
            content.append(line)
    return "\n".join(content).strip(), steps


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
           agent_responses (used to select the primary user-facing text).

    Three outcomes:
      HARD BLOCK (requires_human_review=True, output_text non-empty):
        AI output itself is dangerous. Uses safe replacement and STOP_AND_VERIFY.
      SCAM FLAG (requires_human_review=True, output_text empty):
        Scam detected in input. Passes BenefitsAgent explanation through unchanged
        with STOP_AND_VERIFY. Source citations cleared.
      CAUTION / PASSED (requires_human_review=False):
        Uses primary agent explanation (BenefitsAgent or FormAgent).
        ResearchAgent boilerplate is excluded from response_text — it goes to
        source_citations only.  Step: lines from LLM become next_steps.
    """
    event = state["event"]
    draft = state.get("draft_response", "")
    agent_responses = state.get("agent_responses", [])

    guardrail_resp = _guardrail.run(event, draft)

    if guardrail_resp.requires_human_review and guardrail_resp.output_text:
        # HARD BLOCK — AI output is directly dangerous; replace with safe text.
        logger.debug("node_guardrail | result=HARD_BLOCK")
        decision = FinalDecision(
            response_text=guardrail_resp.output_text,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    elif guardrail_resp.requires_human_review:
        # SCAM FLAG — dangerous input; pass AI explanation through, override risk.
        logger.debug("node_guardrail | result=SCAM_FLAG")
        primary = _select_primary_text(agent_responses)
        main_text, llm_steps = _parse_steps(primary) if primary else ("", [])
        decision = FinalDecision(
            response_text=main_text or draft,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=llm_steps or _guardrail.safe_next_steps,
            source_citations=[],
        )

    else:
        # CAUTION or PASSED — use primary agent explanation.
        caution_note = guardrail_resp.output_text  # "" for clean pass
        logger.debug("node_guardrail | result=%s", "CAUTION" if caution_note else "PASS")

        primary = _select_primary_text(agent_responses)
        main_text, llm_steps = _parse_steps(primary) if primary else ("", [])

        # main_text is either the full primary response (no Step: found)
        # or the content before Step: lines (when LLM produced steps).
        response_part = main_text or draft

        if caution_note:
            final_text = f"{caution_note}\n\n{response_part}" if response_part else caution_note
        else:
            final_text = response_part

        decision = FinalDecision(
            response_text=final_text,
            risk_flag=state.get("risk_flag", RiskLevel.SOFT_HELP),
            next_steps=llm_steps or state.get("next_steps", []),
            source_citations=state.get("evidence_items", []),
        )

    return {**state, "final_decision": decision}
