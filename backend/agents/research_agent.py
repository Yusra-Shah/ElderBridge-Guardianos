"""
Research Verification Agent — trusted-source evidence engine.

Responsibility (AI_AGENTS.md §5, §10 | RESEARCH_ENGINE.md):
  Checks claims, links, domains, and benefit announcements against a
  tiered source hierarchy before the system produces any high-impact output.
  ElderBridge does NOT answer high-stakes questions from model memory alone;
  it retrieves evidence from official or curated sources.

Source tiers (RESEARCH_ENGINE.md §5):
  Tier 1 — Official government / healthcare / bank websites
  Tier 2 — Recognised public-service organisations
  Tier 3 — Reputable news / advisories
  Tier 4 — Community resource directories
  Tier 5 — Unknown domains, forums, social posts

Human review rule:
  If no sources with tier ≤ 4 are returned, the agent cannot provide
  verified guidance and must flag requires_human_review=True.

Tools wired in this milestone:
  - ResearchEngine (offline keyword-matching against mock_sources.py)

Tools NOT yet wired (future milestones):
  - Live web search API (Tavily / SerpAPI)  — os.environ["SEARCH_API_KEY"]
  - URL reputation / threat feeds            — os.environ["URL_SAFETY_API_KEY"]
  - RAG vector database                      — os.environ["RAG_DB_URL"]
"""
from __future__ import annotations

from research.engine import ResearchEngine
from schemas.decision_schema import AgentResponse, EvidenceItem
from schemas.event_schema import IncomingEvent

_engine = ResearchEngine()

# Tier threshold: sources at this tier or below are considered trustworthy
# enough to reduce the human-review requirement.
_TRUSTED_TIER_THRESHOLD = 4


class ResearchAgent:
    """Verifies claims and URLs against trusted official sources."""

    NAME = "ResearchAgent"

    def run(self, event: IncomingEvent) -> AgentResponse:
        """
        Search the source database using the event's redacted text as the query.

        Confidence and human-review flag are derived from the best source tier found:
          Tier 1 → confidence 1.0   (official govt/healthcare source)
          Tier 2 → confidence 0.8
          Tier 3 → confidence 0.6
          Tier 4 → confidence 0.4
          Tier 5 or none → confidence 0.0, requires_human_review=True

        Args:
            event: Normalised, redacted event from the device layer.

        Returns:
            AgentResponse with evidence_items populated from search results
            and sources populated with source_id strings.
        """
        results: list[EvidenceItem] = _engine.search(
            query=event.redacted_text,
            max_results=3,
        )

        # Determine the best (lowest-numbered) tier in the results
        trusted = [r for r in results if r.tier <= _TRUSTED_TIER_THRESHOLD]
        requires_human_review = len(trusted) == 0

        if results:
            best_tier = min(r.tier for r in results)
            # Tier 1 → 1.0, Tier 2 → 0.8, ..., Tier 5 → 0.2
            confidence = round((6 - best_tier) / 5, 2)
        else:
            confidence = 0.0

        source_ids = [r.source_id for r in results]

        if not results:
            output_text = (
                "I could not find an official source to verify this query. "
                "Please verify directly with the relevant agency before taking any action."
            )
        elif requires_human_review:
            output_text = (
                "I found sources related to your query, but none from an official or "
                "recognised organisation. Please verify with an official agency directly."
            )
        else:
            source_titles = "; ".join(r.title for r in trusted[:2])
            output_text = (
                f"I found {len(trusted)} verified source(s) related to your query. "
                f"Sources consulted: {source_titles}. "
                "Please verify the details directly before taking any action."
            )

        return AgentResponse(
            agent_name=self.NAME,
            output_text=output_text,
            confidence=confidence,
            sources=source_ids,
            evidence_items=results,
            requires_human_review=requires_human_review,
        )
