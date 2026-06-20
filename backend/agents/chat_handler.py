"""
Lightweight chat handler for follow-up questions.

Provides a single fast LLM call path for the "Ask a Question" chat feature.
Does NOT run the full multi-agent pipeline.  Has its own timeout and its own
chat-specific fallback text that never mentions "could not analyse this screen."

The system prompt is tuned to answer the user's specific question directly
and concisely.  It does not re-summarize the screen context.
"""
from __future__ import annotations

import logging

import re

from agents.phishing_detector import _OFFICIAL_DOMAINS, _DOMAIN_RE, _EMAIL_RE
from llm.client import LLMUnavailableError, call_llm
from schemas.decision_schema import FinalDecision, RiskLevel

logger = logging.getLogger("elderbridge.chat")

_AUTHENTICITY_QUESTIONS = re.compile(
    r"(is\s+this\s+(website|site|page)\s+(authentic|safe|real|legitimate|legit|genuine|official|trusted))"
    r"|(is\s+this\s+real)"
    r"|(is\s+this\s+safe)",
    re.IGNORECASE,
)

_GOV_PK_RE = re.compile(r'[a-zA-Z0-9.-]+\.gov\.pk\b', re.IGNORECASE)

_ALL_OFFICIAL_DOMAINS: set[str] = set()
for _domains in _OFFICIAL_DOMAINS.values():
    _ALL_OFFICIAL_DOMAINS.update(d.lower() for d in _domains)


def _check_website_authenticity(question: str, screen_context: str) -> FinalDecision | None:
    """Return an instant cached answer for website authenticity questions on known domains."""
    if not _AUTHENTICITY_QUESTIONS.search(question):
        return None
    if not screen_context:
        return None

    ctx_lower = screen_context.lower()

    if _GOV_PK_RE.search(screen_context):
        return FinalDecision(
            response_text=(
                "Yes, this is an official Pakistani government website. The address "
                "ends in .gov.pk which means it is a verified government site. It is "
                "safe to use. If the web address ever looks different from what you "
                "expect, close the page and type the address yourself."
            ),
            risk_flag=RiskLevel.NONE,
            next_steps=[],
            source_citations=[],
        )

    for domain_list in _OFFICIAL_DOMAINS.values():
        for d in domain_list:
            if d.lower() in ctx_lower:
                return FinalDecision(
                    response_text=(
                        "Yes, this appears to be an official website. The address matches "
                        "a known Pakistani institution. It is safe to use. Always double "
                        "check the address in your browser bar before entering personal details."
                    ),
                    risk_flag=RiskLevel.NONE,
                    next_steps=[],
                    source_citations=[],
                )

    domains_in_ctx = [m.group(1).lower() for m in _DOMAIN_RE.finditer(screen_context)
                      if not screen_context[max(0, m.start()-1):m.start()].endswith("@")]
    for d in domains_in_ctx:
        if not d.endswith(".gov.pk") and d not in _ALL_OFFICIAL_DOMAINS:
            for inst in _OFFICIAL_DOMAINS:
                if inst in ctx_lower:
                    return FinalDecision(
                        response_text=(
                            "No, be careful. This web address does not end in .gov.pk "
                            "which all real Pakistani government websites use. Do not "
                            "enter your CNIC or any personal details here. Visit the "
                            "official .gov.pk website directly or go to the office in person."
                        ),
                        risk_flag=RiskLevel.STOP_AND_VERIFY,
                        next_steps=["Close this website.", "Do not enter personal details."],
                        source_citations=[],
                    )

    return None

_CHAT_SYSTEM_PROMPT = (
    "You are ElderBridge, a helpful assistant for elderly people in Pakistan.\n"
    "The user is asking a follow-up question about something on their phone screen.\n\n"
    "RULES:\n"
    "Answer the question directly in one to three plain sentences.\n"
    "Lead with the answer. Do not re-summarize the screen or repeat what the user already knows.\n"
    "If the user asks what a word or term means, define it plainly in one or two sentences.\n"
    "Use simple language an elderly person would understand.\n"
    "No markdown. No dashes as punctuation. No bullet points. Plain text only.\n"
    "If you are unsure, say so honestly and suggest asking a trusted person.\n"
    "Never request OTP, PIN, password, or bank details.\n"
    "Never mention OTP unless the word OTP or one-time password appears in the screen context.\n"
    "Only describe what is explicitly visible in the screen text. Never invent or assume "
    "information that is not present.\n"
    "Never tell the user to share, upload, or take a photo. ElderBridge has no camera or "
    "image input. If the user needs to describe something, ask them to type or read it aloud.\n"
    "If asked about website authenticity, check the URL in the screen context. Official "
    "Pakistani government sites always end in .gov.pk. Answer directly yes or no first, "
    "then explain.\n"
    # NOTE for Kaneeza: the "Looking into this for you" loading text is controlled
    # on the Android side in OverlayService.kt, not here.
    "Keep your answer under 60 words.\n"
)

_CHAT_FALLBACK = FinalDecision(
    response_text=(
        "I am sorry, I could not find the answer to your question right now. "
        "Please try asking in a different way, or ask a trusted family member "
        "or caregiver for help."
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[],
    source_citations=[],
)


def handle_chat_question(
    question: str,
    screen_context: str = "",
) -> FinalDecision:
    """Answer a user's follow-up question with a single fast LLM call.

    Args:
        question:       The user's text question.
        screen_context: Optional screen text from a previous analysis.

    Returns:
        FinalDecision with the answer as response_text and risk_flag=none.
    """
    if not question or not question.strip():
        return _CHAT_FALLBACK

    auth_answer = _check_website_authenticity(question, screen_context)
    if auth_answer is not None:
        return auth_answer

    parts = []
    if screen_context and screen_context.strip():
        parts.append(
            f"Screen context (do NOT repeat this back, just use it to understand "
            f"what the user is looking at): {screen_context[:400]}"
        )
    parts.append(f"User question: {question}")
    user_message = "\n".join(parts)

    try:
        response_text = call_llm(
            _CHAT_SYSTEM_PROMPT,
            user_message,
            max_tokens=512,
        )
        if not response_text or not response_text.strip():
            return _CHAT_FALLBACK

        return FinalDecision(
            response_text=response_text.strip(),
            risk_flag=RiskLevel.NONE,
            next_steps=[],
            source_citations=[],
        )
    except (LLMUnavailableError, Exception) as exc:
        logger.warning("Chat LLM call failed: %s", exc)
        return _CHAT_FALLBACK
