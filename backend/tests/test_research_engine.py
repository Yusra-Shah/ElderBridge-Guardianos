"""
Tests for the Research Intelligence Engine and ResearchAgent.

Four test groups:
  1. search() returns results for known benefit keywords
  2. search() returns empty list for a nonsense / no-match query
  3. Results are ordered by tier (best authority first), relevance breaks ties
  4. ResearchAgent sets requires_human_review=True when no tier 1–4 sources found

All tests run fully offline — no external API calls.

Run from the backend/ directory:
    pytest tests/test_research_engine.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from agents.research_agent import ResearchAgent
from research.engine import ResearchEngine
from research.mock_sources import MOCK_SOURCES
from schemas.decision_schema import EvidenceItem, RiskLevel
from schemas.event_schema import EventType, IncomingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_type: EventType,
    redacted_text: str,
    source_app: str = "test.app",
    user_id: str = "usr_research_test",
) -> IncomingEvent:
    return IncomingEvent(
        event_type=event_type,
        source_app=source_app,
        redacted_text=redacted_text,
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )


engine = ResearchEngine()


# ---------------------------------------------------------------------------
# Test Group 1 — search() returns results for known benefit keywords
# ---------------------------------------------------------------------------

class TestSearchReturnsBenefitResults:
    """
    Queries containing words from the mock source dataset should produce
    EvidenceItem results, each with the correct shape and valid field values.
    """

    def test_healthcare_keyword_returns_results(self):
        results = engine.search("senior healthcare benefit eligibility")
        assert len(results) > 0, "Expected at least one result for 'senior healthcare benefit'"

    def test_pension_keyword_returns_results(self):
        results = engine.search("pension documents required application")
        assert len(results) > 0, "Expected at least one result for 'pension documents'"

    def test_scam_keyword_returns_results(self):
        results = engine.search("otp scam suspicious sms fraud")
        assert len(results) > 0, "Expected at least one result for 'otp scam'"

    def test_results_are_evidence_item_instances(self):
        results = engine.search("healthcare senior benefit")
        for item in results:
            assert isinstance(item, EvidenceItem), f"Expected EvidenceItem, got {type(item)}"

    def test_evidence_item_fields_are_populated(self):
        results = engine.search("pension documents required")
        item = results[0]
        assert item.source_id, "source_id must not be empty"
        assert item.title, "title must not be empty"
        assert 1 <= item.tier <= 5, f"tier must be 1–5, got {item.tier}"
        assert item.snippet, "snippet must not be empty"
        assert 0.0 <= item.relevance_score <= 1.0, f"relevance_score out of range: {item.relevance_score}"

    def test_max_results_respected(self):
        """search() must return at most max_results items."""
        results = engine.search("senior healthcare pension benefit support", max_results=2)
        assert len(results) <= 2

    def test_default_max_results_is_three(self):
        """Default max_results=3 means at most 3 items returned."""
        results = engine.search("senior healthcare pension benefit support form income housing")
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# Test Group 2 — search() returns empty list for nonsense queries
# ---------------------------------------------------------------------------

class TestSearchReturnsEmptyForNonsense:
    """
    Queries with no token overlap against any mock source must return
    an empty list, not raise an exception.
    """

    def test_pure_nonsense_returns_empty(self):
        results = engine.search("xyzzy foobar quux blergh zorp")
        assert results == [], f"Expected empty list for nonsense query, got {results}"

    def test_empty_string_returns_empty(self):
        results = engine.search("")
        assert results == []

    def test_whitespace_only_returns_empty(self):
        results = engine.search("   \t\n  ")
        assert results == []

    def test_short_stopwords_only_returns_empty(self):
        """Tokens shorter than 3 chars are filtered — only stop-words in query → no match."""
        results = engine.search("an is to of in")
        assert results == [], "Query of only short stop-words should return empty"

    def test_completely_unrelated_domain_returns_empty(self):
        """Words that appear in no mock source should return empty."""
        results = engine.search("quantum entanglement superconductor lithography")
        assert results == []


# ---------------------------------------------------------------------------
# Test Group 3 — Results are ordered by tier (best authority first)
# ---------------------------------------------------------------------------

class TestResultsOrderedByTier:
    """
    When a query matches sources across multiple tiers, the results must be
    ordered tier-ascending (Tier 1 before Tier 2, Tier 2 before Tier 4, etc.).
    Within the same tier, higher relevance_score comes first.
    """

    def test_tier_one_appears_before_tier_two(self):
        """A broad query matching both Tier 1 and Tier 2 sources must put Tier 1 first."""
        # "healthcare benefit senior eligibility" matches both the Tier 1 official program
        # page and the Tier 2 advisory directory.
        results = engine.search("healthcare benefit senior eligibility")
        assert len(results) >= 2, "Need at least 2 results to check ordering"
        assert results[0].tier <= results[1].tier, (
            f"First result (tier {results[0].tier}) must have tier ≤ "
            f"second result (tier {results[1].tier})"
        )

    def test_all_results_in_non_decreasing_tier_order(self):
        """Every consecutive pair of results must be non-decreasing in tier."""
        results = engine.search("senior healthcare pension benefit program documents")
        for i in range(len(results) - 1):
            assert results[i].tier <= results[i + 1].tier, (
                f"Results not sorted: index {i} has tier {results[i].tier}, "
                f"index {i+1} has tier {results[i+1].tier}"
            )

    def test_relevance_score_higher_for_better_keyword_match(self):
        """
        Between two sources at the same tier, the one with more matching keywords
        should have a higher relevance_score (tested via the scoring formula directly).
        """
        from research.engine import _score, _tokenize
        from research.mock_sources import SRC_HEALTHCARE_ELIGIBILITY, SRC_SCAM_ADVISORY

        # Both are Tier 1. The healthcare query should score higher against the
        # healthcare source than against the scam advisory.
        tokens = _tokenize("senior healthcare eligibility benefit citizens age")
        hc_score = _score(SRC_HEALTHCARE_ELIGIBILITY, tokens)
        scam_score = _score(SRC_SCAM_ADVISORY, tokens)

        # Healthcare eligibility source should score higher for a healthcare query
        assert hc_score is not None
        assert scam_score is not None
        assert hc_score >= scam_score, (
            f"Healthcare source ({hc_score:.4f}) should score >= scam source ({scam_score:.4f}) "
            f"for a healthcare-focused query"
        )

    def test_tier_1_source_score_higher_than_tier_5_for_same_keyword(self):
        """
        Even with the same keyword overlap, a Tier 1 source must outrank a Tier 5 source
        because the tier weight (60%) dominates.
        """
        from research.engine import _score, _tokenize

        # Create a synthetic token set that overlaps with both Tier 1 and Tier 5 sources
        # Using "senior benefit" which appears in multiple tiers
        tokens = _tokenize("senior benefit")

        tier1_src = next(s for s in MOCK_SOURCES if s.tier == 1)
        tier5_src = next(s for s in MOCK_SOURCES if s.tier == 5)

        t1_score = _score(tier1_src, tokens)
        t5_score = _score(tier5_src, tokens)

        if t1_score is not None and t5_score is not None:
            assert t1_score > t5_score, (
                f"Tier 1 source score ({t1_score}) must exceed Tier 5 source score ({t5_score})"
            )


# ---------------------------------------------------------------------------
# Test Group 4 — ResearchAgent flags requires_human_review for untrustworthy results
# ---------------------------------------------------------------------------

class TestResearchAgentHumanReviewEscalation:
    """
    The ResearchAgent must set requires_human_review=True when all evidence
    found is from Tier 5 sources or when no sources are found at all.
    This prevents ElderBridge from presenting unverified social media claims
    as valid guidance.
    """

    def test_no_sources_sets_requires_human_review(self):
        """Completely unresolvable query → requires_human_review=True, confidence=0.0."""
        event = _make_event(
            EventType.SMS,
            redacted_text="completely nonsensical xyzzy foobar quux irrelevant",
        )
        agent = ResearchAgent()
        resp = agent.run(event)

        assert resp.requires_human_review is True, (
            "ResearchAgent must require human review when no sources found"
        )
        assert resp.confidence == 0.0

    def test_only_tier5_sources_sets_requires_human_review(self):
        """
        When only Tier 5 (unverified) sources are returned, the agent must
        still flag requires_human_review=True even though results are non-empty.
        """
        tier5_only = [
            EvidenceItem(
                source_id="src_social_001",
                title="Unverified Social Post",
                tier=5,
                snippet="Viral claim about free senior lottery prize",
                relevance_score=0.2,
            )
        ]
        event = _make_event(EventType.SMS, redacted_text="lottery prize jackpot free")

        with patch.object(ResearchEngine, "search", return_value=tier5_only):
            agent = ResearchAgent()
            resp = agent.run(event)

        assert resp.requires_human_review is True, (
            "Tier 5 only results must trigger requires_human_review=True"
        )

    def test_tier1_source_clears_requires_human_review(self):
        """When a Tier 1 source is found, requires_human_review must be False."""
        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="senior healthcare benefit eligibility age pension documents",
        )
        agent = ResearchAgent()
        resp = agent.run(event)

        assert resp.requires_human_review is False, (
            "Tier 1 source in results should clear requires_human_review"
        )
        assert resp.confidence > 0.0

    def test_evidence_items_attached_to_agent_response(self):
        """AgentResponse.evidence_items must be populated from search results."""
        event = _make_event(
            EventType.DOCUMENT,
            redacted_text="pension documents required identity proof income",
        )
        agent = ResearchAgent()
        resp = agent.run(event)

        assert isinstance(resp.evidence_items, list)
        if resp.evidence_items:
            item = resp.evidence_items[0]
            assert isinstance(item, EvidenceItem)
            assert item.source_id
            assert item.tier in range(1, 6)

    def test_source_ids_match_evidence_items(self):
        """AgentResponse.sources (ids) must match the source_ids in evidence_items."""
        event = _make_event(
            EventType.NOTIFICATION,
            redacted_text="otp scam sms fraud pension benefit",
        )
        agent = ResearchAgent()
        resp = agent.run(event)

        evidence_ids = {item.source_id for item in resp.evidence_items}
        for sid in resp.sources:
            assert sid in evidence_ids, f"Source ID '{sid}' in sources but not in evidence_items"

    def test_pipeline_attaches_evidence_to_final_decision(self):
        """Integration: run_pipeline must propagate evidence_items to source_citations."""
        from orchestrator import run_pipeline

        event = _make_event(
            EventType.FORM_SCREEN,
            redacted_text="annual household income dependants proof address government form",
        )
        decision = run_pipeline(event)

        # source_citations should be a list of EvidenceItem (may be empty for
        # events where ResearchAgent is not in the routing path, but type must be correct)
        assert isinstance(decision.source_citations, list)
        for item in decision.source_citations:
            assert isinstance(item, EvidenceItem), (
                f"source_citations must contain EvidenceItem, got {type(item)}"
            )
