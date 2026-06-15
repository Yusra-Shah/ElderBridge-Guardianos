"""
Router Agent — dynamic dispatcher for the ElderBridge trust engine.

Responsibility (AI_AGENTS.md §4):
  Receives a normalised IncomingEvent and decides which specialist agents
  should be activated for this particular event, avoiding the cost and
  context pollution of running every agent on every event.

Pipeline contract (ARCHITECTURE.md §6):
  Router runs first, before critic and guardrail.  It returns ONLY the
  specialist agents; CriticAgent and GuardrailAgent are always appended by
  the orchestrator and must NOT appear in route() output.

Signal-aware routing rules:
  Any event type:
    + benefit/grant/pension keywords  → also add BenefitsAgent
    + url/link/domain keywords        → also add ResearchAgent

  Base routing by event type:
    SMS / NOTIFICATION  → ResearchAgent           (scam/link verification)
    FORM_SCREEN         → FormAgent, BenefitsAgent
    DOCUMENT            → FormAgent, BenefitsAgent, ResearchAgent
"""
from __future__ import annotations

from typing import List

from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

# ---------------------------------------------------------------------------
# Keyword-based secondary routing signals
# ---------------------------------------------------------------------------

_BENEFIT_SIGNALS = [
    "benefit", "grant", "pension", "healthcare", "welfare",
    "allowance", "subsidy", "support program", "eligib",
]

_RESEARCH_SIGNALS = [
    "http", ".com", ".org", ".info", ".net", "link", "website",
    "click", "tap here", "verify", "official", "government",
]

_SCAM_ESCALATION_SIGNALS = [
    "otp", "[redacted_otp]", "password", "cnic", "[redacted_cnic]",
    "transfer", "send money", "urgent", "immediately", "expire",
    "suspended", "blocked", "arrest", "threat",
]


class RouterAgent:
    """Decides which specialist agents to invoke for a given event."""

    NAME = "RouterAgent"

    # Base specialist agents by event type (critic + guardrail added by orchestrator)
    _BASE_ROUTING: dict[EventType, List[str]] = {
        EventType.SMS: ["ResearchAgent"],
        EventType.NOTIFICATION: ["ResearchAgent"],
        EventType.FORM_SCREEN: ["FormAgent", "BenefitsAgent"],
        EventType.DOCUMENT: ["FormAgent", "BenefitsAgent", "ResearchAgent"],
    }

    def route(self, event: IncomingEvent) -> List[str]:
        """
        Return the ordered list of specialist agent names to invoke.

        CriticAgent and GuardrailAgent are NOT included here; the orchestrator
        always appends them at the end of the pipeline.

        Signal-aware secondary routing adds agents based on keywords found
        in the event's redacted text, regardless of event type.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            Ordered list of specialist agent name strings.
        """
        agents: list[str] = list(self._BASE_ROUTING.get(event.event_type, ["ResearchAgent"]))
        text_lower = event.redacted_text.lower()

        # Add BenefitsAgent if benefit-related content is found and not already listed
        if "BenefitsAgent" not in agents:
            if any(sig in text_lower for sig in _BENEFIT_SIGNALS):
                agents.append("BenefitsAgent")

        # Add ResearchAgent if URLs/links are found and not already listed
        if "ResearchAgent" not in agents:
            if any(sig in text_lower for sig in _RESEARCH_SIGNALS):
                agents.append("ResearchAgent")

        # Escalate to include ResearchAgent for high-risk scam signals on SMS/NOTIFICATION
        if event.event_type in (EventType.SMS, EventType.NOTIFICATION):
            if any(sig in text_lower for sig in _SCAM_ESCALATION_SIGNALS):
                if "BenefitsAgent" not in agents:
                    agents.append("BenefitsAgent")

        return agents

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Convenience wrapper: runs route() and packages the result as an AgentResponse.

        The orchestrator calls route() directly for the agent list; this method
        exists so RouterAgent conforms to the same run() interface as all other agents
        and can be logged uniformly.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse whose output_text lists the chosen specialist agents.
        """
        agents_to_run = self.route(event)
        return AgentResponse(
            agent_name=self.NAME,
            output_text=f"Routing to specialists: {', '.join(agents_to_run)}",
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )
