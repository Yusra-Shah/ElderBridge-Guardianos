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

import concurrent.futures
import logging

from agents.benefits_agent import BenefitsAgent
from agents.critic_agent import CriticAgent
from agents.form_agent import FormAgent
from agents.guardrail_agent import GuardrailAgent
from agents.research_agent import ResearchAgent
from agents.router_agent import RouterAgent
from graph.state import PipelineState
from orchestrator import compute_baseline
from schemas.decision_schema import AgentResponse, EvidenceItem, FinalDecision, RiskLevel

logger = logging.getLogger("elderbridge.graph.nodes")

_AGENT_TIMEOUT = 15  # seconds per specialist agent
_RESEARCH_TIMEOUT = 8  # shorter budget for research enrichment

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
    def _run():
        return _benefits.run(state["event"], evidence_items=state.get("evidence_items", []))

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_run)
    try:
        resp = future.result(timeout=_AGENT_TIMEOUT)
    except (concurrent.futures.TimeoutError, Exception) as exc:
        logger.warning("node_benefits | timed out or failed (%s), using fallback", exc)
        resp = AgentResponse(
            agent_name="BenefitsAgent",
            output_text=(
                "I could not complete the analysis in time. Please verify your "
                "eligibility directly with the official agency or a trusted caseworker."
            ),
            confidence=0.1,
            sources=[],
            requires_human_review=True,
            used_fallback=True,
        )
    finally:
        ex.shutdown(wait=False)

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
    def _run():
        return _form.run(state["event"])

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_run)
    try:
        resp = future.result(timeout=_AGENT_TIMEOUT)
    except (concurrent.futures.TimeoutError, Exception) as exc:
        logger.warning("node_form | timed out or failed (%s), using fallback", exc)
        resp = AgentResponse(
            agent_name="FormAgent",
            output_text=(
                "This form is asking for standard personal information needed to "
                "process your application. If you are unsure about any field, ask "
                "a trusted person to help you fill it in correctly."
            ),
            confidence=0.1,
            sources=[],
            requires_human_review=True,
            used_fallback=True,
        )
    finally:
        ex.shutdown(wait=False)

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
    Run the Research Verification Agent with its own sub-timeout.

    Non-blocking for the final answer: if research does not return in time,
    the pipeline proceeds with FormAgent and BenefitsAgent output and omits
    the extra citations.

    Appends to: agent_responses, evidence_items.
    Reads: event.
    """
    def _run():
        return _research.run(state["event"])

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_run)
    try:
        resp = future.result(timeout=_RESEARCH_TIMEOUT)
    except (concurrent.futures.TimeoutError, Exception) as exc:
        logger.warning("node_research | timed out or failed (%s), skipping", exc)
        ex.shutdown(wait=False)
        return state
    finally:
        ex.shutdown(wait=False)

    logger.debug(
        "node_research | confidence=%.2f evidence=%d requires_review=%s",
        resp.confidence,
        len(resp.evidence_items),
        resp.requires_human_review,
    )

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
    Also sets: draft_response — overrides the baseline text with the best
    specialist LLM output when one is available (non-fallback, non-empty).
    Reads: event, agent_responses.
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

    # Only BenefitsAgent and FormAgent produce user-facing LLM text.
    # ResearchAgent and others provide supporting evidence, not draft responses.
    _USER_FACING_AGENTS = {"BenefitsAgent", "FormAgent"}
    non_fallback = [
        r for r in responses
        if not r.used_fallback and r.output_text and r.agent_name in _USER_FACING_AGENTS
    ]
    if non_fallback:
        best = max(non_fallback, key=lambda r: r.confidence)
        logger.debug(
            "node_critic | promoting %s output to draft_response (confidence=%.2f)",
            best.agent_name,
            best.confidence,
        )
        return {**state, "last_critic_response": critic_resp, "draft_response": best.output_text}

    return {**state, "last_critic_response": critic_resp}


def node_guardrail(state: PipelineState) -> PipelineState:
    """
    Run the Safety Guardrail Agent — final veto before user delivery.

    Sets: final_decision.
    Reads: event, draft_response, risk_flag, next_steps, evidence_items.

    Three outcomes, determined by GuardrailAgent.run() return value:

      HARD BLOCK (output_text non-empty, requires_human_review=True):
        AI draft output itself contains a dangerous pattern.
        Uses the guardrail safe-replacement text as response_text.
        Sets STOP_AND_VERIFY and clears source_citations.

      SCAM FLAG (output_text empty, requires_human_review=True):
        Scam signal detected in incoming event text.
        Passes the baseline draft_response through unchanged.
        Sets STOP_AND_VERIFY and clears source_citations.

      PASS (requires_human_review=False):
        No violations. Uses baseline draft_response with the existing
        risk_flag and next_steps computed by node_baseline.
    """
    event = state["event"]
    draft = state.get("draft_response", "")

    guardrail_resp = _guardrail.run(event, draft)

    from agents.output_filter import filter_output
    draft = filter_output(draft)

    if guardrail_resp.output_text:
        # HARD BLOCK — AI output is directly dangerous; replace with safe text.
        logger.debug("node_guardrail | result=HARD_BLOCK")
        decision = FinalDecision(
            response_text=guardrail_resp.output_text,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    elif guardrail_resp.requires_human_review:
        # SCAM FLAG — dangerous input; use baseline draft, override risk.
        logger.debug("node_guardrail | result=SCAM_FLAG")
        decision = FinalDecision(
            response_text=draft,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    else:
        # PASS — no violations; use baseline draft with existing risk metadata.
        logger.debug("node_guardrail | result=PASS")
        decision = FinalDecision(
            response_text=draft,
            risk_flag=state.get("risk_flag", RiskLevel.SOFT_HELP),
            next_steps=state.get("next_steps", []),
            source_citations=state.get("evidence_items", []),
        )

    return {**state, "final_decision": decision}
