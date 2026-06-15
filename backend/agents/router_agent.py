"""
Router Agent — dynamic dispatcher for the ElderBridge trust engine.

Responsibility (AI_AGENTS.md §4):
  Receives a normalised IncomingEvent and decides which specialist agents
  should be activated for this particular event, avoiding the cost and
  context pollution of running every agent on every event.

Routing examples:
  SMS / NOTIFICATION  → ResearchAgent, GuardrailAgent
  FORM_SCREEN         → FormAgent, BenefitsAgent, GuardrailAgent
  DOCUMENT            → FormAgent, BenefitsAgent, CriticAgent, GuardrailAgent

This agent does NOT call the LLM directly in this scaffolding phase.
LangGraph orchestration will be wired in a later milestone.
"""
from __future__ import annotations

from typing import List

from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent


class RouterAgent:
    """Decides which specialist agents to invoke for a given event."""

    NAME = "RouterAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Return a routing decision encoded as an AgentResponse.

        The `output_text` field carries a comma-separated list of agent names
        that should run next.  This contract will be replaced by a proper
        LangGraph routing node in the orchestration milestone.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with routing recommendation.
        """
        routing_map: dict[EventType, List[str]] = {
            EventType.SMS: ["ResearchAgent", "GuardrailAgent"],
            EventType.NOTIFICATION: ["ResearchAgent", "GuardrailAgent"],
            EventType.FORM_SCREEN: ["FormAgent", "BenefitsAgent", "GuardrailAgent"],
            EventType.DOCUMENT: ["FormAgent", "BenefitsAgent", "CriticAgent", "GuardrailAgent"],
        }

        agents_to_run = routing_map.get(event.event_type, ["GuardrailAgent"])

        return AgentResponse(
            agent_name=self.NAME,
            output_text=f"Routing to: {', '.join(agents_to_run)}",
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )
