"""
Entity Resolver for Directory Queries
======================================
Resolves query subjects to structured directory entities.

This module provides:
- extract_subject: Extract location subject from canonicalized query
- resolve_entity: Match subject against entity registry
- format_entity_response: Generate natural language response from entity

Resolution is deterministic and prioritizes exact matches for safety.
"""

import re
import logging
from typing import Optional, Tuple

from entity_registry import DirectoryEntity, EntityRegistry

logger = logging.getLogger(__name__)


def extract_subject(canonical_query: str) -> str:
    """
    Extract the location subject from a canonicalized directory query.

    The canonical query format is "[subject] location" (from canonicalize_directory_query).
    This function extracts just the subject part.

    Args:
        canonical_query: Canonicalized query (e.g., "library location", "room sp303 location")

    Returns:
        Extracted subject (e.g., "library", "sp303")

    Examples:
        >>> extract_subject("library location")
        'library'
        >>> extract_subject("room sp303 location")
        'sp303'
        >>> extract_subject("cafeteria location")
        'cafeteria'
    """
    if not canonical_query:
        return ""

    # Remove " location" suffix if present
    subject = canonical_query.lower().strip()
    if subject.endswith(" location"):
        subject = subject[:-9].strip()

    # Remove "room " prefix if present (for room queries)
    if subject.startswith("room "):
        subject = subject[5:].strip()

    return subject


def resolve_entity(
    subject: str,
    registry: EntityRegistry
) -> Tuple[Optional[DirectoryEntity], float, str]:
    """
    Resolve a query subject to a directory entity.

    Resolution Strategy (in priority order):
    1. Exact match on canonical_name (case-insensitive)
    2. Exact match on any alias (case-insensitive)

    The resolution is deterministic - same subject always yields same result.

    Args:
        subject: Extracted location subject (e.g., "library", "cafeteria")
        registry: EntityRegistry instance with loaded entities

    Returns:
        Tuple of:
        - entity: Resolved DirectoryEntity or None
        - confidence: 1.0 for exact match, 0.0 for no match
        - method: Resolution method ("exact_canonical", "exact_alias", "none")

    Examples:
        >>> entity, conf, method = resolve_entity("library", registry)
        >>> entity.canonical_name
        'Main Library'
        >>> conf
        1.0
        >>> method
        'exact_alias'
    """
    if not subject or not registry:
        return None, 0.0, "none"

    normalized = subject.lower().strip()

    # Attempt lookup via alias index (includes canonical names)
    entity = registry.get_by_alias(normalized)

    if entity:
        # Safety check: ensure entity is active (defense-in-depth)
        if getattr(entity, 'status', 'active') != 'active':
            logger.debug(f"Entity '{entity.entity_id}' found but inactive")
            return None, 0.0, "none"

        # Determine if it was canonical or alias match
        if entity.canonical_name.lower() == normalized:
            return entity, 1.0, "exact_canonical"
        else:
            return entity, 1.0, "exact_alias"

    # No match found
    logger.debug(f"Entity resolution failed for subject: '{subject}'")
    return None, 0.0, "none"


def format_entity_response(entity: DirectoryEntity) -> str:
    """
    Format a directory entity as a natural language response.

    Generates a deterministic, template-based response that includes:
    - Location name
    - Building
    - Floor
    - Room (if applicable)
    - Landmarks for navigation

    This avoids LLM generation, ensuring no hallucination of location details.

    Args:
        entity: DirectoryEntity to format

    Returns:
        Natural language response string

    Examples:
        >>> response = format_entity_response(canteen_entity)
        >>> print(response)
        The Canteen is located in the Student Center Building, Ground Floor.
        It is behind the Saint Peter Building, accessible via the covered walkway.
    """
    if not entity:
        return ""

    # Build response parts
    parts = []

    # Main location statement
    location_stmt = f"The {entity.canonical_name} is located in the {entity.building}"

    if entity.floor:
        location_stmt += f", {entity.floor}"

    if entity.room:
        location_stmt += f" (Room {entity.room})"

    location_stmt += "."
    parts.append(location_stmt)

    # Add landmark/navigation info if available
    if entity.landmarks:
        # Clean up landmarks text
        landmarks = entity.landmarks.strip()
        if landmarks:
            # Ensure proper sentence structure
            if landmarks[0].islower():
                landmarks = landmarks[0].upper() + landmarks[1:]
            if not landmarks.endswith('.'):
                landmarks += '.'
            parts.append(landmarks)

    return " ".join(parts)


def get_resolution_summary(
    subject: str,
    entity: Optional[DirectoryEntity],
    confidence: float,
    method: str
) -> dict:
    """
    Generate a summary dict for logging/debugging entity resolution.

    Args:
        subject: Original query subject
        entity: Resolved entity (or None)
        confidence: Resolution confidence
        method: Resolution method used

    Returns:
        Dictionary with resolution details
    """
    return {
        "subject": subject,
        "resolved": entity is not None,
        "entity_id": entity.entity_id if entity else None,
        "canonical_name": entity.canonical_name if entity else None,
        "confidence": confidence,
        "method": method
    }
