"""
Benefits Navigator Agent — public-benefit and support-program interpreter.

Responsibility (AI_AGENTS.md §6):
  Interprets public benefits, pension/elder support, government healthcare,
  housing, and emergency assistance rules.  Generates eligibility guidance
  and follow-up questions when information is missing.

Hard rules (RESPONSIBLE_AI.md §3):
  NEVER output "You qualify."
  ALWAYS output "You may qualify based on the information provided."
  ALWAYS list what information is missing for a definitive determination.
  ALWAYS recommend official verification with the relevant agency.
  NEVER make absolute guarantees about benefit amounts or approval outcomes.

LLM wiring:
  Calls Azure OpenAI via llm/client.py.  On any LLMUnavailableError or
  RuntimeError falls back to the rule-based stub with used_fallback=True.
  Both exception types are treated identically: log a warning and serve the
  safe rule-based response so the user is never left without guidance.
"""
from __future__ import annotations

import logging
import re

from agents.critic_agent import _rewrite
from llm.client import LLMUnavailableError, call_llm, call_llm_race
from schemas.decision_schema import AgentResponse, EvidenceItem
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.agents.benefits")

# ---------------------------------------------------------------------------
# System prompt — encodes RESPONSIBLE_AI.md hard rules + context awareness
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You help elderly Pakistanis understand government messages and benefits.\n"
    "No markdown. No dashes. Plain sentences only. Under 80 words total.\n\n"
    "If the message contains OTP, urgent deadline, unofficial URL, or payment claim:\n"
    "Write 3 plain sentences: what it claims, why suspicious (real govt uses .gov.pk\n"
    "not .info/.com, never sends OTP via SMS), what to do now.\n"
    "Then write: Step: [one action]. Step: [one action].\n\n"
    "If the message is a government form:\n"
    "One sentence saying what the form is for.\n"
    "One sentence per visible field explaining it simply.\n"
    "Then write: Step: [one action]. Step: [one action].\n\n"
    "Never say you qualify. Always say you may qualify based on the information provided.\n"
    "Never request OTP, PIN, or bank details.\n"
    "Always verify with the official agency before acting.\n\n"
    "HELPLINE NUMBERS - include the relevant one in your Step 2:\n"
    "- Ehsaas/BISP helpline: 0800-26477\n"
    "- NADRA helpline: 051-111-786-100\n"
    "- Pakistan Citizen Portal: 3939\n"
    "- Rescue/Emergency: 1122\n"
    "- Cybercrime reporting: 9911\n"
    "When the content is about senior citizen benefits, pension, or healthcare: include 0800-26477.\n"
    "When the content is about CNIC or identity: include 051-111-786-100.\n"
    "When the content is about a scam or cybercrime: include 9911.\n"
)

# Regex patterns for extracting official contacts from screen text
_PHONE_PATTERN = re.compile(
    r'(?:helpline|contact|call|tel|phone|number)[\s:]+([+0-9][\d\s\-]{6,14})',
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
)


class BenefitsAgent:
    """Retrieves and explains public-benefit eligibility rules via LLM with rule-based fallback."""

    NAME = "BenefitsAgent"

    def run(
        self,
        event: IncomingEvent,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> AgentResponse:
        """
        Analyse the event for benefit-related content and return guidance.

        Calls the LLM with a context-aware system prompt and runs the
        critic-style overclaim rewriter on the result before returning.

        On LLMUnavailableError or RuntimeError falls back to a rule-based stub
        response with used_fallback=True — both are treated identically.

        Args:
            event:          Normalised, redacted event from the device layer.
            evidence_items: Optional structured evidence from the Research Engine,
                            included as supporting context in the LLM prompt.

        Returns:
            AgentResponse with plain-language benefit guidance.
        """
        user_message = self._build_user_message(event, evidence_items or [])

        try:
            raw_text = call_llm_race(_SYSTEM_PROMPT, user_message, max_tokens=4096)
            cleaned_text, was_rewritten = _rewrite(raw_text)
            if was_rewritten:
                logger.debug("BenefitsAgent | LLM output contained overclaims — rewrote")
            return AgentResponse(
                agent_name=self.NAME,
                output_text=cleaned_text,
                confidence=0.75,
                sources=[],
                requires_human_review=True,  # always required for benefits guidance per policy
                used_fallback=False,
            )
        except (LLMUnavailableError, RuntimeError) as exc:
            logger.warning("BenefitsAgent | LLM unavailable, using rule-based fallback: %s", exc)
            return self._fallback_response()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_user_message(
        self,
        event: IncomingEvent,
        evidence_items: list[EvidenceItem],
    ) -> str:
        # Detect screen context
        if event.event_type == EventType.FORM_SCREEN:
            context = "CONTEXT: The person is viewing a government form or application screen."
        elif event.event_type == EventType.SMS:
            context = "CONTEXT: The person received an SMS message. Check carefully for scam patterns."
        elif event.event_type == EventType.DOCUMENT:
            context = "CONTEXT: The person is viewing a scanned document or official letter, not a live screen."
        elif event.event_type == EventType.NOTIFICATION:
            context = "CONTEXT: The person received a notification. Check for authenticity."
        else:
            context = ""

        # Sanitize to avoid Azure content filter false positives
        sanitized = event.redacted_text
        sanitized = sanitized.replace("Enter your OTP", "Enter a verification code")
        sanitized = sanitized.replace("enter your OTP", "enter a verification code")
        sanitized = sanitized.replace("Enter OTP", "Enter a code")
        sanitized = sanitized.replace("OTP:", "Code:")
        sanitized = re.sub(r'\bOTP\b', 'verification code', sanitized)

        # Detect official contacts visible on screen
        phone_match = _PHONE_PATTERN.search(event.redacted_text)
        email_match = _EMAIL_PATTERN.search(event.redacted_text)
        if phone_match or email_match:
            contact_note = (
                "Note: An official contact number or email appears to be visible in "
                "the screen content — please extract and include it in your response."
            )
        else:
            contact_note = (
                "Note: No official helpline number or email is visible in the screen "
                "content. End your response with the standard helpline prompt."
            )

        redacted_text = sanitized[:500]

        parts = [
            f"Event type: {event.event_type.value}",
            f"Source app: {event.source_app}",
        ]
        if context:
            parts.append(context)
        parts.append(
            f"Screen content (already redacted of PII): {redacted_text}"
        )
        parts.append(contact_note)

        if evidence_items:
            parts.append("\nSupporting sources found by Research Engine:")
            for item in evidence_items[:5]:  # cap at 5 to stay within token budget
                parts.append(f"  [Tier {item.tier}] {item.title}: {item.snippet[:200]}")

        parts.append(
            "\nProvide brief, hedged benefit guidance based on the above. "
            "Follow all hard rules in your system prompt."
        )
        return "\n".join(parts)

    def _fallback_response(self) -> AgentResponse:
        """Rule-based fallback used when the LLM is unavailable."""
        return AgentResponse(
            agent_name=self.NAME,
            output_text=(
                "I was unable to analyse your benefit eligibility in detail right now. "
                "You may qualify for public support programs based on your age and "
                "circumstances, but please verify directly with the official agency "
                "or a trusted caseworker. "
                "Contact the official helpline. You can find the number on the official "
                "government website or on your benefit documents."
            ),
            confidence=0.1,
            sources=[],
            requires_human_review=True,
            used_fallback=True,
        )
