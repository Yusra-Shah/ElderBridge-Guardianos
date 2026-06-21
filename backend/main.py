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

import asyncio
import concurrent.futures
import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import os

from dotenv import load_dotenv

# Load .env — backend-local first, fall back to project root.  No-op if
# neither exists (production uses real env vars injected by the deployment
# environment).
_env_backend = Path(__file__).parent / ".env"
_env_root = Path(__file__).parent.parent / ".env"
if _env_backend.exists():
    load_dotenv(_env_backend, override=True)
elif _env_root.exists():
    load_dotenv(_env_root, override=True)

print(f"[STARTUP] Azure key loaded: {bool(os.environ.get('AZURE_OPENAI_API_KEY'))}")
print(f"[STARTUP] Deployment: {os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'NOT SET')}")

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from agents.chat_handler import handle_chat_question, _CHAT_FALLBACK
from agents.emergency_scam_detector import detect_emergency_scam, EMERGENCY_SCAM_RESPONSE, EMERGENCY_SCAM_NEXT_STEPS
from agents.form_cache import check_form_cache
from agents.fraud_detector import detect_financial_fraud, FRAUD_BLOCK_RESPONSE, FRAUD_NEXT_STEPS
from agents.injection_detector import detect_injection, INJECTION_BLOCK_RESPONSE
from agents.phishing_detector import detect_phishing, PHISHING_BLOCK_RESPONSE, PHISHING_NEXT_STEPS
from graph.build_graph import run_graph
from middleware.security_middleware import check_rate_limit, validate_replay_protection, get_client_ip
from schemas.decision_schema import FinalDecision, RiskLevel
from schemas.event_schema import EventType, IncomingEvent
from secure_logging.secure_logger import setup_secure_logging


# ---------------------------------------------------------------------------
# Pre-pipeline safe-document bypass — runs before ANY agent touches the event.
# Medical reports, lab results, and clinical documents from mail apps must
# never be flagged as scams regardless of what keywords they contain.
# ---------------------------------------------------------------------------

_MEDICAL_KEYWORDS = [
    "clinical laboratory", "aga khan", "laboratory@aku",
    "specimen", "patient name", "lab report", "test result",
    "medical report", "hospital report", "discharge summary",
    "prescription", "diagnostic report",
]

_MAIL_SOURCES = ["gmail", "mail", "outlook", "yahoo", "email", "com.google.android.gm"]


def is_safe_medical_document(event: IncomingEvent) -> bool:
    """Return True if the event is a medical document from a mail app."""
    text = (event.redacted_text or "").lower()
    source = (event.source_app or "").lower()
    event_type = (event.event_type.value if event.event_type else "").lower()

    is_mail = any(s in source for s in _MAIL_SOURCES) or event_type == "document"
    has_medical = any(kw in text for kw in _MEDICAL_KEYWORDS)

    return is_mail and has_medical


_SAFE_MEDICAL_RESPONSE = FinalDecision(
    response_text=(
        "This is a medical report or lab result sent to you by email. "
        "It is a normal clinical document. Check the report for your "
        "test results and the doctor's notes. If you have questions "
        "about the results, contact your doctor or the hospital."
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[
        "Open the attached PDF to see your results",
        "Contact your doctor if you have questions",
    ],
    source_citations=[],
)


# ---------------------------------------------------------------------------
# Post-pipeline gov site flag override — lets the LLM produce a helpful
# response body but forces risk_flag=none so the header does not say
# "Stop and check" for legitimate government websites.
# ---------------------------------------------------------------------------

_BROWSER_APPS = ["chrome", "firefox", "browser", "com.android.chrome", "org.mozilla"]

_GOV_DOMAINS = [
    ".gov.pk", "nadra.gov.pk", "fbr.gov.pk", "sbp.org.pk",
    "pass.gov.pk", "ehsaas.gov.pk", "swd.sindh.gov.pk",
    "punjab.gov.pk", "kp.gov.pk", "balochistan.gov.pk",
    "pakpost.gov.pk", "pta.gov.pk", "secp.gov.pk",
]


def is_official_gov_site(event: IncomingEvent) -> bool:
    """Return True if the event is from a browser showing an official .gov.pk site."""
    text = (event.redacted_text or "").lower()
    source = (event.source_app or "").lower()
    is_browser = any(b in source for b in _BROWSER_APPS)
    has_gov = any(d in text for d in _GOV_DOMAINS)
    return is_browser and has_gov


# ---------------------------------------------------------------------------
# Pre-pipeline telecom promotional SMS bypass — legitimate marketing messages
# from Pakistani mobile networks should not be flagged as scams.
# ---------------------------------------------------------------------------

_TELECOM_PROMO_BRANDS = [
    "ufone", "jazz", "telenor", "zong", "upaisa", "jazzcash",
    "jazz cash", "easypaisa", "mobilink",
]

_TELECOM_PROMO_SIGNALS = [
    "bundle", "cashback", "recharge", "reactivate",
    "t&cs apply", "terms and conditions", "data offer",
    "free minutes", "free sms", "mb free", "gb free",
]

_TELECOM_DANGER_WORDS = [
    "otp", "pin", "password", "cnic", "account number",
    "send money", "transfer rs", "transfer pkr",
]


_SMS_APP_FRAGMENTS = [
    "com.android.messaging", "com.google.android.apps.messaging",
    "com.samsung.android.messaging", "com.miui.messaging",
    "com.sonyericsson.conversations", "org.thoughtcrime.securesms",
    "com.android.mms",
]


def _is_sms_source(source_app: str) -> bool:
    source = source_app.lower()
    return any(app in source for app in _SMS_APP_FRAGMENTS) or "sms" in source


def is_telecom_promotional(event: IncomingEvent) -> bool:
    """Return True if the event is a legitimate telecom promotional SMS."""
    text = (event.redacted_text or "").lower()

    if not _is_sms_source(event.source_app):
        return False

    has_brand = any(b in text for b in _TELECOM_PROMO_BRANDS)
    has_promo = any(p in text for p in _TELECOM_PROMO_SIGNALS)
    has_danger = any(d in text for d in _TELECOM_DANGER_WORDS)

    return has_brand and has_promo and not has_danger


_TELECOM_PROMO_RESPONSE = FinalDecision(
    response_text=(
        "This is a promotional message from your mobile network. "
        "It is advertising a bundle, cashback, or prize offer. "
        "You do not need to do anything unless you want to join. "
        "If you did not ask for this, you can ignore it."
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[
        "Read the offer if interested",
        "Ignore if not interested",
    ],
    source_citations=[],
)


logger = logging.getLogger("elderbridge")

# ---------------------------------------------------------------------------
# Response cache — avoids re-running the full pipeline when the user taps
# the same bubble twice within 5 minutes.
# ---------------------------------------------------------------------------
_response_cache: dict[str, tuple[float, FinalDecision]] = {}
_CACHE_TTL = 300  # 5 minutes

_SAFE_FALLBACK = FinalDecision(
    response_text=(
        "ElderBridge could not analyse this screen right now. "
        "If you need urgent help, call 1122. "
        "If this keeps happening, please restart the assistant."
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[],
    source_citations=[],
)

_pipeline_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# Tiered timeouts by event type
# ---------------------------------------------------------------------------
_TIMEOUTS: dict[EventType, float] = {
    EventType.SMS: 12.0,
    EventType.NOTIFICATION: 12.0,
    EventType.FORM_SCREEN: 40.0,
    EventType.DOCUMENT: 40.0,
}
_DEFAULT_TIMEOUT = 25.0


def _get_timeout(event: IncomingEvent) -> float:
    return _TIMEOUTS.get(event.event_type, _DEFAULT_TIMEOUT)


def _assemble_partial(state: dict) -> FinalDecision | None:
    """Try to build a FinalDecision from partial pipeline state."""
    responses = state.get("agent_responses", [])
    _USER_FACING = {"BenefitsAgent", "FormAgent"}
    non_fallback = [
        r for r in responses
        if not r.used_fallback and r.output_text and r.agent_name in _USER_FACING
    ]
    if non_fallback:
        best = max(non_fallback, key=lambda r: r.confidence)
        from agents.output_filter import filter_output
        return FinalDecision(
            response_text=filter_output(best.output_text),
            risk_flag=state.get("risk_flag", RiskLevel.NONE),
            next_steps=state.get("next_steps", []),
            source_citations=state.get("evidence_items", []),
        )
    draft = state.get("draft_response", "")
    if draft:
        return FinalDecision(
            response_text=draft,
            risk_flag=state.get("risk_flag", RiskLevel.NONE),
            next_steps=state.get("next_steps", []),
            source_citations=[],
        )
    return None


def _cache_key(event: IncomingEvent) -> str:
    raw = f"{event.event_type.value}:{event.redacted_text}"
    return hashlib.sha256(raw.encode()).hexdigest()


# Increment this on every milestone/release.
# v0.5.0 changelog:
#   - fraud detector, form cache, chat handler, phishing detector, emergency scam detector
#   - safe-app bypass, context classification, baseline signal extraction
#   - tiered timeouts, partial result degradation, research non-blocking
#   - guardrail scam-type naming, response quality enforcement
#   - router low-signal and media content detection
_VERSION = "0.5.0"

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

setup_secure_logging()

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    print(f"[422 ERROR] Validation failed: {exc.errors()}")
    print(f"[422 ERROR] Body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


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
    """Liveness probe — returns 200 with version and capabilities."""
    return {
        "status": "ok",
        "version": _VERSION,
        "capabilities": [
            "investment_fraud_detection",
            "phishing_site_detection",
            "emergency_scam_detection",
            "prize_lottery_scam_detection",
            "government_form_assistance",
            "banking_app_safe_bypass",
            "chat_question_answering",
            "low_signal_filtering",
        ],
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
async def analyze_event(event: IncomingEvent, request: Request) -> FinalDecision:
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
    try:
        client_ip = get_client_ip(request)
        check_rate_limit(client_ip, "analyze-event")
        if detect_injection(event.redacted_text):
            return FinalDecision(
                response_text=INJECTION_BLOCK_RESPONSE,
                risk_flag=RiskLevel.STOP_AND_VERIFY,
                next_steps=["Do not interact with this screen.", "Close it immediately."],
                source_citations=[],
            )

        if is_telecom_promotional(event):
            logger.info("analyze-event | telecom promo bypass for user=%s", event.user_id)
            return _TELECOM_PROMO_RESPONSE

        if detect_financial_fraud(event.redacted_text):
            logger.warning("analyze-event | financial fraud detected for user=%s", event.user_id)
            return FinalDecision(
                response_text=FRAUD_BLOCK_RESPONSE,
                risk_flag=RiskLevel.STOP_AND_VERIFY,
                next_steps=FRAUD_NEXT_STEPS,
                source_citations=[],
            )

        if detect_phishing(event.redacted_text, event.source_app):
            logger.warning("analyze-event | phishing detected for user=%s", event.user_id)
            return FinalDecision(
                response_text=PHISHING_BLOCK_RESPONSE,
                risk_flag=RiskLevel.STOP_AND_VERIFY,
                next_steps=PHISHING_NEXT_STEPS,
                source_citations=[],
            )

        if detect_emergency_scam(event.redacted_text):
            logger.warning("analyze-event | emergency scam detected for user=%s", event.user_id)
            return FinalDecision(
                response_text=EMERGENCY_SCAM_RESPONSE,
                risk_flag=RiskLevel.STOP_AND_VERIFY,
                next_steps=EMERGENCY_SCAM_NEXT_STEPS,
                source_citations=[],
            )

        if is_safe_medical_document(event):
            logger.info("analyze-event | safe medical document bypass for user=%s", event.user_id)
            return _SAFE_MEDICAL_RESPONSE

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
        )

        key = _cache_key(event)
        cached = _response_cache.get(key)
        if cached:
            cached_time, cached_result = cached
            if time.time() - cached_time < _CACHE_TTL:
                print(f"[CACHE] Hit for event {key[:8]}")
                logger.info("analyze-event | cache hit for user=%s", event.user_id)
                return cached_result
            del _response_cache[key]

        form_cached = check_form_cache(event.redacted_text, event.source_app)
        if form_cached is not None:
            print(f"[FORM_CACHE] Hit for user {event.user_id}")
            logger.info("analyze-event | form cache hit for user=%s", event.user_id)
            _response_cache[key] = (time.time(), form_cached)
            return form_cached

        timeout = _get_timeout(event)
        loop = asyncio.get_running_loop()
        partial_store: dict = {}
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _pipeline_executor,
                    lambda: run_graph(event, partial_store),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("analyze-event | pipeline timed out after %.0fs", timeout)
            partial_state = partial_store.get("state")
            if partial_state:
                partial_result = _assemble_partial(partial_state)
                if partial_result is not None:
                    logger.info("analyze-event | assembled partial result for user=%s", event.user_id)
                    _response_cache[key] = (time.time(), partial_result)
                    return partial_result
            return _SAFE_FALLBACK

        if is_official_gov_site(event) and result.risk_flag in (
            RiskLevel.STOP_AND_VERIFY, RiskLevel.VERIFY_FIRST, RiskLevel.CAUTION,
        ):
            logger.info("analyze-event | gov site flag override for user=%s", event.user_id)
            result = FinalDecision(
                response_text=result.response_text,
                risk_flag=RiskLevel.NONE,
                next_steps=[],
                source_citations=result.source_citations,
            )

        _response_cache[key] = (time.time(), result)
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pipeline failure: %s", type(exc).__name__)
        return _SAFE_FALLBACK


# ---------------------------------------------------------------------------
# User profile — in-memory storage for demo
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    name: str | None = None
    location: str | None = None
    emergency_contact: str | None = None
    caregiver_contact: str | None = None
    language: str | None = None

_user_profiles: dict[str, dict] = {}


@app.post("/user-profile", tags=["profile"])
async def save_user_profile(user_id: str, profile: UserProfile) -> dict:
    """Store a user profile in memory (demo — no database)."""
    _user_profiles[user_id] = profile.model_dump(exclude_none=True)
    return {"status": "saved"}


@app.get("/user-profile/{user_id}", tags=["profile"])
async def get_user_profile(user_id: str) -> dict:
    """Retrieve a stored user profile, or empty dict if not found."""
    return _user_profiles.get(user_id, {})


# ---------------------------------------------------------------------------
# Chat endpoint — multi-turn conversation with history
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(
        ...,
        validation_alias=AliasChoices("user_id", "userId"),
        min_length=1, max_length=64,
    )
    messages: list[ChatMessage] = Field(default_factory=list)
    screen_context: str = Field(
        default="",
        validation_alias=AliasChoices("screen_context", "screenContext"),
    )
    question: str = Field(default="", max_length=1024)

    @field_validator("screen_context")
    @classmethod
    def truncate_screen_context(cls, v: str) -> str:
        if v and len(v) > 2048:
            return v[:2048]
        return v


_CHAT_TIMEOUT = 30.0


@app.post(
    "/ask-question",
    response_model=FinalDecision,
    tags=["chat"],
    summary="Multi-turn chat: answer a question with full conversation history.",
)
async def ask_question(req: ChatRequest, request: Request) -> FinalDecision:
    """Multi-turn chat path with conversation history. No full pipeline."""
    try:
        client_ip = get_client_ip(request)
        check_rate_limit(client_ip, "ask-question")

        last_user_text = req.question
        if req.messages:
            for m in reversed(req.messages):
                if m.role == "user":
                    last_user_text = m.content
                    break

        if last_user_text and detect_injection(last_user_text):
            return FinalDecision(
                response_text=INJECTION_BLOCK_RESPONSE,
                risk_flag=RiskLevel.STOP_AND_VERIFY,
                next_steps=["Do not interact with this screen.", "Close it immediately."],
                source_citations=[],
            )

        logger.info("ask-question | user=%s msgs=%d", req.user_id, len(req.messages))

        msgs: list[dict] | None = None
        question = req.question

        if req.messages:
            msgs = [{"role": m.role, "content": m.content} for m in req.messages]
        elif question and question.strip():
            msgs = [{"role": "user", "content": question}]

        if not msgs and not (question and question.strip()):
            return _CHAT_FALLBACK

        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                _pipeline_executor,
                lambda: handle_chat_question(
                    messages=msgs,
                    screen_context=req.screen_context,
                    question=question if not msgs else "",
                ),
            ),
            timeout=_CHAT_TIMEOUT,
        )
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat failure: %s", type(exc).__name__)
        return _CHAT_FALLBACK
