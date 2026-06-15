"""
ElderBridge GuardianOS — Research Intelligence Engine.

Implements the source-tier-based evidence retrieval described in
RESEARCH_ENGINE.md.  This version is fully offline: it keyword-matches
against a static mock source database.

Swapping in a live backend (Tavily, SerpAPI, Qdrant RAG) is a one-file
change: replace the body of `ResearchEngine.search()` with a real API call
while keeping the same `List[EvidenceItem]` return type.

Scoring formula (RESEARCH_ENGINE.md §8):
  tier_score    = (6 - tier) / 5       # Tier 1 → 1.0 … Tier 5 → 0.2
  keyword_score = matched / total       # fraction of query tokens found
  relevance     = 0.6 * tier_score + 0.4 * keyword_score

Ranking:
  Primary   — tier ascending  (lower tier number = higher authority)
  Secondary — relevance_score descending (better keyword match wins ties)

A result is included only if at least one query token matches the source.
Stop-words shorter than 3 characters are excluded from the token set to
prevent common words ("in", "of", "is") from inflating relevance scores.
"""
from __future__ import annotations

import re

from research.mock_sources import MOCK_SOURCES, MockSource
from schemas.decision_schema import EvidenceItem

# Minimum token length to count as a meaningful keyword.
_MIN_TOKEN_LEN = 3

# Scoring weights — must sum to 1.0.
_TIER_WEIGHT = 0.6
_KEYWORD_WEIGHT = 0.4


def _tokenize(text: str) -> frozenset[str]:
    """
    Lowercase, extract alphabetic word tokens, discard short stop-words.

    Returns a frozenset so callers can use fast set intersection.
    """
    return frozenset(
        word
        for word in re.findall(r"[a-z]+", text.lower())
        if len(word) >= _MIN_TOKEN_LEN
    )


def _score(source: MockSource, query_tokens: frozenset[str]) -> float | None:
    """
    Compute relevance_score for a single source against the query tokens.

    Returns None if the source has zero keyword overlap with the query.
    """
    source_text = f"{source.title} {source.content_snippet}"
    source_tokens = _tokenize(source_text)

    matched = query_tokens & source_tokens
    if not matched:
        return None

    keyword_score = len(matched) / len(query_tokens)
    tier_score = (6 - source.tier) / 5
    return round(_TIER_WEIGHT * tier_score + _KEYWORD_WEIGHT * keyword_score, 4)


class ResearchEngine:
    """
    Keyword-based evidence retrieval over the mock source database.

    Designed to be drop-in replaceable with a live API client.
    The public interface (search signature + EvidenceItem return type) must
    remain stable when the implementation is swapped.
    """

    def search(self, query: str, max_results: int = 3) -> list[EvidenceItem]:
        """
        Search the source database for evidence relevant to `query`.

        Algorithm:
          1. Tokenise query into meaningful keywords.
          2. Score every source against the token set.
          3. Discard sources with zero keyword overlap.
          4. Sort by tier ascending, then relevance_score descending.
          5. Return the top max_results items as EvidenceItem objects.

        Args:
            query:       Free-text query (typically event.redacted_text).
            max_results: Maximum number of EvidenceItems to return (default 3).

        Returns:
            List of EvidenceItem, ordered best-first.
            Returns an empty list if no sources match.
        """
        if not query or not query.strip():
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # Score every source; collect (tier, -relevance, source, relevance) for sorting
        candidates: list[tuple[int, float, MockSource, float]] = []
        for src in MOCK_SOURCES:
            score = _score(src, query_tokens)
            if score is not None:
                # Negate relevance so that sort() puts highest relevance first
                candidates.append((src.tier, -score, src, score))

        if not candidates:
            return []

        # Sort: tier ascending, then relevance descending (via negated score)
        candidates.sort(key=lambda x: (x[0], x[1]))

        return [
            EvidenceItem(
                source_id=src.source_id,
                title=src.title,
                tier=src.tier,
                snippet=src.content_snippet,
                relevance_score=rel,
            )
            for _, _, src, rel in candidates[:max_results]
        ]
