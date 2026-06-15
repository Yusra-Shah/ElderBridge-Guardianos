"""
Safety Guardrail Agent — highest-authority veto over all outputs and actions.

Responsibility (AI_AGENTS.md §16 | SECURITY_MODEL.md §2, §8):
  The last line of defence.  Blocks any final response or suggested action
  that violates the ElderBridge safety policy, even if every other agent
  approved it.

Hard blocks (non-negotiable, per SECURITY_MODEL.md §2):
  - Sending, reading aloud, storing, or echoing OTPs
  - Storing raw screenshots or call audio
  - Clicking, tapping, or submitting any form element
  - Approving or initiating any payment
  - Guaranteeing eligibility ("you qualify")
  - Providing legal, medical, or financial final decisions
  - Prompt-injection instructions embedded in scanned content

Action allowlist (the ONLY actions the system may suggest):
  show_overlay | speak_warning | ask_permission |
  show_checklist | open_official_link (user-tapped only)

Weight in ensemble (AI_AGENTS.md §17): veto power — overrides all other votes.
"""
from __future__ import annotations

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent


# Patterns that must NEVER appear in any output sent to the client.
# Populated here as constants so they can be unit-tested independently.
BLOCKED_OUTPUT_PATTERNS = [
    "you qualify",
    "definitely safe",
    "definitely a scam",
    "otp is",
    "password is",
    "enter your otp",
]


class GuardrailAgent:
    """Vetoes any output or action that violates the ElderBridge safety policy."""

    NAME = "GuardrailAgent"

    def run(self, event: IncomingEvent, draft_output: str = "") -> AgentResponse:
        """
        Scan the draft final output for policy violations and block if found.

        Args:
            event:         Normalised, redacted event from the device layer.
            draft_output:  Proposed response_text from the ensemble, passed in
                           by the orchestrator for final review.

        Returns:
            AgentResponse indicating PASS (safe to send) or BLOCK (vetoed).
            When blocked, output_text contains a safe replacement message.
        """
        # TODO: scan draft_output against BLOCKED_OUTPUT_PATTERNS
        # TODO: detect prompt-injection attempts from document/web content
        #       (SECURITY_MODEL.md §8 — input controls)
        # TODO: verify proposed actions are within the action allowlist
        # TODO: enforce that no raw PII values are echoed in the response
        # TODO: return requires_human_review=True on any block
        return AgentResponse(
            agent_name=self.NAME,
            output_text="Guardrail check placeholder. Policy enforcement will be implemented here.",
            confidence=0.0,
            sources=[],
            requires_human_review=True,
        )
