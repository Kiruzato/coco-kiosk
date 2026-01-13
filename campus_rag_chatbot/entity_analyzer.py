"""
Entity Agreement Analyzer for Directory Queries
================================================
Extracts location entities from retrieved chunks and checks for consistency.

This module enables entity-aware confidence promotion for directory queries
by verifying that all retrieved chunks refer to the same location entity.

Used to safely promote borderline MEDIUM confidence to HIGH when there is
strong entity agreement, without lowering global similarity thresholds.
"""

import re
from typing import List, Tuple, Optional
from langchain_core.documents import Document


# ==============================================================================
# LOCATION ENTITY PATTERNS
# ==============================================================================

# Patterns for extracting location entities from chunk text
# Order matters - more specific patterns should come first
LOCATION_PATTERNS = [
    # Directory format header (highest priority)
    r"=== LOCATION: (.+?) ===",

    # Room numbers: SP-303, AD201, sp303
    r"\b[Rr]oom\s+([A-Za-z]{1,3}[-]?\d+)\b",
    r"\b([A-Za-z]{1,3}[-]?\d{2,4})\b",

    # Specific facilities (normalize variations)
    r"\b((?:Main\s+)?[Ll]ibrary)\b",
    r"\b([Cc]anteen|[Cc]afeteria)\b",
    r"\b([Cc]linic|[Hh]ealth\s+[Cc]enter)\b",
    r"\b([Gg]ymnasium|[Gg]ym)\b",
    r"\b([Cc]hapel)\b",
    r"\b([Rr]egistrar(?:'s)?\s*(?:[Oo]ffice)?)\b",
    r"\b([Gg]uidance(?:\s+[Oo]ffice)?)\b",

    # Office patterns
    r"\b([A-Z][a-z]+(?:'s)?\s+[Oo]ffice)\b",
    r"\b([Dd]ean(?:'s)?\s+[Oo]ffice)\b",

    # Building patterns
    r"\b([A-Z][a-z]+\s+[Bb]uilding)\b",
    r"\b([A-Z][a-z]+\s+[Cc]enter)\b",
    r"\b([A-Z][a-z]+\s+[Hh]all)\b",

    # Court patterns
    r"\b([Bb]asketball\s+[Cc]ourt)\b",
    r"\b([Cc]overed\s+[Cc]ourts?)\b",
]


# ==============================================================================
# ENTITY NORMALIZATION
# ==============================================================================

def normalize_entity(entity: str) -> str:
    """
    Normalize extracted entity for comparison.

    Args:
        entity: Raw extracted entity string

    Returns:
        Normalized lowercase entity string
    """
    if not entity:
        return ""

    # Convert to lowercase
    normalized = entity.lower().strip()

    # Normalize common variations
    normalizations = {
        "cafeteria": "canteen",
        "gymnasium": "gym",
        "health center": "clinic",
        "main library": "library",
        "registrar's office": "registrar",
        "registrar office": "registrar",
        "guidance office": "guidance",
        "dean's office": "dean office",
    }

    for variant, standard in normalizations.items():
        if variant in normalized:
            normalized = standard
            break

    return normalized


# ==============================================================================
# ENTITY EXTRACTION
# ==============================================================================

def extract_location_entity(text: str) -> Optional[str]:
    """
    Extract primary location entity from chunk text.

    Uses pattern matching to identify location references in the text.
    Returns the first matching entity found (patterns are ordered by specificity).

    Args:
        text: Chunk text to analyze

    Returns:
        Normalized entity string, or None if no entity found
    """
    if not text:
        return None

    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw_entity = match.group(1).strip()
            return normalize_entity(raw_entity)

    return None


# ==============================================================================
# ENTITY AGREEMENT CHECKING
# ==============================================================================

def check_entity_agreement(
    docs: List[Document],
    scores: Optional[List[float]] = None,
    min_score_for_agreement: float = 0.78
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Check if high-scoring retrieved chunks refer to the same location entity.

    Analyzes each document's text to extract location entities and
    determines if there is agreement among chunks that meet the score threshold.

    Args:
        docs: List of retrieved Document objects
        scores: Optional list of similarity scores (same order as docs)
        min_score_for_agreement: Minimum score for a chunk to be considered
                                 for entity agreement (default 0.70)

    Returns:
        Tuple of:
        - has_agreement: True if high-scoring chunks with entities agree
        - common_entity: The agreed-upon entity (None if no agreement)
        - all_entities: List of all extracted entities for debugging
    """
    if not docs:
        return False, None, []

    entities = []
    all_entities = []  # Track all entities for debugging

    for i, doc in enumerate(docs):
        # Prefer original_text from metadata (pre-normalization text)
        text = doc.metadata.get('original_text', doc.page_content)
        entity = extract_location_entity(text)

        if entity:
            all_entities.append(entity)
            # Only consider high-scoring chunks for agreement
            if scores is None or (i < len(scores) and scores[i] >= min_score_for_agreement):
                entities.append(entity)

    # No high-scoring entities found - cannot determine agreement
    if not entities:
        return False, None, all_entities

    # Check for unanimous agreement among high-scoring chunks
    unique_entities = set(entities)
    if len(unique_entities) == 1:
        return True, entities[0], all_entities

    # Multiple different entities in high-scoring chunks - no agreement
    return False, None, all_entities


# ==============================================================================
# CONFIDENCE PROMOTION LOGIC
# ==============================================================================

# Promotion thresholds (slightly relaxed from HIGH confidence requirements)
PROMOTION_AVG_THRESHOLD = 0.70      # HIGH requires 0.75
PROMOTION_MAX_THRESHOLD = 0.80      # Same as HIGH
PROMOTION_MIN_CHUNKS = 2            # Same as HIGH
PROMOTION_MAX_VARIANCE = 0.05       # Same as HIGH


def should_promote_confidence(
    avg_similarity: float,
    max_similarity: float,
    num_chunks: int,
    variance: float,
    has_entity_agreement: bool
) -> Tuple[bool, str]:
    """
    Determine if confidence should be promoted from MEDIUM to HIGH.

    This function implements multi-signal validation for safe confidence
    promotion. All criteria must be met for promotion to occur.

    Args:
        avg_similarity: Average similarity score across retrieved chunks
        max_similarity: Maximum similarity score (best match)
        num_chunks: Number of chunks retrieved
        variance: Variance in similarity scores (lower = more consistent)
        has_entity_agreement: Whether all chunks reference the same entity

    Returns:
        Tuple of:
        - should_promote: True if confidence should be promoted to HIGH
        - reason: Explanation string for the decision
    """
    # Check each criterion and return early with reason if not met

    if avg_similarity < PROMOTION_AVG_THRESHOLD:
        return False, f"Avg similarity {avg_similarity:.3f} below promotion threshold {PROMOTION_AVG_THRESHOLD}"

    if max_similarity < PROMOTION_MAX_THRESHOLD:
        return False, f"Max similarity {max_similarity:.3f} below threshold {PROMOTION_MAX_THRESHOLD}"

    if num_chunks < PROMOTION_MIN_CHUNKS:
        return False, f"Chunk count {num_chunks} below minimum {PROMOTION_MIN_CHUNKS}"

    if variance > PROMOTION_MAX_VARIANCE:
        return False, f"Variance {variance:.3f} exceeds maximum {PROMOTION_MAX_VARIANCE}"

    if not has_entity_agreement:
        return False, "No entity agreement across retrieved chunks"

    # All criteria met - safe to promote
    return True, "Entity agreement confirmed with strong similarity metrics"
