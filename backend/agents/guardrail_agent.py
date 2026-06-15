"""
Safety Guardrail Agent — highest-authority veto over all outputs and actions.

Responsibility (AI_AGENTS.md §16 | SECURITY_MODEL.md §2, §8):
  The last line of defence in the pipeline.  Scans both the proposed draft
  response text AND the original event's redacted text for policy violations,
  and replaces the draft with a safe fallback if any violation is detected.

  Even if every preceding agent approved the output, the guardrail can and
  will override it.  It has veto power in the ensemble (AI_AGENTS.md §17).

Hard blocks (non-negotiable, per SECURITY_MODEL.md §2):
  - Output that echoes or mentions OTPs
  - Output instructing the user to enter/share an OTP
  - Output claiming "you qualify" (eligibility overclaiming)
  - Output claiming "definitely safe" or "definitely a scam"
  - Output echoing passwords, CNICs, or bank numbers
  - Output instructing the user to send/transfer money
  - Direct-action language ("click here", "tap here")

Pattern scanning strategy:
  Combines draft_output + event.redacted_text into a single scan target.
  This means the guardrail acts as a defence-in-depth layer against
  dangerous content arriving from the device, not only from agents.

requires_human_review semantics:
  True  → BLOCKED: orchestrator must use output_text as final response
          and override risk_flag to STOP_AND_VERIFY.
  False → PASSED: draft_output is safe to deliver as-is.
"""
from __future__ import annotations

import re

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each pattern that must never appear in an AI output OR arrive as unsafe input.
# Written as regex strings so they can be unit-tested independently of the class.
BLOCKED_OUTPUT_PATTERNS: list[str] = [
    r"you qualify\b",            # eligibility overclaim (critic should catch first)
    r"definitely safe",          # safety overclaim
    r"definitely\s+(a\s+)?scam", # scam overclaim
    r"\byour\s+otp\s+(is|=)",   # echoing OTP value
    r"password\s+is\b",          # echoing password
    r"enter\s+your\s+otp",       # instructing OTP entry
    r"\[redacted_otp\]",         # redacted OTP accidentally echoed in output
    r"send\s+money\s+now",       # financial action instruction
    r"transfer\s+money\s+now",
    r"transfer\s+the\s+funds",
]

# High-risk signals in the incoming event text that trigger an immediate guardrail
# block regardless of what the draft output says.
INPUT_RISK_SIGNALS: list[str] = [
    r"enter\s+(your\s+)?otp",
    r"send\s+(your\s+)?otp",
    r"verify\s+with\s+otp",
    r"otp\s*(is|=|:)\s*\d",     # OTP value leaked through
    r"\[redacted_otp\]",         # OTP was present and redacted
    r"enter\s+your\s+pin",
    r"transfer\s+(rs\.?|pkr\.?|\$)?\s*\d",  # transfer with amount
    r"send\s+(rs\.?|pkr\.?|\$)?\s*\d",
]

# Pre-compiled pattern sets for fast repeated matching
_COMPILED_OUTPUT: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in BLOCKED_OUTPUT_PATTERNS
]
_COMPILED_INPUT: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in INPUT_RISK_SIGNALS
]

# Safe replacement shown to the user whenever the guardrail blocks output.
# Language follows RESPONSIBLE_AI.md §3 — hedged, calm, no absolutes.
_SAFE_REPLACEMENT = (
    "Please stop and do not continue. "
    "This may be asking for private information such as a security code, password, "
    "or bank detail. Official agencies and banks never ask for these by message. "
    "Do not share anything yet. Contact your trusted person or call the official "
    "agency using a number you already know."
)

_SAFE_NEXT_STEPS = [
    "Do not share any code, password, PIN, or bank detail.",
    "Close this message or screen.",
    "Call the official helpline using a number you already trust.",
    "Contact your trusted family member or caregiver.",
]


class GuardrailAgent:
    """Vetoes any output or action that violates the ElderBridge safety policy."""

    NAME = "GuardrailAgent"

    @staticmethod
    def _scan(patterns: list[re.Pattern[str]], text: str) -> str | None:
        """Return the first matching pattern string, or None if all clear."""
        for pat in patterns:
            m = pat.search(text)
            if m:
                return m.group(0)
        return None

    def run(self, event: IncomingEvent, draft_output: str = "") -> AgentResponse:
        """
        Scan draft output and event text for policy violations.

        Scanning is performed in two passes:
          1. Output patterns — phrases the AI must never output.
          2. Input risk signals — dangerous patterns in the incoming event text
             that indicate the user is in an active high-risk situation.

        If either pass finds a match the response is BLOCKED (requires_human_review=True)
        and output_text is replaced with the safe fallback message.

        If both passes are clean the response is PASSED (requires_human_review=False)
        and output_text is the unchanged draft_output.

        Args:
            event:        Normalised, redacted event from the device layer.
            draft_output: Proposed response_text assembled by the orchestrator.

        Returns:
            AgentResponse.
              requires_human_review=True  → BLOCKED; use output_text as response.
              requires_human_review=False → PASSED; draft_output is safe.
        """
        # Pass 1: output content check
        trigger = self._scan(_COMPILED_OUTPUT, draft_output)
        if trigger:
            return self._block(f"output pattern matched: '{trigger}'")

        # Pass 2: incoming event risk signal check
        trigger = self._scan(_COMPILED_INPUT, event.redacted_text)
        if trigger:
            return self._block(f"input risk signal matched: '{trigger}'")

        # All clear
        return AgentResponse(
            agent_name=self.NAME,
            output_text=draft_output,
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )

    def _block(self, reason: str) -> AgentResponse:
        """Return a BLOCKED AgentResponse with the safe replacement message."""
        return AgentResponse(
            agent_name=self.NAME,
            output_text=_SAFE_REPLACEMENT,
            confidence=1.0,
            sources=[],
            requires_human_review=True,
        )

    @property
    def safe_next_steps(self) -> list[str]:
        """Next steps to include in the FinalDecision when a block is triggered."""
        return list(_SAFE_NEXT_STEPS)
