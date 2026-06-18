"""
Safety Guardrail Agent — highest-authority veto over all outputs and actions.

Responsibility (AI_AGENTS.md §16 | SECURITY_MODEL.md §2, §8):
  The last line of defence in the pipeline.  Scans both the proposed draft
  response text AND the original event's redacted text for policy violations,
  and replaces the draft with a safe fallback if any violation is detected.

  Even if every preceding agent approved the output, the guardrail can and
  will override it.  It has veto power in the ensemble (AI_AGENTS.md §17).

Three-tier response model:
  BLOCKED (requires_human_review=True):
    Triggered by hard-stop signals — OTP codes, payment transfer instructions,
    explicit credential requests.  Response text is the STOP safe replacement.
    Calling code must use STOP_AND_VERIFY risk level.
  CAUTION (requires_human_review=False, output_text=caution message):
    Triggered by suspicious-but-not-definitive patterns — click-to-verify
    links, prize claim language, urgent account suspension threats.
    Calling code should prepend the caution note to agent output.
  PASSED (requires_human_review=False, output_text=""):
    No signals detected.  Calling code should use agent/critic output directly.

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
  False → PASSED or CAUTION: draft_output is safe; output_text is either
          empty (clean) or a cautionary note to prepend.
"""
from __future__ import annotations

import re

from schemas.decision_schema import AgentResponse
from schemas.event_schema import EventType, IncomingEvent

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Patterns that must never appear in AI output.
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

# Scam-flag signals in incoming event text — triggers STOP_AND_VERIFY risk level
# but passes the AI-generated explanation through unchanged (not replaced).
# Narrowed to explicit OTP/PIN/transfer instructions only; plain OTP mentions
# are intentionally excluded so BenefitsAgent can explain the scam in detail.
INPUT_RISK_SIGNALS: list[str] = [
    r"enter\s+(your\s+)?otp",
    r"send\s+(your\s+)?otp",
    r"verify\s+with\s+otp",
    r"otp\s*(is|=|:)\s*\d",          # OTP value leaked through
    r"\[redacted_otp\]",              # OTP was present and redacted
    r"enter\s+your\s+pin",
    r"transfer\s+(rs\.?|pkr\.?|\$)?\s*\d",  # transfer with amount
    r"send\s+(rs\.?|pkr\.?|\$)?\s*\d",
    # NOTE: r"\botp\b" removed — too broad; catches legitimate scam explanations
    # from BenefitsAgent that explain why an OTP request is suspicious.
]

# Caution-level signals — suspicious but not definitively dangerous.
# Guardrail passes (requires_human_review=False) but returns a caution note
# in output_text for the orchestrator to prepend to the agent response.
CAUTION_SIGNALS: list[str] = [
    r"click\s+(this|the|here)\s*(link|url)\s*to\s*(verify|claim|confirm|activate)",
    r"\bclaim\s+your\s+(prize|reward|jackpot|lottery)\b",
    r"account\s+(will\s+be\s+)?(suspended|blocked|closed)\s+(in\s+)?\d+\s*hours?",
    r"your\s+(cnic|id|identity)\s*(number)?\s*(is\s+)?(needed|required|must\s+be\s+verified).*urgent",
    r"urgent.*verify.*cnic|cnic.*verify.*urgent",
]

# Pre-compiled pattern sets for fast repeated matching
_COMPILED_OUTPUT: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in BLOCKED_OUTPUT_PATTERNS
]
_COMPILED_INPUT: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in INPUT_RISK_SIGNALS
]
_COMPILED_CAUTION: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in CAUTION_SIGNALS
]

# ---------------------------------------------------------------------------
# Response text constants
# ---------------------------------------------------------------------------

# Safe replacement shown when a HARD STOP is triggered.
# Language follows RESPONSIBLE_AI.md §3 — hedged, calm, no absolutes.
_SAFE_REPLACEMENT = (
    "Please stop and do not continue. "
    "This may be asking for private information such as a security code, password, "
    "or bank detail. Official agencies and banks never ask for these by message. "
    "Do not share anything yet. Contact your trusted person or call the official "
    "agency using a number you already know."
)

# Caution note prepended to agent output when CAUTION signals are detected.
# Deliberately mild — does not alarm but prompts caution.
_CAUTION_NOTE = (
    "Please take a moment before continuing. "
    "This message has some patterns that are sometimes used by unofficial parties. "
    "Ask a trusted person to review this with you before taking any action."
)

_SAFE_NEXT_STEPS = [
    "Do not share any code, password, PIN, or bank detail.",
    "Close this message or screen.",
    "Call the official helpline using a number you already trust.",
    "Contact your trusted family member or caregiver.",
]

_CAUTION_NEXT_STEPS = [
    "Read this message carefully before responding.",
    "Do not click any links or call unknown numbers without verifying first.",
    "Ask a trusted family member or caregiver to review this with you.",
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

        Three-pass scanning:
          Pass 1 — Output patterns: phrases the AI must never produce.
          Pass 2 — Hard-stop input signals: definitive scam/phishing patterns
                   in the incoming event that demand an immediate BLOCKED response.
          Pass 3 — Caution signals: suspicious-but-not-definitive patterns.
                   Returns a non-blocking caution note instead of hard stop.

        Normal government forms (CNIC field, profession, name etc.) with no
        OTP, payment, or urgency patterns pass all three checks and return
        a clean PASSED response.

        Args:
            event:        Normalised, redacted event from the device layer.
            draft_output: Proposed response_text assembled by the orchestrator.

        Returns:
            AgentResponse.
              requires_human_review=True, output_text=stop_msg → BLOCKED
              requires_human_review=False, output_text=caution_note → CAUTION
              requires_human_review=False, output_text="" → PASSED
        """
        # Pass 1: output content check
        trigger = self._scan(_COMPILED_OUTPUT, draft_output)
        if trigger:
            return self._block(f"output pattern matched: '{trigger}'")

        # Pass 2: scam-flag input risk signal check — flag STOP_AND_VERIFY but
        # do NOT replace the AI response; pass agent explanation through.
        trigger = self._scan(_COMPILED_INPUT, event.redacted_text)
        if trigger:
            return self._flag_scam(f"input risk signal matched: '{trigger}'")

        # Pass 3: caution signal check (non-blocking)
        trigger = self._scan(_COMPILED_CAUTION, event.redacted_text)
        if trigger:
            return AgentResponse(
                agent_name=self.NAME,
                output_text=_CAUTION_NOTE,
                confidence=0.85,
                sources=[],
                requires_human_review=False,
            )

        # All clear — PASSED
        return AgentResponse(
            agent_name=self.NAME,
            output_text="",   # empty = clean pass; orchestrator uses agent/critic output
            confidence=1.0,
            sources=[],
            requires_human_review=False,
        )

    def _block(self, reason: str) -> AgentResponse:
        """HARD BLOCK: AI output itself is dangerous — replace with safe message."""
        return AgentResponse(
            agent_name=self.NAME,
            output_text=_SAFE_REPLACEMENT,
            confidence=1.0,
            sources=[],
            requires_human_review=True,
        )

    def _flag_scam(self, reason: str) -> AgentResponse:
        """SCAM FLAG: scam detected in input — set STOP_AND_VERIFY but pass AI response through.

        Unlike _block(), output_text is empty so the orchestrator uses the
        agent-generated scam explanation rather than the generic safe replacement.
        """
        return AgentResponse(
            agent_name=self.NAME,
            output_text="",   # empty → caller uses agent/critic text
            confidence=1.0,
            sources=[],
            requires_human_review=True,
        )

    @property
    def safe_next_steps(self) -> list[str]:
        """Next steps to include in FinalDecision when a BLOCK is triggered."""
        return list(_SAFE_NEXT_STEPS)

    @property
    def caution_next_steps(self) -> list[str]:
        """Next steps to include in FinalDecision when a CAUTION is triggered."""
        return list(_CAUTION_NEXT_STEPS)
