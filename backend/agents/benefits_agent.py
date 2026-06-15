"""
Benefits Navigator Agent — public-benefit and support-program interpreter.

Responsibility (AI_AGENTS.md §6):
  Interprets public benefits, pension/elder support, government healthcare,
  housing, and emergency assistance rules using a curated RAG database of
  official program documents.  It generates eligibility guidance and
  follow-up questions when information is missing.

Hard rule (RESPONSIBLE_AI.md §3):
  NEVER output "You qualify."
  ALWAYS output "You may qualify based on the information provided."

Tools (not wired in this scaffolding milestone):
  - RAG official program database (Qdrant / Supabase Vector)
  - Eligibility rule parser
  - Follow-up question generator
"""
from __future__ import annotations

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent


class BenefitsAgent:
    """Retrieves and explains public-benefit eligibility rules using RAG."""

    NAME = "BenefitsAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Analyse the event for benefit-related content and return guidance.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with plain-language benefit guidance and
            a list of official source citations.
        """
        # TODO: query RAG database with event.redacted_text
        # TODO: parse eligibility rules for user's age/location/income context
        # TODO: generate missing-information questions when fields are absent
        return AgentResponse(
            agent_name=self.NAME,
            output_text=(
                "Benefits analysis placeholder. "
                "RAG retrieval and eligibility parsing will be implemented here."
            ),
            confidence=0.0,
            sources=[],
            requires_human_review=True,
        )
