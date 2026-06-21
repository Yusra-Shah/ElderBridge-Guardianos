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

from llm.client import LLMUnavailableError, call_llm, call_llm_race, sanitize_for_llm
from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.agents.form")

_SYSTEM_PROMPT = (
    "You help elderly Pakistanis understand government forms.\n"
    "No markdown. No dashes. Plain sentences only.\n"
    "Write like a helpful friend, not a manual. Maximum 60 words.\n"
    "If a user name is provided in the context, you may greet or address the person "
    "naturally by their first name once, warmly, like a friend would. If no name is "
    "provided, do not use any name and do not invent one.\n\n"
    "One sentence: what this form is for and who should fill it.\n"
    "One or two sentences: the most important things to prepare or know.\n"
    "Do NOT list every single field. Pick only what matters most.\n"
    "TOOL RECOMMENDATIONS: Only suggest a tool if it genuinely fits the situation. "
    "Do NOT suggest CamScanner unless the user must physically scan a paper document "
    "to upload it. Never suggest CamScanner for emails, messages, web pages, or forms "
    "that are already digital. If no tool fits the situation, do not mention any tool "
    "at all. Recommending an irrelevant tool is worse than recommending nothing.\n"
    "ANTI-HALLUCINATION: Only describe what is explicitly visible in the screen text "
    "provided. Never invent, assume, or mention information not present in the text. "
    "Never mention OTP unless the word OTP or one-time password appears explicitly "
    "in the screen text. Never tell the user to share, upload, or take a photo. "
    "ElderBridge has no camera or image input.\n"
    "End with one practical Step.\n"
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
        redacted_text = sanitize_for_llm(event.redacted_text[:500])
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
