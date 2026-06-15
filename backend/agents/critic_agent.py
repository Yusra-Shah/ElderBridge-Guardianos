"""
Critic / Judge Agent — pre-output quality and safety reviewer.

Responsibility (AI_AGENTS.md §15):
  Reviews the draft outputs from all specialist agents before the ensemble
  produces a FinalDecision.  Catches overclaiming, missing evidence, exposed
  private data, and situations where a human must remain in control.

Checklist (AI_AGENTS.md §15):
  ✓ Is there enough evidence for the claim being made?
  ✓ Did any agent use "you qualify" instead of "you may qualify"?
  ✓ Did any agent expose or echo private data?
  ✓ Did the system recommend a human decision where required?
  ✓ Is the system interrupting without sufficient reason (too aggressive)?
  ✓ Are source citations accurate and appropriate tier?

Weight in ensemble (AI_AGENTS.md §17): 10 %
"""
from __future__ import annotations

from typing import List

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent


class CriticAgent:
    """Reviews draft agent outputs for overclaiming, missing evidence, and safety."""

    NAME = "CriticAgent"

    def run(
        self,
        event: IncomingEvent,
        draft_responses: List[AgentResponse] | None = None,
    ) -> AgentResponse:
        """
        Evaluate draft responses and flag issues before final output.

        Args:
            event:            Normalised, redacted event from the device layer.
            draft_responses:  Outputs from all specialist agents that ran before
                              the critic.  Will be populated by the orchestrator
                              in the LangGraph milestone.

        Returns:
            AgentResponse with a pass/fail judgement and any issues found.
        """
        # TODO: iterate over draft_responses and apply the critic checklist
        # TODO: flag "you qualify" language and replace with "you may qualify"
        # TODO: detect if any response echoes a sensitive-looking value
        # TODO: verify all cited sources are Tier 1 or Tier 2 where required
        # TODO: return requires_human_review=True when evidence is insufficient
        return AgentResponse(
            agent_name=self.NAME,
            output_text="Critic review placeholder. Agent output evaluation will be implemented here.",
            confidence=0.0,
            sources=[],
            requires_human_review=True,
        )
