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

import re

from agents.benefits_agent import BenefitsAgent
from agents.critic_agent import CriticAgent
from agents.form_agent import FormAgent
from agents.guardrail_agent import GuardrailAgent, _COMPILED_SAFE
from agents.research_agent import ResearchAgent
from agents.router_agent import RouterAgent, classify_context
from schemas.event_schema import EventType
from graph.state import PipelineState
from orchestrator import compute_baseline
from schemas.decision_schema import AgentResponse, EvidenceItem, FinalDecision, RiskLevel

_AMOUNT_RE = re.compile(r'(?:rs\.?|pkr\.?)\s*[\d,]+', re.IGNORECASE)
_URL_RE = re.compile(r'https?://\S+|[a-zA-Z0-9-]+\.[a-z]{2,}(?:\.[a-z]{2,})?', re.IGNORECASE)
_URGENCY_WORDS = {"urgent", "immediately", "expire", "suspended", "blocked", "hurry"}
_PERSONAL_FIELDS = {"cnic", "password", "otp", "pin", "date of birth", "mother"}

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

def _extract_signals(text: str) -> dict:
    """Extract structured signals from screen text for downstream agents."""
    text_lower = text.lower()
    words = set(text_lower.split())
    return {
        "amounts": _AMOUNT_RE.findall(text),
        "urls": _URL_RE.findall(text),
        "urgency": sorted(words & _URGENCY_WORDS),
        "personal_fields": sorted({f for f in _PERSONAL_FIELDS if f in text_lower}),
    }


def node_baseline(state: PipelineState) -> PipelineState:
    """
    Compute the rule-based risk baseline and extract structured signals.

    Sets: draft_response, risk_flag, next_steps, extracted_signals.
    Reads: event.
    """
    event = state["event"]
    risk_flag, response_text, next_steps = compute_baseline(event)
    signals = _extract_signals(event.redacted_text)
    logger.debug(
        "node_baseline | risk_flag=%s text_len=%d signals=%s",
        risk_flag.value,
        len(response_text),
        {k: v for k, v in signals.items() if v},
    )
    return {
        **state,
        "draft_response": response_text,
        "risk_flag": risk_flag,
        "next_steps": next_steps,
        "extracted_signals": signals,
    }


def node_router(state: PipelineState) -> PipelineState:
    """
    Determine which specialist agents to invoke and classify screen context.

    Sets: routed_agents, context_type.
    Reads: event.
    """
    event = state["event"]
    ctx = classify_context(event)
    routed = _router.route(event)
    logger.debug("node_router | context=%s routed_agents=%s", ctx, routed)
    return {**state, "routed_agents": routed, "context_type": ctx}


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


_OTP_HALLUCINATION_RE = re.compile(
    r'[^.]*\b(otp|one.time\s+password|one.time\s+code|verification\s+code)\b[^.]*\.',
    re.IGNORECASE,
)

_PHOTO_LANGUAGE_RE = re.compile(
    r'[^.]*\b(share|upload|send|take|attach)\s+(a\s+)?(clear\s+)?(photo|picture|screenshot|image)\b[^.]*\.?',
    re.IGNORECASE,
)


def _enforce_quality(text: str, context_type: str, event_text: str = "") -> str:
    """Enforce response quality rules on the final text."""
    if not text:
        return text
    text = re.sub(r'^This\s+(screen|looks\s+like)\s+', '', text, flags=re.IGNORECASE).strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    event_lower = event_text.lower()
    if "otp" not in event_lower and "one-time" not in event_lower and "one time" not in event_lower:
        text = _OTP_HALLUCINATION_RE.sub('', text).strip()
        text = re.sub(r'\s{2,}', ' ', text).strip()

    text = _PHOTO_LANGUAGE_RE.sub('', text).strip()
    text = re.sub(r'\s{2,}', ' ', text).strip()

    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    if context_type in ("low_signal", "media_content"):
        words = text.split()
        if len(words) > 20:
            text = " ".join(words[:20]) + "."
    else:
        words = text.split()
        if len(words) > 80:
            text = " ".join(words[:80]) + "."
    return text


def node_guardrail(state: PipelineState) -> PipelineState:
    """
    Run the Safety Guardrail Agent — final veto before user delivery.

    Context-aware: adjusts response tone and length based on context_type.
    Scam responses name the specific scam type in the first sentence.

    Sets: final_decision.
    Reads: event, draft_response, risk_flag, next_steps, evidence_items, context_type.
    """
    event = state["event"]
    draft = state.get("draft_response", "")
    context_type = state.get("context_type", "default")

    guardrail_resp = _guardrail.run(event, draft)

    from agents.output_filter import filter_output
    draft = filter_output(draft)

    event_text = event.redacted_text

    if guardrail_resp.output_text:
        logger.debug("node_guardrail | result=HARD_BLOCK")
        decision = FinalDecision(
            response_text=_enforce_quality(guardrail_resp.output_text, context_type, event_text),
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    elif guardrail_resp.requires_human_review:
        logger.debug("node_guardrail | result=SCAM_FLAG context=%s", context_type)
        scam_response = _guardrail.get_scam_response(event_text)
        decision = FinalDecision(
            response_text=_enforce_quality(scam_response, context_type, event_text),
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    else:
        logger.debug("node_guardrail | result=PASS context=%s", context_type)
        decision = FinalDecision(
            response_text=_enforce_quality(draft, context_type, event_text),
            risk_flag=state.get("risk_flag", RiskLevel.SOFT_HELP),
            next_steps=state.get("next_steps", []),
            source_citations=state.get("evidence_items", []),
        )

    if (event.event_type == EventType.DOCUMENT
            and any(p.search(event.redacted_text) for p in _COMPILED_SAFE)
            and decision.risk_flag == RiskLevel.STOP_AND_VERIFY):
        logger.info("node_guardrail | safe-document override: %s -> none", event.event_type.value)
        decision = FinalDecision(
            response_text=_enforce_quality(draft or decision.response_text, context_type, event_text),
            risk_flag=RiskLevel.NONE,
            next_steps=[],
            source_citations=state.get("evidence_items", []),
        )

    return {**state, "final_decision": decision}
