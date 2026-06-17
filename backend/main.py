"""
ElderBridge GuardianOS — FastAPI backend entry point.

Exposes a single decision endpoint (/analyze-event) that the Android client
calls after local PII redaction.  All pipeline logic lives in the graph layer;
this file is concerned only with HTTP transport, validation, and error handling.

Security notes (SECURITY_MODEL.md §7):
  - All secrets are loaded from environment variables — never hardcoded.
  - No raw PII may appear in logs (redacted_text is intentionally omitted).
  - Auth middleware will be added before production deployment.
  - CORS is currently open (allow_origins=["*"]) for local dev/demo ONLY.
    Before any real deployment, restrict allow_origins to the Android app's
    origin or a specific reverse-proxy domain.

Environment variables (set in deployment environment, never in code):
  ELDERBRIDGE_API_KEY — shared secret for device-to-backend auth (future)
  ANTHROPIC_API_KEY   — Anthropic LLM key for BenefitsAgent
  LOG_LEVEL           — uvicorn log level (default: info)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above backend/) before any module
# reads environment variables.  No-op if the file is absent (production uses
# real env vars injected by the deployment environment).
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from graph.build_graph import run_graph
from schemas.decision_schema import FinalDecision
from schemas.event_schema import IncomingEvent

logger = logging.getLogger("elderbridge")

# Increment this on every milestone/release.
_VERSION = "0.4.0"

app = FastAPI(
    title="ElderBridge GuardianOS API",
    description=(
        "Privacy-first AI decision backend for the ElderBridge Android companion. "
        "Receives redacted device events and returns plain-language guidance."
    ),
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — local dev / demo only
# IMPORTANT: allow_origins=["*"] must be replaced with a specific origin list
# before any production or public-facing deployment (SECURITY_MODEL.md §7).
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict to app origin before production
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
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
    """Liveness probe — returns 200 with version if the service is running."""
    return {
        "status": "ok",
        "version": _VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
    before sending.  The backend applies an additional keyword check via the
    GuardrailAgent as defence-in-depth (SECURITY_MODEL.md §3, Threat 1).

    The full pipeline (LangGraph-style graph):
      baseline → router → [fan-out: specialists] → critic → guardrail → FinalDecision

    Returns a FinalDecision with a risk_flag, plain-language response_text,
    and ordered next_steps.
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
        # NOTE: redacted_text intentionally excluded from logs to minimise
        # log-based data retention surface (SECURITY_MODEL.md §9).
    )

    return run_graph(event)
