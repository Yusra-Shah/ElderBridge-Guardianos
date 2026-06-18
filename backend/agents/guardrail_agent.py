"""
Safety Guardrail Agent — highest-authority veto over all outputs and actions.

Three-outcome model:
  HARD BLOCK (output_text non-empty, requires_human_review=True):
    AI draft output itself contains a dangerous pattern — echoes an OTP value,
    instructs money transfer, overclaims guaranteed eligibility.
    Calling code must replace response_text with output_text and set STOP_AND_VERIFY.

  SCAM FLAG (output_text empty, requires_human_review=True):
    Incoming event text matches a scam signal — explicit OTP instruction,
    urgency deadline, money transfer with amount.
    Calling code should set STOP_AND_VERIFY but keep the AI explanation.

  PASS (output_text empty, requires_human_review=False):
    No violations detected.  Calling code uses draft/agent output unchanged.
"""
from __future__ import annotations

import re

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent

# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------

# Phrases that must never appear in AI draft output.
# Covers: OTP echoing, money instructions, guaranteed eligibility overclaims.
BLOCKED_OUTPUT_PATTERNS: list[str] = [
    r"\byour\s+otp\s+(is|=)\s*\d",        # echoing an actual OTP value
    r"\botp\s*(is|=|:)\s*\d",              # any OTP value in output
    r"password\s+is\b",                    # echoing a password
    r"\[redacted_otp\]",                   # redacted placeholder leaked to output
    r"send\s+money\s+now",                 # financial action instruction
    r"transfer\s+money\s+now",
    r"transfer\s+the\s+funds",
    r"\bguaranteed\s+(to\s+)?(receive|get|qualify)",  # guarantee overclaim
    r"you\s+are\s+(definitely\s+)?approved",           # approval overclaim
    r"definitely\s+safe",
    r"definitely\s+(a\s+)?scam",
]

# Patterns in incoming event text that indicate a scam or phishing attempt.
# Triggers SCAM FLAG — sets STOP_AND_VERIFY but does NOT replace AI explanation.
SCAM_FLAG_SIGNALS: list[str] = [
    # Explicit OTP / PIN instructions — primary scam vector
    r"enter\s+(your\s+)?otp",
    r"send\s+(your\s+)?otp",
    r"verify\s+with\s+otp",
    r"otp\s*(is|=|:)\s*\d",          # OTP value present in input text (e.g. "OTP is 7823")
    r"enter\s+your\s+pin",
    # Money transfer with explicit amount
    r"transfer\s+(rs\.?|pkr\.?|rs\s|pkr\s)\s*\d",
    r"send\s+(rs\.?|pkr\.?|rs\s|pkr\s)\s*\d",
    # Artificial urgency deadline
    r"expires?\s+in\s+\d+\s*hours?",
    # Click-to-claim with urgency
    r"click\s+here\s+to\s+claim",
]

# ---------------------------------------------------------------------------
# Pre-compiled pattern sets
# ---------------------------------------------------------------------------

_COMPILED_OUTPUT: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in BLOCKED_OUTPUT_PATTERNS
]
_COMPILED_SCAM: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in SCAM_FLAG_SIGNALS
]

# ---------------------------------------------------------------------------
# Response text constants
# ---------------------------------------------------------------------------

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
    """Vetoes dangerous AI output and flags scam inputs before delivery to the user."""

    NAME = "GuardrailAgent"

    # -----------------------------------------------------------------------
    # Check methods — return simple string tokens for clear branching
    # -----------------------------------------------------------------------

    def _check_output(self, text: str) -> str:
        """Return 'BLOCK' if text contains a dangerous AI output pattern, else 'PASS'."""
        for pat in _COMPILED_OUTPUT:
            if pat.search(text):
                return "BLOCK"
        return "PASS"

    def _check_input(self, text: str) -> str:
        """Return 'FLAG' if text contains a scam signal, else 'PASS'.

        Redaction placeholders inserted by the Android RedactionEngine are stripped
        before scanning.  This prevents false positives from field labels like
        '[OTP]' or '[REDACTED_CNIC]' which are safe metadata, not threat signals.
        """
        # Strip generic REDACTED[...] placeholders (e.g. [REDACTED_PHONE])
        clean = re.sub(r'\[REDACTED[^\]]*\]', '', text)
        # Strip known single-token placeholders used by the Android client
        clean = re.sub(r'\[OTP\]|\[PHONE\]|\[EMAIL\]|\[CNIC\]', '', clean)

        for pat in _COMPILED_SCAM:
            if pat.search(clean):
                return "FLAG"
        return "PASS"

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def run(self, event: IncomingEvent, draft_output: str = "") -> AgentResponse:
        """
        Evaluate draft_output and event text for safety violations.

        Calling sequence:
          1. _check_output(draft_output) — if BLOCK, return safe replacement (HARD BLOCK).
          2. _check_input(event.redacted_text) — if FLAG, return empty output with
             requires_human_review=True (SCAM FLAG).
          3. Both clear — return empty output with requires_human_review=False (PASS).

        Args:
            event:        Normalised, redacted event from the device layer.
            draft_output: Proposed response text to scan for dangerous content.

        Returns:
            AgentResponse where:
              output_text non-empty, requires_human_review=True  → HARD BLOCK
              output_text empty,     requires_human_review=True  → SCAM FLAG
              output_text empty,     requires_human_review=False → PASS
        """
        # Step 1 — scan AI draft output for dangerous content
        if self._check_output(draft_output) == "BLOCK":
            return AgentResponse(
                agent_name=self.NAME,
                output_text=_SAFE_REPLACEMENT,
                confidence=1.0,
                sources=[],
                requires_human_review=True,
            )

        # Step 2 — scan incoming event text for scam signals
        if self._check_input(event.redacted_text) == "FLAG":
            return AgentResponse(
                agent_name=self.NAME,
                output_text="",   # empty → caller uses AI explanation unchanged
                confidence=1.0,
                sources=[],
                requires_human_review=True,
            )

        # Step 3 — all clear
        return AgentResponse(
            agent_name=self.NAME,
            output_text="",
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )

    # -----------------------------------------------------------------------
    # Properties consumed by orchestrator and graph nodes
    # -----------------------------------------------------------------------

    @property
    def safe_next_steps(self) -> list[str]:
        """Ordered next steps for HARD BLOCK and SCAM FLAG decisions."""
        return list(_SAFE_NEXT_STEPS)

    @property
    def caution_next_steps(self) -> list[str]:
        """Kept for interface compatibility; CAUTION path removed in this revision."""
        return []
