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

# Phase 28: Domain-specific synonym dictionary for query expansion
# Format: term -> [synonyms] (bidirectional expansion)
# Keep list small and focused to avoid noise
CAMPUS_SYNONYMS = {
    # Locations - common abbreviations and alternate names
    'library': ['lib'],
    'lib': ['library'],
    'registrar': ['registration'],
    'registration': ['registrar'],
    'cafeteria': ['canteen', 'caf'],
    'canteen': ['cafeteria'],
    'gymnasium': ['gym'],
    'gym': ['gymnasium'],
    'clinic': ['infirmary', 'health'],
    'infirmary': ['clinic'],
    'cashier': ['treasurer', 'payment'],
    'treasurer': ['cashier', 'payment'],
    'restroom': ['cr', 'comfort', 'bathroom', 'toilet'],
    'cr': ['restroom', 'comfort', 'bathroom'],
    'bathroom': ['restroom', 'cr'],
    'toilet': ['restroom', 'cr'],

    # Administrative terms
    'admin': ['administration', 'administrative'],
    'administration': ['admin'],
    'office': ['ofc'],
    'ofc': ['office'],

    # Financial terms
    'tuition': ['payment', 'fees', 'pay'],
    'fees': ['tuition', 'payment'],
    'payment': ['tuition', 'fees', 'cashier'],
    'pay': ['tuition', 'payment'],

    # Academic terms
    'dean': ['deans'],
    'deans': ['dean'],
    'professor': ['prof', 'instructor', 'teacher'],
    'prof': ['professor'],
    'instructor': ['professor', 'teacher'],
    'teacher': ['instructor', 'professor'],
    'student': ['students'],
    'students': ['student'],

    # Document types
    'handbook': ['manual', 'guide'],
    'manual': ['handbook', 'guide'],
    'guide': ['handbook', 'manual'],

    # Schedule terms
    'schedule': ['sched', 'timetable'],
    'sched': ['schedule'],
    'timetable': ['schedule'],

    # Common abbreviations
    'requirements': ['reqs', 'requisites'],
    'reqs': ['requirements'],
    'information': ['info'],
    'info': ['information'],
}

# Phase 28: Enable/disable synonym expansion
ENABLE_SYNONYM_EXPANSION = True

# Phase 20: Semantic grounding thresholds
# Allow grounding bypass for high-confidence long-form content
SEMANTIC_SIMILARITY_THRESHOLD = 0.75  # Min similarity for semantic override
MIN_SEMANTIC_CONTENT_LENGTH = 300     # Min chars for long-form content


@dataclass
class GroundingResult:
    """Result of grounding validation check."""
    is_grounded: bool
    topic: str
    matched_terms: List[str]
    reason: str
    grounding_mode: str = "keyword"  # Phase 20: "keyword" | "semantic"

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "is_grounded": self.is_grounded,
            "topic": self.topic,
            "matched_terms": self.matched_terms,
            "reason": self.reason,
            "grounding_mode": self.grounding_mode  # Phase 20
        }


@dataclass
class HybridScore:
    """Holds hybrid scoring details for a chunk."""
    hybrid_score: float        # Final combined score (normalized 0-1)
    vector_score: float        # Semantic similarity (0-1)
    keyword_score: float       # Term coverage (0-1)
    vector_rank: int = 0       # Phase 26: Rank in vector results (1-indexed)
    keyword_rank: int = 0      # Phase 26: Rank in keyword results (1-indexed)
    scoring_method: str = "linear"  # Phase 26: "linear" or "rrf"


def expand_with_synonyms(terms: List[str]) -> List[str]:
    """
    Phase 28: Expand query terms with domain-specific synonyms.

    Adds synonyms to improve recall while keeping original terms.
    Original terms are kept first for scoring priority.

    Args:
        terms: Base query terms extracted from query

    Returns:
        Expanded list with original terms + their synonyms

    Examples:
        >>> expand_with_synonyms(['library', 'hours'])
        ['library', 'hours', 'lib']
        >>> expand_with_synonyms(['tuition', 'payment'])
        ['tuition', 'payment', 'fees', 'pay', 'cashier']
    """
    if not ENABLE_SYNONYM_EXPANSION:
        return terms

    expanded = list(terms)  # Keep originals first
    seen = set(terms)

    for term in terms:
        if term in CAMPUS_SYNONYMS:
            for synonym in CAMPUS_SYNONYMS[term]:
                if synonym not in seen:
                    expanded.append(synonym)
                    seen.add(synonym)

    if len(expanded) > len(terms):
        logger.debug(f"[PHASE28] Expanded terms: {terms} -> {expanded}")

    return expanded


def extract_query_terms(query: str, expand_synonyms: bool = True) -> List[str]:
    """
    Extract meaningful terms from user query.

    Filters stopwords and short terms, preserving important keywords
    that should appear in relevant document chunks.

    Args:
        query: User's input query
        expand_synonyms: Whether to expand with domain synonyms (Phase 28)

    Returns:
        List of meaningful terms (lowercase, deduplicated)

    Examples:
        >>> extract_query_terms("What are the Dean's Lister requirements?")
        ['dean', 'lister', 'requirements', 'deans', 'reqs', 'requisites']
        >>> extract_query_terms("Tell me about student scholarships")
        ['student', 'scholarships', 'students']
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

    # Phase 28: Expand with synonyms for better recall
    if expand_synonyms:
        terms = expand_with_synonyms(terms)

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


def compute_rrf_scores(
    retrieval_results: List[Tuple],  # [(doc, vector_score), ...]
    keyword_scores: List[float],
    k: int = 60
) -> List[Tuple[int, float, int, int]]:
    """
    Phase 26: Compute Reciprocal Rank Fusion scores.

    RRF normalizes by rank position rather than score value,
    making it robust to different score distributions.

    Formula: rrf_score = 1/(k + rank_vector) + 1/(k + rank_keyword)

    Args:
        retrieval_results: Vector search results with scores
        keyword_scores: Keyword match scores for each doc
        k: Smoothing constant (default 60, industry standard)

    Returns:
        List of (original_index, rrf_score, vector_rank, keyword_rank)
        sorted by rrf_score descending
    """
    n = len(retrieval_results)
    if n == 0:
        return []

    # Get vector ranks (1-indexed)
    vector_order = sorted(range(n), key=lambda i: retrieval_results[i][1], reverse=True)
    vector_ranks = {idx: rank + 1 for rank, idx in enumerate(vector_order)}

    # Get keyword ranks (1-indexed)
    keyword_order = sorted(range(n), key=lambda i: keyword_scores[i], reverse=True)
    keyword_ranks = {idx: rank + 1 for rank, idx in enumerate(keyword_order)}

    # Compute RRF scores
    rrf_scores = []
    for i in range(n):
        vec_rank = vector_ranks[i]
        kw_rank = keyword_ranks[i]
        rrf = 1.0 / (k + vec_rank) + 1.0 / (k + kw_rank)
        rrf_scores.append((i, rrf, vec_rank, kw_rank))

    # Sort by RRF score (descending)
    rrf_scores.sort(key=lambda x: x[1], reverse=True)
    return rrf_scores


def _normalize_rrf_to_01(rrf_scores: List[Tuple[int, float, int, int]]) -> List[Tuple[int, float, int, int]]:
    """
    Normalize RRF scores to [0, 1] range for compatibility.

    RRF scores are naturally small (e.g., 0.032 for best rank with k=60).
    This normalization maintains ranking while providing compatible scores.
    """
    if not rrf_scores or len(rrf_scores) == 1:
        # Single result gets score of 1.0
        if rrf_scores:
            return [(rrf_scores[0][0], 1.0, rrf_scores[0][2], rrf_scores[0][3])]
        return []

    scores = [s[1] for s in rrf_scores]
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        # All scores equal, give them all 1.0
        return [(s[0], 1.0, s[2], s[3]) for s in rrf_scores]

    # Normalize: (score - min) / (max - min)
    normalized = []
    for orig_idx, score, vec_rank, kw_rank in rrf_scores:
        norm_score = (score - min_score) / (max_score - min_score)
        normalized.append((orig_idx, norm_score, vec_rank, kw_rank))

    return normalized


def combine_hybrid_scores(
    retrieval_results: List[Tuple],  # [(doc, vector_score), ...]
    keyword_scores: List[float],
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    method: str = "linear",  # Phase 26: "linear" or "rrf"
    rrf_k: int = 60
) -> Tuple[List[Tuple], List[HybridScore]]:
    """
    Combine vector and keyword scores with configurable method.

    Returns re-ranked results by hybrid score.

    Methods:
    - "linear": Weighted sum (Phase 17A): 0.7*vector + 0.3*keyword
    - "rrf": Reciprocal Rank Fusion (Phase 26): industry standard

    Args:
        retrieval_results: List of (document, vector_score) tuples
        keyword_scores: Keyword scores for each document
        vector_weight: Weight for vector similarity (linear method only)
        keyword_weight: Weight for keyword score (linear method only)
        method: Scoring method - "linear" or "rrf"
        rrf_k: RRF smoothing constant (rrf method only, default 60)

    Returns:
        Tuple of:
        - Re-ranked results as [(doc, hybrid_score), ...]
        - Detailed scoring info as [HybridScore, ...]
    """
    if not retrieval_results:
        return [], []

    if method == "rrf":
        # Phase 26: RRF scoring
        rrf_results = compute_rrf_scores(retrieval_results, keyword_scores, rrf_k)
        normalized_rrf = _normalize_rrf_to_01(rrf_results)

        sorted_results = []
        sorted_details = []

        for orig_idx, norm_score, vec_rank, kw_rank in normalized_rrf:
            doc, vector_score = retrieval_results[orig_idx]
            kw_score = keyword_scores[orig_idx] if orig_idx < len(keyword_scores) else 0.0

            sorted_results.append((doc, norm_score))
            sorted_details.append(HybridScore(
                hybrid_score=norm_score,
                vector_score=vector_score,
                keyword_score=kw_score,
                vector_rank=vec_rank,
                keyword_rank=kw_rank,
                scoring_method="rrf"
            ))

        logger.debug(f"[PHASE26] RRF scores after re-ranking: {[d.hybrid_score for d in sorted_details]}")
        return sorted_results, sorted_details

    else:
        # Phase 17A: Linear weighted scoring
        hybrid_results = []
        score_details = []

        for i, (doc, vector_score) in enumerate(retrieval_results):
            kw_score = keyword_scores[i] if i < len(keyword_scores) else 0.0
            hybrid_score = (vector_weight * vector_score) + (keyword_weight * kw_score)

            hybrid_results.append((doc, hybrid_score, vector_score, kw_score))
            score_details.append(HybridScore(
                hybrid_score=hybrid_score,
                vector_score=vector_score,
                keyword_score=kw_score,
                vector_rank=0,
                keyword_rank=0,
                scoring_method="linear"
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


def check_semantic_grounding_override(
    retrieval_results: List[Tuple],  # [(doc, score), ...]
    min_similarity: float = SEMANTIC_SIMILARITY_THRESHOLD,
    min_content_length: int = MIN_SEMANTIC_CONTENT_LENGTH
) -> Tuple[bool, dict]:
    """
    Phase 20: Check if semantic grounding override applies.
    
    Override applies when top chunk has:
    - High similarity score (semantic confidence)
    - Sufficient length (substantial long-form content)
    
    This allows answers for hymns, prayers, policies where
    semantic retrieval succeeds but literal keywords don't match.
    
    Note: Expansion (Phase 19) is an implementation detail.
    Grounding is gated by confidence + content size, not neighbor merging.
    
    Args:
        retrieval_results: Ranked (doc, score) tuples
        min_similarity: Minimum similarity threshold (default 0.75)
        min_content_length: Minimum content length (default 300 chars)
    
    Returns:
        (override_applies, metadata_dict)
    """
    if not retrieval_results:
        return False, {}
    
    # Check top chunk
    top_doc, top_score = retrieval_results[0]
    
    # Criterion 1: High similarity (semantic confidence)
    similarity_ok = top_score >= min_similarity
    
    # Criterion 2: Sufficient content length (long-form content)
    content_length = len(top_doc.page_content)
    length_ok = content_length >= min_content_length
    
    # Override applies when BOTH criteria met
    # (removed expanded=True requirement per industry standards)
    override_applies = similarity_ok and length_ok
    
    # Track expansion status for observability (not gating)
    is_expanded = top_doc.metadata.get('expanded', False)
    
    metadata = {
        'top_similarity': round(top_score, 3),
        'content_length': content_length,
        'is_expanded': is_expanded,  # For observability only
        'semantic_override': override_applies,
        'criteria': {
            'similarity_ok': similarity_ok,
            'length_ok': length_ok
        }
    }
    
    if override_applies:
        logger.info(
            f"[PHASE20] Semantic grounding override triggered: "
            f"similarity={top_score:.3f}, length={content_length} chars, "
            f"expanded={is_expanded}"
        )
    
    return override_applies, metadata


def validate_grounding(
    query_terms: List[str],
    retrieval_results: List[Tuple],  # [(doc, score), ...]
    min_term_matches: int = 1,
    check_top_k: int = 4,
    allow_semantic_override: bool = True  # Phase 20
) -> GroundingResult:
    """
    Validate that retrieved chunks are grounded in the query topic.

    Requires at least one query term to appear in top chunks.
    This prevents answering from semantically similar but incorrect sections.
    
    Phase 20: Can bypass keyword validation via semantic override when
    high-confidence long-form content is retrieved.

    Args:
        query_terms: Meaningful terms from user query
        retrieval_results: List of (document, score) tuples
        min_term_matches: Minimum number of terms required (default 1)
        check_top_k: Number of top chunks to check (default 4)
        allow_semantic_override: Enable Phase 20 semantic grounding (default True)

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
    
    # Phase 20: Check semantic grounding override
    if allow_semantic_override:
        override_applies, override_meta = check_semantic_grounding_override(
            retrieval_results
        )
        
        if override_applies:
            # Skip keyword validation, pass on semantic confidence
            return GroundingResult(
                is_grounded=True,
                topic=" ".join(query_terms[:3]),
                matched_terms=[],  # No literal matches needed
                reason="semantic_confidence",
                grounding_mode="semantic"
            )

    # Continue with existing keyword validation
    # Check top chunks for query term presence
    matched_terms = set()
    chunks_checked = min(check_top_k, len(retrieval_results))

    for doc, score in retrieval_results[:chunks_checked]:
        content = f" {doc.page_content.lower()} "  # Pad for word boundaries

        for term in query_terms:
            # Check for term presence (with common variations)
            if (f" {term} " in content or
                f" {term}s " in content or  # Plural
                f" {term}'" in content):    # Possessive
                matched_terms.add(term)

    is_grounded = len(matched_terms) >= min_term_matches

    # Derive topic from query terms for refusal message
    topic = " ".join(query_terms[:3])  # Use first 3 terms as topic

    # Phase 30: Check for entity confusion even if grounded
    # This catches cases where terms match but the wrong entity was retrieved
    if is_grounded:
        has_confusion, target, confusion = detect_entity_confusion(
            query_terms, retrieval_results, check_top_k
        )
        if has_confusion:
            return GroundingResult(
                is_grounded=False,
                topic=target or topic,
                matched_terms=list(matched_terms),
                reason=f"entity_confusion:{confusion}"
            )

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


def detect_entity_confusion(
    query_terms: List[str],
    retrieval_results: List[Tuple],  # [(doc, score), ...]
    check_top_k: int = 3
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Phase 30: Detect if retrieved content contains a confusion entity.

    Checks if the query is about entity A but retrieval returned content
    about entity B (a known semantic neighbor that causes confusion).

    Args:
        query_terms: Extracted terms from the query
        retrieval_results: List of (document, score) tuples
        check_top_k: Number of top chunks to check

    Returns:
        Tuple of (has_confusion, target_entity, confusion_entity)
        - has_confusion: True if confusion detected
        - target_entity: What the user asked about
        - confusion_entity: What was incorrectly retrieved

    Examples:
        Query: "Dean's list requirements"
        Retrieved: "Team Leadership Award criteria"
        Returns: (True, "dean's list", "team leadership")
    """
    if not ENABLE_CONFUSION_DETECTION:
        return False, None, None

    if not query_terms or not retrieval_results:
        return False, None, None

    # Build query string for entity matching
    query_lower = " ".join(query_terms).lower()

    # Check if query mentions any target entity
    target_entity = None
    confusion_list = None

    for entity, confusions in CONFUSION_PAIRS.items():
        if entity in query_lower:
            target_entity = entity
            confusion_list = confusions
            break

    if not target_entity:
        # Query doesn't mention any tracked entity
        return False, None, None

    # Check top chunks for confusion entities
    chunks_to_check = min(check_top_k, len(retrieval_results))

    for doc, score in retrieval_results[:chunks_to_check]:
        content_lower = doc.page_content.lower()

        # Check if content contains a confusion entity but NOT the target
        target_in_content = target_entity in content_lower

        for confusion in confusion_list:
            if confusion in content_lower and not target_in_content:
                logger.info(
                    f"[PHASE30] Entity confusion detected: "
                    f"query='{target_entity}', retrieved='{confusion}'"
                )
                return True, target_entity, confusion

    return False, None, None


def get_confusion_refusal_message(target: str, confusion: str) -> str:
    """
    Phase 30: Generate refusal message for entity confusion.

    Args:
        target: What the user asked about
        confusion: What was incorrectly retrieved

    Returns:
        User-friendly message explaining the confusion
    """
    return (
        f"I found information about {confusion}, but you asked about {target}. "
        f"Could you please clarify your question?"
    )


# Phase 29: Chunk diversity configuration
MAX_CHUNKS_PER_SECTION = 3  # Maximum chunks from same section (3 balances diversity vs completeness)
ENABLE_CHUNK_DIVERSITY = True  # Toggle for diversity enforcement

# Phase 30: Confusion pairs for entity mismatch detection
# Format: {target_entity: [confusion_entities]}
# When query mentions target, refuse if retrieval contains confusion entities instead
CONFUSION_PAIRS = {
    # Academic awards confusion
    "dean's list": ["team leadership", "leadership award", "excellence award", "service award"],
    "dean's lister": ["team leadership", "leadership award", "excellence award"],
    "deans list": ["team leadership", "leadership award", "excellence award"],
    "honors": ["special awards", "team leadership"],

    # Personnel vs awards confusion
    "deans": ["dean's list", "deans list", "dean's lister"],  # Asking about people, not the award
    "dean": ["dean's list", "deans list"],  # Single dean query

    # Location confusion
    "library": ["bookstore"],
    "bookstore": ["library"],
    "clinic": ["guidance"],
    "guidance": ["clinic"],

    # Document confusion
    "handbook": ["manual"],  # These are actually synonyms, but could cause issues
}

# Phase 30: Enable/disable confusion detection
ENABLE_CONFUSION_DETECTION = True


def apply_section_diversity(
    docs_with_scores: List[Tuple],  # [(doc, score), ...]
    max_per_section: int = MAX_CHUNKS_PER_SECTION
) -> List[Tuple]:
    """
    Phase 29: Apply section-based diversity to limit chunks per section.

    Prevents retrieval from being dominated by a single section.
    Keeps the highest-scoring chunks from each section.

    Args:
        docs_with_scores: List of (document, score) tuples, already sorted by score
        max_per_section: Maximum chunks allowed per section (default 2)

    Returns:
        Filtered list maintaining score order but limiting section repetition

    Examples:
        Input: 5 chunks from "Deans", 3 from "Prayer"
        Output: 2 from "Deans" (highest scoring), 2 from "Prayer" (highest scoring)
    """
    if not ENABLE_CHUNK_DIVERSITY or not docs_with_scores:
        return docs_with_scores

    section_counts = {}  # section -> count
    filtered_results = []
    skipped_sections = set()

    for doc, score in docs_with_scores:
        section = doc.metadata.get('section', 'Unknown')

        # Normalize section name (lowercase for comparison)
        section_key = section.lower().strip()

        # Track section count
        current_count = section_counts.get(section_key, 0)

        if current_count < max_per_section:
            # Keep this chunk
            filtered_results.append((doc, score))
            section_counts[section_key] = current_count + 1
        else:
            # Skip - already have enough from this section
            skipped_sections.add(section)

    if skipped_sections:
        logger.info(
            f"[PHASE29] Diversity filter: kept {len(filtered_results)} chunks "
            f"(skipped extras from: {', '.join(sorted(skipped_sections))})"
        )

    return filtered_results


def apply_mmr_diversity(
    docs_with_scores: List[Tuple],  # [(doc, score), ...]
    lambda_param: float = 0.7,
    top_k: int = 5
) -> List[Tuple]:
    """
    Phase 29: Apply Maximal Marginal Relevance (MMR) for diversity.

    MMR balances relevance with diversity by penalizing chunks
    that are too similar to already-selected chunks.

    Formula: MMR = λ * Sim(doc, query) - (1-λ) * max(Sim(doc, selected))

    Note: This is a simplified version using section overlap as similarity proxy.
    Full MMR would require embedding comparisons.

    Args:
        docs_with_scores: List of (document, score) tuples
        lambda_param: Balance between relevance (1.0) and diversity (0.0)
        top_k: Number of chunks to select

    Returns:
        MMR-reranked list of (document, score) tuples
    """
    if not docs_with_scores or len(docs_with_scores) <= top_k:
        return docs_with_scores

    selected = []
    remaining = list(docs_with_scores)
    selected_sections = set()

    while len(selected) < top_k and remaining:
        best_idx = 0
        best_mmr = float('-inf')

        for i, (doc, relevance) in enumerate(remaining):
            section = doc.metadata.get('section', 'Unknown').lower()

            # Diversity penalty: penalize if same section already selected
            diversity_penalty = 0.5 if section in selected_sections else 0.0

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = i

        # Select best and remove from remaining
        doc, score = remaining.pop(best_idx)
        selected.append((doc, score))
        selected_sections.add(doc.metadata.get('section', 'Unknown').lower())

    return selected
