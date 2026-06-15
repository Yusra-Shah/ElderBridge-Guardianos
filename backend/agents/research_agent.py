"""
Research Verification Agent — trusted-source evidence engine.

Responsibility (AI_AGENTS.md §5, §10 | RESEARCH_ENGINE.md):
  Checks claims, links, domains, and benefit announcements against a
  tiered source hierarchy before the system produces any high-impact output.
  ElderBridge does NOT answer high-stakes questions from model memory alone;
  it uses evidence retrieved from official or curated sources.

Source tiers (RESEARCH_ENGINE.md §5):
  Tier 1 — Official government / healthcare / bank websites
  Tier 2 — Recognised public-service organisations
  Tier 3 — Reputable news / advisories
  Tier 4 — Community resource directories
  Tier 5 — Unknown domains, forums, social posts

Tools (not wired in this scaffolding milestone):
  - Web search API (Tavily / SerpAPI)       — os.environ["SEARCH_API_KEY"]
  - URL reputation / threat feeds           — os.environ["URL_SAFETY_API_KEY"]
  - RAG vector database                     — os.environ["RAG_DB_URL"]
  - Official-domain allowlist / denylist
"""
from __future__ import annotations

from schemas.decision_schema import AgentResponse
from schemas.event_schema import IncomingEvent


class ResearchAgent:
    """Verifies claims and URLs against trusted official sources."""

    NAME = "ResearchAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Execute research questions against tiered sources and return evidence.

        Produces an evidence graph (RESEARCH_ENGINE.md §7) that feeds the
        ensemble decision engine.  If no official source is found, the output
        text instructs the user NOT to share private information yet.

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with evidence summary, source citations, and a
            research confidence score.
        """
        # TODO: call Research Planner to generate targeted research questions
        # TODO: query RAG database for known program/benefit information
        # TODO: run live web search for current confirmation (Tavily / SerpAPI)
        #       API key: os.environ["SEARCH_API_KEY"]  — never hardcode
        # TODO: run URL intelligence checks (domain age, HTTPS, lookalike, threat feeds)
        #       API key: os.environ["URL_SAFETY_API_KEY"]  — never hardcode
        # TODO: build evidence graph and compute research_confidence score
        return AgentResponse(
            agent_name=self.NAME,
            output_text=(
                "I could not verify this from an official source yet. "
                "Research retrieval will be implemented here."
            ),
            confidence=0.0,
            sources=[],
            requires_human_review=True,
        )
