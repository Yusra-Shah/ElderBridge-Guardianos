"""
ElderBridge GuardianOS — FastAPI backend entry point.

Exposes a single decision endpoint (/analyze-event) that the Android client
calls after local PII redaction.  This milestone uses rule-based logic only;
LangGraph multi-agent orchestration will be wired in a later milestone.

Security notes (SECURITY_MODEL.md §7):
  - All secrets are loaded from environment variables — never hardcoded.
  - No raw PII may appear in logs (see redacted_text contract in event_schema).
  - Auth middleware will be added before production deployment.

Environment variables required (set in deployment environment, never in code):
  ELDERBRIDGE_API_KEY — shared secret for device-to-backend auth (future)
  LOG_LEVEL           — uvicorn log level (default: info)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from schemas.decision_schema import FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("elderbridge")

app = FastAPI(
    title="ElderBridge GuardianOS API",
    description=(
        "Privacy-first AI decision backend for the ElderBridge Android companion. "
        "Receives redacted device events and returns plain-language guidance."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Rule-based decision logic (pre-agent scaffolding)
# ---------------------------------------------------------------------------

# Keyword patterns that elevate risk without needing agent inference.
# These mirror the local rule engine on-device and serve as a backend
# sanity-check.  Each tuple is (pattern_substring, risk_level).
_KEYWORD_RULES: list[tuple[str, RiskLevel]] = [
    ("otp", RiskLevel.STOP_AND_VERIFY),
    ("[redacted_otp]", RiskLevel.STOP_AND_VERIFY),
    ("password", RiskLevel.STOP_AND_VERIFY),
    ("transfer", RiskLevel.STOP_AND_VERIFY),
    ("send money", RiskLevel.STOP_AND_VERIFY),
    ("urgent", RiskLevel.VERIFY_FIRST),
    ("immediately", RiskLevel.VERIFY_FIRST),
    ("cnic", RiskLevel.VERIFY_FIRST),
    ("[redacted_cnic]", RiskLevel.VERIFY_FIRST),
    ("grant approved", RiskLevel.VERIFY_FIRST),
    ("claim your", RiskLevel.VERIFY_FIRST),
    ("benefit approved", RiskLevel.VERIFY_FIRST),
    ("click here", RiskLevel.CAUTION),
    ("tap here", RiskLevel.CAUTION),
    ("limited time", RiskLevel.CAUTION),
]

_EVENT_BASE_RISK: dict[EventType, RiskLevel] = {
    EventType.SMS: RiskLevel.CAUTION,
    EventType.NOTIFICATION: RiskLevel.CAUTION,
    EventType.FORM_SCREEN: RiskLevel.SOFT_HELP,
    EventType.DOCUMENT: RiskLevel.SOFT_HELP,
}

_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.SILENT: 0,
    RiskLevel.SOFT_HELP: 1,
    RiskLevel.CAUTION: 2,
    RiskLevel.VERIFY_FIRST: 3,
    RiskLevel.STOP_AND_VERIFY: 4,
    RiskLevel.CONTACT_TRUSTED_PERSON: 5,
}

_RESPONSE_TEMPLATES: dict[RiskLevel, dict] = {
    RiskLevel.SILENT: {
        "response_text": "Everything looks routine. No action needed right now.",
        "next_steps": [],
    },
    RiskLevel.SOFT_HELP: {
        "response_text": "I am here to help. Tap or ask if you need anything explained.",
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
            "This message is asking for private information such as a code or password. "
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


def _rule_based_decision(event: IncomingEvent) -> FinalDecision:
    """
    Deterministic risk assessment using keyword rules and event type.

    This runs without any LLM or agent calls.  It mirrors the local rule
    engine on-device to provide a fast, auditable baseline decision.
    The multi-agent ensemble will replace or augment this in milestone 2.
    """
    text_lower = event.redacted_text.lower()

    # Start from the baseline risk for this event category.
    current_level = _EVENT_BASE_RISK.get(event.event_type, RiskLevel.SOFT_HELP)

    # Elevate risk if any keyword pattern matches.
    for pattern, level in _KEYWORD_RULES:
        if pattern in text_lower and _RISK_RANK[level] > _RISK_RANK[current_level]:
            current_level = level

    template = _RESPONSE_TEMPLATES[current_level]
    return FinalDecision(
        response_text=template["response_text"],
        risk_flag=current_level,
        next_steps=template["next_steps"],
        source_citations=[],
    )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health_check() -> dict:
    """Liveness probe — returns 200 if the service is running."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post(
    "/analyze-event",
    response_model=FinalDecision,
    tags=["decision"],
    summary="Analyse a redacted device event and return a safety decision.",
    response_description=(
        "Plain-language guidance, risk level, next steps, and source citations."
    ),
)
async def analyze_event(event: IncomingEvent) -> FinalDecision:
    """
    Main decision endpoint called by the ElderBridge Android client.

    The client MUST redact all PII (OTPs, CNICs, passwords, bank numbers)
    before sending.  The backend applies an additional keyword check as a
    defence-in-depth measure, but it is NOT a substitute for device-side
    redaction (SECURITY_MODEL.md §3, Threat 1).

    Returns a FinalDecision with a risk_flag, plain-language response_text,
    and ordered next_steps.  Agent orchestration will be plugged in here in
    milestone 2; until then a rule-based decision is returned.
    """
    if not event.redacted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="redacted_text must not be empty.",
        )

    logger.info(
        "analyze-event | user=%s event_type=%s source_app=%s",
        event.user_id,
        event.event_type.value,
        event.source_app,
        # NOTE: redacted_text is intentionally excluded from logs even though
        # it is already redacted, to minimise log-based data retention surface.
    )

    return _rule_based_decision(event)
