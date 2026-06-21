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
from llm.client import ContentFilterError, LLMUnavailableError, call_llm, call_llm_chat, sanitize_for_llm
from schemas.decision_schema import FinalDecision, RiskLevel

logger = logging.getLogger("elderbridge.chat")

_AUTHENTICITY_QUESTIONS = re.compile(
    r"(is\s+this\s+(website|site|page)\s+(authentic|safe|real|legitimate|legit|genuine|official|trusted))"
    r"|(is\s+this\s+(an?\s+)?(authentic|safe|real|legitimate|legit|genuine|official|trusted)\s+(website|site|page))"
    r"|(is\s+this\s+real)"
    r"|(is\s+this\s+safe)"
    r"|(is\s+this\s+authentic)",
    re.IGNORECASE,
)

_GOV_PK_RE = re.compile(r'[a-zA-Z0-9.-]+\.gov\.pk\b', re.IGNORECASE)

_ALL_OFFICIAL_DOMAINS: set[str] = set()
for _domains in _OFFICIAL_DOMAINS.values():
    _ALL_OFFICIAL_DOMAINS.update(d.lower() for d in _domains)


def _check_website_authenticity(
    question: str,
    screen_context: str,
    messages: list[dict] | None = None,
) -> FinalDecision | None:
    """Return an instant cached answer for website authenticity questions on known domains.

    Searches both the screen_context and all prior conversation messages for
    .gov.pk domains so the fast-path works even when screen_context is empty
    on follow-up turns.
    """
    if not _AUTHENTICITY_QUESTIONS.search(question):
        return None

    searchable = screen_context or ""
    if messages:
        for m in messages:
            content = m.get("content", "")
            if content:
                searchable += " " + content

    if not searchable.strip():
        return None

    if _GOV_PK_RE.search(searchable):
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

    ctx_lower = searchable.lower()

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

    domains_in_ctx = [m_obj.group(1).lower() for m_obj in _DOMAIN_RE.finditer(searchable)
                      if not searchable[max(0, m_obj.start()-1):m_obj.start()].endswith("@")]
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

def _build_system_prompt(screen_context: str = "") -> str:
    """Build the chat system prompt, embedding sanitized screen context if provided."""
    ctx_block = ""
    if screen_context and screen_context.strip():
        clean = sanitize_for_llm(screen_context[:500])
        ctx_block = (
            f"\nScreen context (what the user is currently looking at):\n"
            f"{clean}\n"
        )

    return (
        "You are ElderBridge, a warm and helpful assistant for elderly people in Pakistan.\n"
        "You are having a real conversation with the user about what they see on their phone screen.\n"
        f"{ctx_block}\n"
        "Rules:\n"
        "Answer conversationally like a trusted family member would.\n"
        "Remember everything said earlier in this conversation.\n"
        "Answer the specific question asked, directly and simply.\n"
        "If the user says thank you, hello, goodbye, or similar, respond warmly and "
        "ask if they need anything else.\n"
        "When checking if a website is authentic, look only for the domain in the browser "
        "address bar at the top of the screen. Ignore URLs in the page body text. "
        "If the address bar contains .gov.pk, the site IS authentic and official.\n"
        "Never use the word OTP in any response. If you see OTP in the screen text, "
        "describe it as 'a verification code' instead. The word OTP must not appear "
        "anywhere in your response.\n"
        "Never quote text in square brackets like [OTP], [REDACTED_CODE], or [REDACTED_CNIC]. "
        "These are internal redaction markers, not real content. "
        "Say 'a verification code' or 'a private code' instead.\n"
        "Never tell the user to share a photo or upload an image.\n"
        "Never run scam detection on casual conversational messages.\n"
        "Always respond in English only, even if the screen contains Urdu or "
        "the user writes in Urdu. Never respond in Urdu or Roman Urdu.\n"
        "Keep responses under 60 words.\n"
        "Plain text only, no markdown.\n"
        "If you genuinely do not know something, say so honestly.\n"
    )

# NOTE for Kaneeza: the "Looking into this for you" loading text was removed
# from OverlayService.kt.  Loading text is controlled on the Android side only.

_CHAT_FALLBACK = FinalDecision(
    response_text=(
        "I could not reach my knowledge just now. "
        "Please try your question again in a moment."
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[],
    source_citations=[],
)

_CHAT_CONTENT_FILTER_FALLBACK = FinalDecision(
    response_text=(
        "I had trouble reading the screen content, but I am still here to help. "
        "Could you tell me in your own words what you see or what you need help with?"
    ),
    risk_flag=RiskLevel.NONE,
    next_steps=[],
    source_citations=[],
)


def _warm_fallback(messages: list[dict] | None, question: str = "") -> FinalDecision:
    """Build a fallback that references what the user actually asked."""
    last_user_msg = question
    if messages:
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
    snippet = last_user_msg[:50].strip() if last_user_msg else "your question"
    return FinalDecision(
        response_text=(
            f"I had trouble reaching my knowledge right now. "
            f"Please try asking again in a moment, "
            f"or tap Emergency if you need urgent help."
        ),
        risk_flag=RiskLevel.NONE,
        next_steps=[],
        source_citations=[],
    )


def handle_chat_question(
    question: str = "",
    screen_context: str = "",
    messages: list[dict] | None = None,
) -> FinalDecision:
    """Answer a user's follow-up question, supporting multi-turn conversation.

    When ``messages`` is provided (a list of {role, content} dicts), the full
    conversation history is passed to the LLM as the messages array — exactly
    like ChatGPT.  The system prompt is prepended automatically.

    When ``messages`` is None, falls back to single-turn mode using ``question``
    (backwards-compatible with existing callers and tests).

    Args:
        question:       Single question (legacy single-turn mode).
        screen_context: Current screen text, embedded in the system prompt.
        messages:       Full conversation history [{role, content}, ...].

    Returns:
        FinalDecision with the answer as response_text and risk_flag=none.
    """
    if messages is not None:
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
        if last_user_msg:
            auth_answer = _check_website_authenticity(last_user_msg, screen_context, messages)
            if auth_answer is not None:
                return auth_answer

        system_prompt = _build_system_prompt(screen_context)
        llm_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                llm_messages.append({"role": role, "content": content})

        if len(llm_messages) < 2:
            return _CHAT_FALLBACK

        try:
            response_text = call_llm_chat(llm_messages, max_tokens=2048)
            if not response_text or not response_text.strip():
                return _CHAT_FALLBACK
            return FinalDecision(
                response_text=response_text.strip(),
                risk_flag=RiskLevel.NONE,
                next_steps=[],
                source_citations=[],
            )
        except ContentFilterError:
            logger.warning("Chat content filter tripped, retrying without screen context and truncated history")
            try:
                user_assistant_msgs = [m for m in llm_messages if m["role"] in ("user", "assistant")]
                recent = user_assistant_msgs[-4:] if len(user_assistant_msgs) > 4 else user_assistant_msgs
                retry_messages = [{"role": "system", "content": _build_system_prompt("")}]
                retry_messages.extend(recent)
                response_text = call_llm_chat(retry_messages, max_tokens=2048)
                if response_text and response_text.strip():
                    return FinalDecision(
                        response_text=response_text.strip(),
                        risk_flag=RiskLevel.NONE,
                        next_steps=[],
                        source_citations=[],
                    )
            except Exception as retry_exc:
                logger.warning("Chat retry also failed: %s", retry_exc)
            return _warm_fallback(messages, question)
        except (LLMUnavailableError, Exception) as exc:
            logger.warning("Chat LLM call failed: %s", exc)
            return _warm_fallback(messages, question)

    if not question or not question.strip():
        return _CHAT_FALLBACK

    auth_answer = _check_website_authenticity(question, screen_context)
    if auth_answer is not None:
        return auth_answer

    system_prompt = _build_system_prompt(screen_context)
    try:
        response_text = call_llm(system_prompt, question, max_tokens=2048)
        if not response_text or not response_text.strip():
            return _CHAT_FALLBACK
        return FinalDecision(
            response_text=response_text.strip(),
            risk_flag=RiskLevel.NONE,
            next_steps=[],
            source_citations=[],
        )
    except ContentFilterError:
        logger.warning("Chat content filter tripped (single-turn), retrying without context")
        try:
            response_text = call_llm(_build_system_prompt(""), question, max_tokens=2048)
            if response_text and response_text.strip():
                return FinalDecision(
                    response_text=response_text.strip(),
                    risk_flag=RiskLevel.NONE,
                    next_steps=[],
                    source_citations=[],
                )
        except Exception as retry_exc:
            logger.warning("Chat retry also failed: %s", retry_exc)
        return _warm_fallback(None, question)
    except (LLMUnavailableError, Exception) as exc:
        logger.warning("Chat LLM call failed: %s", exc)
        return _warm_fallback(None, question)
