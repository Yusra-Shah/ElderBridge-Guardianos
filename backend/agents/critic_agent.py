"""
Critic / Judge Agent — pre-output quality and safety reviewer.

Responsibility (AI_AGENTS.md §15):
  Reviews the draft outputs from all specialist agents before the guardrail
  and final response assembly.  Its primary job at this milestone is to catch
  and rewrite overclaiming language before it can reach the user.

Overclaim rewrites applied (RESPONSIBLE_AI.md §3):
  "you qualify"        → "you may qualify based on the information provided"
  "you will receive"   → "you may receive"
  "guaranteed"         → "possibly available"
  "confirmed"          → "indicated"
  "this is definitely" → "this may be"
  "you are eligible"   → "you may be eligible"
  "you are approved"   → "you may be approved"

Pipeline position (ARCHITECTURE.md §5, AI_AGENTS.md §2):
  Critic runs AFTER all specialist agents and BEFORE the guardrail.
  Weight in ensemble: 10% (AI_AGENTS.md §17).

requires_human_review semantics on the returned AgentResponse:
  True  → critic found and rewrote at least one overclaim; the orchestrator
          should treat the specialist outputs as lower-confidence.
  False → no issues found; specialist outputs passed the critic check.
"""
from __future__ import annotations

import re
from typing import List

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent

# ---------------------------------------------------------------------------
# Overclaim rewrite rules
# Each tuple is (regex_pattern, replacement_string).
# Applied in order — put more specific patterns first.
# ---------------------------------------------------------------------------

OVERCLAIM_REWRITES: list[tuple[str, str]] = [
    # Eligibility overclaims — RESPONSIBLE_AI.md hard rule
    (r"\byou\s+qualify\b", "you may qualify based on the information provided"),
    (r"\byou\s+are\s+eligible\b", "you may be eligible"),
    (r"\byou\s+are\s+approved\b", "you may be approved"),
    (r"\byou\s+will\s+receive\b", "you may receive"),
    (r"\byou\s+have\s+been\s+approved\b", "you may have been approved"),

    # Safety/certainty overclaims
    (r"\bguaranteed\b", "possibly available"),
    (r"\bconfirmed\b", "indicated"),
    (r"\bdefinitely\b", "possibly"),
    (r"this\s+is\s+definitely", "this may be"),
    (r"\bfor\s+certain\b", "possibly"),
    (r"\bwithout\s+a\s+doubt\b", "based on current information"),
]

_COMPILED_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pat, re.IGNORECASE), replacement)
    for pat, replacement in OVERCLAIM_REWRITES
]


def _rewrite(text: str) -> tuple[str, bool]:
    """
    Apply all overclaim rewrites to `text`.

    Returns:
        (cleaned_text, was_modified) — was_modified is True if any pattern matched.
    """
    modified = False
    for pattern, replacement in _COMPILED_REWRITES:
        new_text, n = pattern.subn(replacement, text)
        if n > 0:
            modified = True
            text = new_text
    return text, modified


class CriticAgent:
    """Reviews draft agent outputs for overclaiming and rewrites unsafe phrasing."""

    NAME = "CriticAgent"

    def run(
        self,
        event: IncomingEvent,
        draft_responses: List[AgentResponse] | None = None,
    ) -> AgentResponse:
        """
        Evaluate all specialist agent outputs and rewrite overclaiming phrases.

        Each AgentResponse in draft_responses is scanned individually.  The
        cleaned texts are joined into a single output_text that represents the
        critic-reviewed summary of all specialist outputs.

        If the draft_responses list is empty or None the critic returns a neutral
        pass-through with requires_human_review=False.

        Args:
            event:            Normalised, redacted event from the device layer.
            draft_responses:  All AgentResponse objects from specialist agents.

        Returns:
            AgentResponse where:
              output_text            = combined, overclaim-free specialist text
              requires_human_review  = True if any rewrites were applied
              confidence             = 0.9 (clean) or 0.6 (rewrites applied)
        """
        if not draft_responses:
            return AgentResponse(
                agent_name=self.NAME,
                output_text="No specialist outputs to review.",
                confidence=1.0,
                sources=[],
                requires_human_review=False,
            )

        cleaned_parts: list[str] = []
        any_rewritten = False
        all_sources: list[str] = []

        for resp in draft_responses:
            cleaned_text, was_rewritten = _rewrite(resp.output_text)
            if was_rewritten:
                any_rewritten = True
            cleaned_parts.append(cleaned_text)
            all_sources.extend(resp.sources)

        combined = " | ".join(cleaned_parts)

        return AgentResponse(
            agent_name=self.NAME,
            output_text=combined,
            confidence=0.6 if any_rewritten else 0.9,
            sources=list(dict.fromkeys(all_sources)),  # deduplicate, preserve order
            requires_human_review=any_rewritten,
        )
