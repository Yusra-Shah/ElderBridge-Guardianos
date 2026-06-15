"""
ElderBridge GuardianOS — agent pipeline orchestrator.

Implements the ordered pipeline described in ARCHITECTURE.md §5:

  IncomingEvent
    → RouterAgent            (decides which specialists to invoke)
    → [Specialist agents]    (BenefitsAgent | FormAgent | ResearchAgent)
    → CriticAgent            (rewrites overclaiming language)
    → GuardrailAgent         (final safety veto)
    → FinalDecision

This module owns the rule-based baseline logic (risk scoring + response
templates) that drives the FinalDecision until specialist agents produce
real LLM-backed outputs in a later milestone.

No external API calls are made here.  All logic is deterministic and
runs offline.
"""
from __future__ import annotations

import logging
from typing import List

from agents.benefits_agent import BenefitsAgent
from agents.critic_agent import CriticAgent
from agents.form_agent import FormAgent
from agents.guardrail_agent import GuardrailAgent
from agents.research_agent import ResearchAgent
from agents.router_agent import RouterAgent
from schemas.decision_schema import AgentResponse, EvidenceItem, FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.orchestrator")

# ---------------------------------------------------------------------------
# Rule-based baseline engine
# Provides risk_flag + response_text + next_steps before real agents are live.
# ---------------------------------------------------------------------------

_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.NONE: 0,
    RiskLevel.SILENT: 1,
    RiskLevel.SOFT_HELP: 2,
    RiskLevel.CAUTION: 3,
    RiskLevel.VERIFY_FIRST: 4,
    RiskLevel.STOP_AND_VERIFY: 5,
    RiskLevel.CONTACT_TRUSTED_PERSON: 6,
}

# Baseline risk by event category.
# FORM_SCREEN and DOCUMENT start at NONE — they are help requests, not threats.
_EVENT_BASE_RISK: dict[EventType, RiskLevel] = {
    EventType.SMS: RiskLevel.CAUTION,
    EventType.NOTIFICATION: RiskLevel.CAUTION,
    EventType.FORM_SCREEN: RiskLevel.NONE,
    EventType.DOCUMENT: RiskLevel.NONE,
}

# Keyword → risk level escalation rules.
# Checked against the lowercased redacted_text; first match that beats the
# current level wins (we take the maximum).
_KEYWORD_RULES: list[tuple[str, RiskLevel]] = [
    # Critical — always escalate to STOP_AND_VERIFY
    ("enter your otp", RiskLevel.STOP_AND_VERIFY),
    ("enter the otp", RiskLevel.STOP_AND_VERIFY),
    ("send your otp", RiskLevel.STOP_AND_VERIFY),
    ("otp",             RiskLevel.STOP_AND_VERIFY),
    ("[redacted_otp]",  RiskLevel.STOP_AND_VERIFY),
    ("password",        RiskLevel.STOP_AND_VERIFY),
    ("transfer",        RiskLevel.STOP_AND_VERIFY),
    ("send money",      RiskLevel.STOP_AND_VERIFY),

    # High — escalate to VERIFY_FIRST
    ("urgent",           RiskLevel.VERIFY_FIRST),
    ("immediately",      RiskLevel.VERIFY_FIRST),
    ("cnic",             RiskLevel.VERIFY_FIRST),
    ("[redacted_cnic]",  RiskLevel.VERIFY_FIRST),
    ("grant approved",   RiskLevel.VERIFY_FIRST),
    ("benefit approved", RiskLevel.VERIFY_FIRST),
    ("claim your",       RiskLevel.VERIFY_FIRST),
    ("expire",           RiskLevel.VERIFY_FIRST),
    ("suspended",        RiskLevel.VERIFY_FIRST),
    ("blocked",          RiskLevel.VERIFY_FIRST),

    # Medium — escalate to CAUTION
    ("click here",    RiskLevel.CAUTION),
    ("tap here",      RiskLevel.CAUTION),
    ("limited time",  RiskLevel.CAUTION),
    ("act now",       RiskLevel.CAUTION),
]

_RESPONSE_TEMPLATES: dict[RiskLevel, dict[str, object]] = {
    RiskLevel.NONE: {
        "response_text": (
            "I am here to help whenever you need me. "
            "Everything looks routine right now."
        ),
        "next_steps": [],
    },
    RiskLevel.SILENT: {
        "response_text": "Everything looks routine. No action needed right now.",
        "next_steps": [],
    },
    RiskLevel.SOFT_HELP: {
        "response_text": (
            "I am here to help. Tap or ask if you need anything explained."
        ),
        "next_steps": ["Ask me about any field or word you find confusing."],
    },
    RiskLevel.CAUTION: {
        "response_text": (
            "Please take a moment before continuing. "
            "This may need a quick check."
        ),
        "next_steps": [
            "Read the message carefully before responding.",
            "If unsure, ask a trusted family member or caregiver first.",
        ],
    },
    RiskLevel.VERIFY_FIRST: {
        "response_text": (
            "Please pause before continuing. "
            "I could not verify this from an official source. "
            "It may be asking for private information."
        ),
        "next_steps": [
            "Do not enter any personal information yet.",
            "Visit the official website or call the official helpline directly.",
            "Ask a trusted family member or caregiver to review with you.",
        ],
    },
    RiskLevel.STOP_AND_VERIFY: {
        "response_text": (
            "Please stop and do not continue. "
            "This message may be asking for private information such as a code or password. "
            "Official agencies never ask for these details by message."
        ),
        "next_steps": [
            "Do not share any code, password, or personal number.",
            "Close this screen or message.",
            "Call the official agency directly using a number you already know.",
            "Contact your trusted family member or caregiver immediately.",
        ],
    },
    RiskLevel.CONTACT_TRUSTED_PERSON: {
        "response_text": (
            "Please contact your trusted person right now before doing anything else."
        ),
        "next_steps": [
            "Do not take any action until you have spoken to your trusted contact.",
            "Your trusted contact has been notified (if configured).",
        ],
    },
}

# ---------------------------------------------------------------------------
# Specialist agent registry
# Keys must match the strings returned by RouterAgent.route()
# ---------------------------------------------------------------------------

_SPECIALIST_REGISTRY: dict[str, BenefitsAgent | FormAgent | ResearchAgent] = {
    "BenefitsAgent": BenefitsAgent(),
    "FormAgent": FormAgent(),
    "ResearchAgent": ResearchAgent(),
}

# ---------------------------------------------------------------------------
# Singleton agent instances shared across requests (stateless)
# ---------------------------------------------------------------------------

_router = RouterAgent()
_critic = CriticAgent()
_guardrail = GuardrailAgent()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_baseline(event: IncomingEvent) -> tuple[RiskLevel, str, list[str]]:
    """
    Rule-based risk assessment for the event.

    Returns (risk_level, response_text, next_steps).

    Uses keyword escalation over the event's redacted_text.  This is the
    backbone decision layer until specialist agents produce LLM outputs.
    """
    current = _EVENT_BASE_RISK.get(event.event_type, RiskLevel.SOFT_HELP)
    text_lower = event.redacted_text.lower()

    for keyword, level in _KEYWORD_RULES:
        if keyword in text_lower and _RISK_RANK[level] > _RISK_RANK[current]:
            current = level

    template = _RESPONSE_TEMPLATES[current]
    return current, str(template["response_text"]), list(template["next_steps"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Public pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(event: IncomingEvent) -> FinalDecision:
    """
    Run the full agent pipeline for one IncomingEvent.

    Pipeline order (ARCHITECTURE.md §5):
      1. Rule-based baseline  — compute initial risk_flag + response text
      2. RouterAgent          — determine which specialists to invoke
      3. Specialist agents    — run each in routing order
      4. CriticAgent          — rewrite overclaiming language in specialist outputs
      5. GuardrailAgent       — final safety veto on draft_text + event text
      6. Assemble FinalDecision

    Args:
        event: Validated, redacted IncomingEvent from the API endpoint.

    Returns:
        FinalDecision — safe to deliver to the Android client.
    """
    logger.debug(
        "pipeline start | event_type=%s source_app=%s user=%s",
        event.event_type.value,
        event.source_app,
        event.user_id,
    )

    # ── Step 1: Baseline ────────────────────────────────────────────────────
    risk_flag, response_text, next_steps = _compute_baseline(event)

    # ── Step 2: Router ──────────────────────────────────────────────────────
    specialist_names: List[str] = _router.route(event)
    logger.debug("router selected: %s", specialist_names)

    # ── Step 3: Specialists ─────────────────────────────────────────────────
    specialist_responses: List[AgentResponse] = []
    for name in specialist_names:
        agent = _SPECIALIST_REGISTRY.get(name)
        if agent is None:
            logger.warning("router returned unknown agent name: %s — skipping", name)
            continue
        resp = agent.run(event)
        specialist_responses.append(resp)
        logger.debug("specialist %s | confidence=%.2f", name, resp.confidence)

    # ── Step 4: Critic ──────────────────────────────────────────────────────
    critic_resp = _critic.run(event, specialist_responses)
    if critic_resp.requires_human_review:
        logger.info(
            "critic flagged overclaiming in specialist outputs | event_type=%s",
            event.event_type.value,
        )
        # Critic rewrote something — lower confidence in specialist outputs.
        # The baseline response_text is still used; the critic's cleaned text
        # is for logging and future LLM integration.

    # ── Step 5: Guardrail ───────────────────────────────────────────────────
    guardrail_resp = _guardrail.run(event, response_text)

    if guardrail_resp.requires_human_review:
        # BLOCKED — override everything with the safe fallback
        logger.warning(
            "guardrail BLOCKED | event_type=%s source_app=%s",
            event.event_type.value,
            event.source_app,
        )
        return FinalDecision(
            response_text=guardrail_resp.output_text,
            risk_flag=RiskLevel.STOP_AND_VERIFY,
            next_steps=_guardrail.safe_next_steps,
            source_citations=[],
        )

    # ── Step 6: Assemble final decision ─────────────────────────────────────
    # Collect EvidenceItems from all specialist agents, deduplicated by source_id.
    all_evidence: list[EvidenceItem] = []
    seen_source_ids: set[str] = set()
    for resp in specialist_responses:
        for item in resp.evidence_items:
            if item.source_id not in seen_source_ids:
                seen_source_ids.add(item.source_id)
                all_evidence.append(item)

    logger.debug(
        "pipeline complete | risk_flag=%s evidence_items=%d",
        risk_flag.value,
        len(all_evidence),
    )

    return FinalDecision(
        response_text=response_text,
        risk_flag=risk_flag,
        next_steps=next_steps,
        source_citations=all_evidence,
    )
