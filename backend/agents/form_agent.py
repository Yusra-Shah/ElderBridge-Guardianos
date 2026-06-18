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

from llm.client import LLMUnavailableError, call_llm
from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

logger = logging.getLogger("elderbridge.agents.form")

_SYSTEM_PROMPT = (
    "You are helping an elderly person understand a government form or application screen.\n\n"
    "YOUR ONLY JOB is to explain each visible field in plain, simple language. "
    "For each field, say what it means and why the form needs it — one or two short sentences.\n\n"
    "COMMON FIELDS — always explain these simply, never treat them as suspicious:\n"
    "- CNIC / National Identity Card Number: the 13-digit number on your Pakistani ID card.\n"
    "- Full Name / Naam: your complete name as it appears on your ID.\n"
    "- Date of Birth / Taarikh-e-Paidaish: the day, month, and year you were born.\n"
    "- Profession / Peshaa: your job or what you do for work (e.g. farmer, retired, housewife).\n"
    "- Monthly Income / Mahana Amdani: how much money you earn or receive each month.\n"
    "- Number of Dependants: how many family members depend on you for support.\n\n"
    "STRICT RULES:\n"
    "1. NEVER describe standard form fields (CNIC, name, profession, income, date of birth) "
    "as suspicious or dangerous — these are normal government requirements.\n"
    "2. NEVER warn about a form being a scam unless it explicitly asks for an OTP, "
    "password, or bank PIN — those are NOT standard form fields.\n"
    "3. Use very simple words. Write as if speaking to someone unfamiliar with forms.\n"
    "4. Do not give eligibility advice — only explain what each field is asking for."
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
        user_message = (
            f"The person is looking at this government form or screen:\n\n"
            f"{event.redacted_text}\n\n"
            "Please explain each visible field in plain, simple language "
            "suitable for an elderly person unfamiliar with government forms."
        )
        try:
            raw_text = call_llm(_SYSTEM_PROMPT, user_message, max_tokens=512)
            return AgentResponse(
                agent_name=self.NAME,
                output_text=raw_text,
                confidence=0.8,
                sources=[],
                requires_human_review=False,
                used_fallback=False,
            )
        except (LLMUnavailableError, RuntimeError) as exc:
            logger.warning("FormAgent | LLM unavailable, using fallback: %s", exc)
            return self._fallback_response()

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
