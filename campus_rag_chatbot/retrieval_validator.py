"""
Retrieval Validator - Phase 17A
===============================
Implements hybrid retrieval and grounding validation for document queries.

This module addresses semantic neighbor confusion by:
1. Combining vector similarity with BM25 keyword matching
2. Enforcing query term presence in retrieved chunks
3. Validating grounding before answer generation

Example problem this solves:
- Query: "Dean's Lister requirements"
- Without this: Returns "Team Leadership Award" content (semantic neighbor)
- With this: Returns actual Dean's Lister section OR refuses gracefully
"""

import re
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

from text_normalizer import normalize_text

logger = logging.getLogger(__name__)

# Stopwords to filter from query terms
# These are common words that don't help identify the specific topic
STOPWORDS = {
    # Articles and determiners
    'the', 'a', 'an', 'this', 'that', 'these', 'those',
    # Question words
    'what', 'where', 'when', 'how', 'who', 'which', 'why',
    # Verbs
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'do', 'does', 'did', 'done',
    'have', 'has', 'had', 'having',
    'can', 'could', 'will', 'would', 'should', 'may', 'might', 'must',
    'get', 'got', 'getting',
    # Pronouns
    'i', 'you', 'we', 'they', 'it', 'he', 'she', 'me', 'my', 'your', 'our',
    # Prepositions
    'for', 'to', 'of', 'in', 'on', 'at', 'by', 'with', 'about', 'from',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    # Conjunctions
    'and', 'or', 'but', 'if', 'then', 'so', 'as', 'because', 'while',
    # Common question phrases
    'tell', 'know', 'find', 'need', 'want', 'please', 'help',
    # Command/enumeration words (Phase 17C: don't penalize keyword scoring)
    'list', 'show', 'give', 'name', 'all', 'every', 'each',
    # Campus-specific common words (still want to extract the subject)
    'campus', 'school', 'college', 'university',
}

# Minimum term length to consider meaningful
MIN_TERM_LENGTH = 2


@dataclass
class GroundingResult:
    """Result of grounding validation check."""
    is_grounded: bool
    topic: str
    matched_terms: List[str]
    reason: str

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "is_grounded": self.is_grounded,
            "topic": self.topic,
            "matched_terms": self.matched_terms,
            "reason": self.reason
        }


@dataclass
class HybridScore:
    """Holds hybrid scoring details for a chunk."""
    hybrid_score: float
    vector_score: float
    keyword_score: float


def extract_query_terms(query: str) -> List[str]:
    """
    Extract meaningful terms from user query.

    Filters stopwords and short terms, preserving important keywords
    that should appear in relevant document chunks.

    Args:
        query: User's input query

    Returns:
        List of meaningful terms (lowercase, deduplicated)

    Examples:
        >>> extract_query_terms("What are the Dean's Lister requirements?")
        ['dean', 'lister', 'requirements']
        >>> extract_query_terms("Tell me about student scholarships")
        ['student', 'scholarships']
    """
    if not query:
        return []

    # Normalize the query first
    normalized = normalize_text(query)

    # Split on whitespace and punctuation (preserve apostrophe-connected words)
    # Handle cases like "Dean's" -> "dean" and "deans"
    tokens = re.split(r'[\s\-\",.?!:;()\[\]]+', normalized)

    # Also handle apostrophes by splitting them
    expanded_tokens = []
    for token in tokens:
        if "'" in token:
            # "dean's" -> ["dean", "s"] -> keep "dean"
            parts = token.split("'")
            expanded_tokens.extend(p for p in parts if len(p) >= MIN_TERM_LENGTH)
        else:
            expanded_tokens.append(token)

    # Filter and deduplicate
    seen = set()
    terms = []
    for token in expanded_tokens:
        token = token.strip()
        if (len(token) >= MIN_TERM_LENGTH and
            token not in STOPWORDS and
            token not in seen and
            not token.isdigit()):
            terms.append(token)
            seen.add(token)

    logger.debug(f"Extracted query terms: {terms} from '{query}'")
    return terms


def compute_keyword_scores(
    query_terms: List[str],
    documents: List,  # LangChain Document objects
    weight_exact: float = 2.0
) -> List[float]:
    """
    Compute keyword matching scores for retrieved documents.

    Uses term coverage scoring (what fraction of query terms appear in each doc)
    combined with term frequency weighting. This avoids BM25's IDF penalty
    that hurts scores when multiple retrieved chunks contain the same terms.

    Args:
        query_terms: Meaningful terms extracted from query
        documents: List of LangChain Document objects
        weight_exact: Bonus multiplier for exact term matches

    Returns:
        List of keyword scores (0-1 range) for each document
    """
    if not query_terms or not documents:
        return [0.0] * len(documents)

    final_scores = []
    num_terms = len(query_terms)

    for doc in documents:
        content = doc.page_content.lower()

        # Count term matches (coverage score)
        matched_terms = 0
        total_occurrences = 0

        for term in query_terms:
            # Use regex for proper word boundary matching
            # Handle both singular and plural forms: "deans" matches "dean", "dean" matches "deans"
            stem = term.rstrip('s') if term.endswith('s') and len(term) > 3 else term
            pattern = r'\b' + re.escape(stem) + r's?\b'
            matches = re.findall(pattern, content)
            if matches:
                matched_terms += 1
                total_occurrences += len(matches)

        # Base score: fraction of query terms found (0-1)
        coverage_score = matched_terms / num_terms if num_terms > 0 else 0.0

        # Frequency bonus: small boost for multiple occurrences (capped at 0.2)
        frequency_bonus = min(total_occurrences * 0.05, 0.2)

        # Combined score
        final_score = min(coverage_score + frequency_bonus, 1.0)
        final_scores.append(final_score)

    logger.debug(f"Keyword scores: {final_scores}")
    return final_scores


def combine_hybrid_scores(
    retrieval_results: List[Tuple],  # [(doc, vector_score), ...]
    keyword_scores: List[float],
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> Tuple[List[Tuple], List[HybridScore]]:
    """
    Combine vector and keyword scores with configurable weighting.

    Returns re-ranked results by hybrid score.

    Args:
        retrieval_results: List of (document, vector_score) tuples
        keyword_scores: Keyword scores for each document
        vector_weight: Weight for vector similarity (default 0.7)
        keyword_weight: Weight for keyword score (default 0.3)

    Returns:
        Tuple of:
        - Re-ranked results as [(doc, hybrid_score), ...]
        - Detailed scoring info as [HybridScore, ...]
    """
    if not retrieval_results:
        return [], []

    hybrid_results = []
    score_details = []

    for i, (doc, vector_score) in enumerate(retrieval_results):
        kw_score = keyword_scores[i] if i < len(keyword_scores) else 0.0
        hybrid_score = (vector_weight * vector_score) + (keyword_weight * kw_score)

        hybrid_results.append((doc, hybrid_score, vector_score, kw_score))
        score_details.append(HybridScore(
            hybrid_score=hybrid_score,
            vector_score=vector_score,
            keyword_score=kw_score
        ))

    # Sort by hybrid score (descending)
    sorted_indices = sorted(range(len(hybrid_results)),
                           key=lambda i: hybrid_results[i][1],
                           reverse=True)

    # Reorder both lists
    sorted_results = [(hybrid_results[i][0], hybrid_results[i][1]) for i in sorted_indices]
    sorted_details = [score_details[i] for i in sorted_indices]

    logger.debug(f"Hybrid scores after re-ranking: {[d.hybrid_score for d in sorted_details]}")
    return sorted_results, sorted_details


def validate_grounding(
    query_terms: List[str],
    retrieval_results: List[Tuple],  # [(doc, score), ...]
    min_term_matches: int = 1,
    check_top_k: int = 4
) -> GroundingResult:
    """
    Validate that retrieved chunks are grounded in the query topic.

    Requires at least one query term to appear in top chunks.
    This prevents answering from semantically similar but incorrect sections.

    Args:
        query_terms: Meaningful terms from user query
        retrieval_results: List of (document, score) tuples
        min_term_matches: Minimum number of terms required (default 1)
        check_top_k: Number of top chunks to check (default 4)

    Returns:
        GroundingResult with grounding status and details
    """
    # Handle edge cases
    if not query_terms:
        return GroundingResult(
            is_grounded=True,  # Can't validate without terms
            topic="",
            matched_terms=[],
            reason="no_terms_extracted"
        )

    if not retrieval_results:
        return GroundingResult(
            is_grounded=False,
            topic=" ".join(query_terms[:3]),
            matched_terms=[],
            reason="no_chunks_retrieved"
        )

    # Check top chunks for query term presence
    matched_terms = set()
    chunks_checked = min(check_top_k, len(retrieval_results))

    for doc, score in retrieval_results[:chunks_checked]:
        content = f" {doc.page_content.lower()} "  # Pad for word boundaries
        # Phase 18: Also check section_title metadata for grounding
        section_title = doc.metadata.get('section_title', '') if hasattr(doc, 'metadata') else ''
        if section_title:
            content += f" {section_title.lower()} "

        for term in query_terms:
            # Phase 18: Apply same stemming as keyword scorer for consistency
            stem = term.rstrip('s') if term.endswith('s') and len(term) > 3 else term
            # Check for term/stem presence (with common variations)
            if (f" {term} " in content or
                f" {term}s " in content or  # Plural
                f" {term}'" in content or   # Possessive
                (stem != term and (f" {stem} " in content or
                                   f" {stem}s " in content))):
                matched_terms.add(term)

    is_grounded = len(matched_terms) >= min_term_matches

    # Derive topic from query terms for refusal message
    topic = " ".join(query_terms[:3])  # Use first 3 terms as topic

    result = GroundingResult(
        is_grounded=is_grounded,
        topic=topic,
        matched_terms=list(matched_terms),
        reason="grounded" if is_grounded else "no_term_match"
    )

    if not is_grounded:
        logger.info(f"Grounding validation failed: query terms {query_terms} "
                   f"not found in top {chunks_checked} chunks")

    return result


def get_grounding_refusal_message(topic: str) -> str:
    """
    Generate a user-friendly refusal message when grounding fails.

    Args:
        topic: The topic extracted from query terms

    Returns:
        Formatted refusal message
    """
    if topic:
        return f"I couldn't confidently find information about {topic}. Could you clarify or rephrase your question?"
    else:
        return "I couldn't confidently find relevant information for your question. Could you clarify or rephrase?"
