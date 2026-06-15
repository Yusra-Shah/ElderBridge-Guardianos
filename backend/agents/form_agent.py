"""
Screen / Form Agent — UI and document field interpreter.

Responsibility (AI_AGENTS.md §7, §8):
  Understands confusing form fields, government portal screens, and scanned
  official letters.  For screen events it parses accessibility text to explain
  what each field means in plain language.  For document events it extracts
  deadlines, required documents, agency contact details, and next-step
  checklists.

Detects:
  - income / household / dependent fields
  - document-upload prompts
  - OTP / password fields (flagged immediately to GuardrailAgent)
  - payment and submit buttons
  - government / healthcare wording
  - deadline language in letters and notices
"""
from __future__ import annotations

from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent


class FormAgent:
    """Explains form fields and extracts key information from documents."""

    NAME = "FormAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Parse screen accessibility text or document content.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with field-by-field explanations (FORM_SCREEN)
            or a document summary with deadline and next steps (DOCUMENT).
        """
        # TODO: classify screen_type from event.redacted_text keywords
        # TODO: extract field labels and map to plain-language explanations
        # TODO: for DOCUMENT events, run deadline extraction and document-type detection
        # TODO: flag OTP / password fields to trigger GuardrailAgent immediately
        mode = "screen analysis" if event.event_type == EventType.FORM_SCREEN else "document analysis"
        return AgentResponse(
            agent_name=self.NAME,
            output_text=f"Form/document {mode} placeholder. Field parsing will be implemented here.",
            confidence=0.0,
            sources=[],
            requires_human_review=True,
        )
