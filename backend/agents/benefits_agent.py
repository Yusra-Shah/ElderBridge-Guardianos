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
  Calls the Anthropic API via llm/client.py.  On any LLMUnavailableError or
  RuntimeError falls back to the rule-based stub with used_fallback=True.
  Both exception types are treated identically: log a warning and serve the
  safe rule-based response so the user is never left without guidance.
"""
from __future__ import annotations

import logging

from agents.critic_agent import _rewrite
from llm.client import LLMUnavailableError, call_llm
from schemas.decision_schema import AgentResponse, EvidenceItem
from schemas.event_schema import IncomingEvent

logger = logging.getLogger("elderbridge.agents.benefits")

# ---------------------------------------------------------------------------
# System prompt — encodes RESPONSIBLE_AI.md hard rules for the LLM
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are the ElderBridge Benefits Navigator, an AI assistant helping older "
    "adults understand public benefit and government support programs.\n\n"
    "HARD RULES — never violate these:\n"
    "1. NEVER say 'you qualify' — always say "
    "'you may qualify based on the information provided'.\n"
    "2. NEVER say 'you are eligible' — always say 'you may be eligible'.\n"
    "3. NEVER say 'you will receive', 'you are approved', or "
    "'you have been approved'.\n"
    "4. NEVER use 'guaranteed', 'confirmed', 'definitely', or 'for certain' "
    "about benefit outcomes.\n"
    "5. ALWAYS list what additional information would be needed for a more "
    "precise determination.\n"
    "6. ALWAYS recommend that the user verify directly with the official agency "
    "or a trusted caseworker.\n"
    "7. Keep your response concise (3–6 sentences). Use plain language suitable "
    "for older adults.\n"
    "8. Do NOT request OTPs, PINs, passwords, bank details, or any sensitive "
    "personal information.\n"
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

        Calls the Anthropic LLM with a safety-focused system prompt and runs
        the critic-style overclaim rewriter on the result before returning.

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
            raw_text = call_llm(_SYSTEM_PROMPT, user_message, max_tokens=512)
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
        parts = [
            f"Event type: {event.event_type.value}",
            f"Source app: {event.source_app}",
            f"Screen content (already redacted of PII): {event.redacted_text}",
        ]
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
                "I could not confirm specific program details at this time."
            ),
            confidence=0.1,
            sources=[],
            requires_human_review=True,
            used_fallback=True,
        )
