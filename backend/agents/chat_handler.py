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

from llm.client import LLMUnavailableError, call_llm
from schemas.decision_schema import FinalDecision, RiskLevel

logger = logging.getLogger("elderbridge.chat")

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
