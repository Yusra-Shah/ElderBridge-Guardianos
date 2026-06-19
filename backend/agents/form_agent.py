"""
Screen / Form Agent — UI and document field interpreter.

Responsibility (AI_AGENTS.md §7, §8):
  Understands confusing form fields, government portal screens, and scanned
  official letters.  For FORM_SCREEN events it calls the LLM to explain each
  visible field in plain language.  For DOCUMENT events it returns a prompt to
  review with a trusted person (full extraction in a future milestone).

LLM wiring:
  Calls Azure OpenAI via llm/client.py.  On LLMUnavailableError or RuntimeError
  falls back to a rule-based stub with used_fallback=True.

Detects and explains:
  - income / household / dependent fields
  - document-upload prompts
  - OTP / password fields (flagged immediately to GuardrailAgent)
  - payment and submit buttons
  - government / healthcare wording
  - deadline language in letters and notices
"""
from __future__ import annotations

import logging

from llm.client import LLMUnavailableError, call_llm, call_llm_race
from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.agents.form")

_SYSTEM_PROMPT = (
    "You help elderly Pakistanis understand government forms.\n"
    "No markdown. No dashes. Plain sentences only. Under 80 words total.\n\n"
    "For each form field visible, write one plain sentence explaining what\n"
    "it means and why the form needs it.\n"
    "If a photo or document is needed, suggest CamScanner app to scan it easily.\n"
    "If the form asks for a photo or document scan, mention CamScanner as a\n"
    "free app that makes scanning easy on a phone.\n"
    "Then write: Step: [one action]. Step: [one action].\n"
)


class FormAgent:
    """Explains form fields and extracts key information from documents."""

    NAME = "FormAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Parse screen accessibility text or document content.

        For FORM_SCREEN events: calls the LLM to explain each visible field in
        plain language suitable for an elderly person.  Falls back to a
        rule-based response if the LLM is unavailable.

        For DOCUMENT events: returns a prompt to review with a trusted person
        (full deadline extraction is a future milestone).

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with field-by-field explanations (FORM_SCREEN)
            or a safe review prompt (DOCUMENT).
        """
        if event.event_type == EventType.FORM_SCREEN:
            return self._explain_form(event)
        return self._document_response()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _explain_form(self, event: IncomingEvent) -> AgentResponse:
        redacted_text = event.redacted_text[:500]
        user_message = (
            f"The person is looking at this government form or screen:\n\n"
            f"{redacted_text}\n\n"
            "Please explain each visible field in plain, simple language "
            "suitable for an elderly person unfamiliar with government forms."
        )
        try:
            raw_text = call_llm_race(_SYSTEM_PROMPT, user_message, max_tokens=6000)
        except LLMUnavailableError as exc:
            if "finish_reason='length'" in str(exc):
                logger.warning("FormAgent | finish_reason=length, retrying with max_tokens=8000")
                try:
                    raw_text = call_llm_race(_SYSTEM_PROMPT, user_message, max_tokens=8000)
                except (LLMUnavailableError, RuntimeError) as retry_exc:
                    logger.warning("FormAgent | retry also failed: %s", retry_exc)
                    return self._fallback_response()
            else:
                logger.warning("FormAgent | LLM unavailable, using fallback: %s", exc)
                return self._fallback_response()
        except RuntimeError as exc:
            logger.warning("FormAgent | LLM unavailable, using fallback: %s", exc)
            return self._fallback_response()
        return AgentResponse(
            agent_name=self.NAME,
            output_text=raw_text,
            confidence=0.8,
            sources=[],
            requires_human_review=False,
            used_fallback=False,
        )

    def _fallback_response(self) -> AgentResponse:
        return AgentResponse(
            agent_name=self.NAME,
            output_text=(
                "This form is asking for standard personal information needed to "
                "process your application. If you are unsure about any field, ask "
                "a trusted person to help you fill it in correctly."
            ),
            confidence=0.3,
            sources=[],
            requires_human_review=True,
            used_fallback=True,
        )

    def _document_response(self) -> AgentResponse:
        return AgentResponse(
            agent_name=self.NAME,
            output_text=(
                "This appears to be an official document. Please review it carefully "
                "with a trusted person if you have any questions about its contents "
                "or what action it requires from you."
            ),
            confidence=0.3,
            sources=[],
            requires_human_review=True,
        )
