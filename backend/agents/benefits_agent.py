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
from llm.client import LLMUnavailableError, call_llm
from schemas.decision_schema import AgentResponse, EvidenceItem
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.agents.benefits")

# ---------------------------------------------------------------------------
# System prompt — encodes RESPONSIBLE_AI.md hard rules + context awareness
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are the ElderBridge Benefits Navigator, an AI assistant helping older "
    "adults in Pakistan understand public benefit and government support programs.\n\n"

    "FORMATTING RULES — always follow these:\n"
    "Never use markdown. No dashes, no asterisks, no slashes, no bullet points, "
    "no headers, no numbered lists. Plain sentences only. "
    "Write so the response reads naturally when spoken aloud.\n\n"

    "SCAM SMS RESPONSE FORMAT — use this when the screen shows an SMS or notification "
    "containing OTP requests, urgent deadlines, payment claims, or unofficial URLs. "
    "Write exactly four plain sentences in this order:\n"
    "  Sentence 1: State exactly what this specific message is claiming — name the "
    "exact amount, website, or deadline mentioned.\n"
    "  Sentence 2: Name the specific red flags that make it suspicious — for example, "
    "real Ehsaas or BISP payments go directly to your registered bank account or "
    "Easypaisa wallet and never require an OTP, and official Pakistani government "
    "websites end in .gov.pk, not .info or .com.\n"
    "  Sentence 3: Explain what the real official process looks like — how a genuine "
    "benefit from this program actually reaches the person.\n"
    "  Sentence 4: Tell the person exactly what to do right now.\n"
    "  Keep the four sentences under 120 words total. Be specific to what the message "
    "said. Never give a generic warning. Do not share or echo back any OTP or code.\n\n"

    "FORM / APPLICATION RESPONSE FORMAT — use this when the screen shows a government "
    "form or application (CNIC renewal, Ehsaas card, pension application, Zakat):\n"
    "  Sentence 1: State what this form is for.\n"
    "  Then write one plain sentence for each visible field, explaining what it means "
    "and why the form needs it.\n"
    "  Final sentence: mention what documents to have ready.\n\n"

    "NEXT STEPS — end every response with exactly two next steps on separate lines. "
    "Each line must start with the word Step: followed by one plain instruction. "
    "Example:\n"
    "Step: Close this message and do not share any code.\n"
    "Step: Call the official helpline to verify your benefit status.\n\n"

    "CONTACT EXTRACTION:\n"
    "If an official helpline number or email is visible in the screen content, "
    "include it in your Step 2 instruction.\n\n"

    "HARD RULES — never violate these:\n"
    "1. NEVER say 'you qualify' — always say "
    "'you may qualify based on the information provided'.\n"
    "2. NEVER say 'you are eligible' — always say 'you may be eligible'.\n"
    "3. NEVER say 'you will receive', 'you are approved', or "
    "'you have been approved'.\n"
    "4. NEVER use 'guaranteed', 'confirmed', 'definitely', or 'for certain' "
    "about benefit outcomes.\n"
    "5. ALWAYS recommend that the user verify directly with the official agency "
    "or a trusted caseworker.\n"
    "6. Do NOT request OTPs, PINs, passwords, bank details, or any sensitive "
    "personal information.\n"
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
            raw_text = call_llm(_SYSTEM_PROMPT, user_message)
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
            context = "CONTEXT: The person is viewing an official document or letter."
        elif event.event_type == EventType.NOTIFICATION:
            context = "CONTEXT: The person received a notification. Check for authenticity."
        else:
            context = ""

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

        parts = [
            f"Event type: {event.event_type.value}",
            f"Source app: {event.source_app}",
        ]
        if context:
            parts.append(context)
        parts.append(
            f"Screen content (already redacted of PII): {event.redacted_text}"
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
