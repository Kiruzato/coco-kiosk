# ==============================================================================
# WARNING: SYNCHRONIZED FILE
# ==============================================================================
# This file exists in TWO locations:
#   1. WEB_APP/modules/text_normalizer.py       (runtime)
#   2. INGESTION_MODULE/modules/text_normalizer.py  (ingestion)
#
# These copies are intentionally independent to maintain strict architectural
# isolation between WEB_APP and INGESTION_MODULE. Neither module may import
# from the other.
#
# ANY CHANGES to this file MUST be manually mirrored to the other copy.
# Failure to synchronize will cause behavioral divergence between runtime
# and ingestion environments.
# ==============================================================================
"""
Text Normalization Utility
==========================
Provides consistent text normalization for embedding and retrieval.

This module ensures that text is normalized identically at both:
- Ingestion time (when creating embeddings for documents)
- Query time (when searching for similar documents)

This eliminates retrieval score discrepancies caused by casing or
minor formatting differences (e.g., "canteen" vs "Canteen").
"""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent embedding/retrieval.

    Operations performed (in order):
    1. Handle empty/None input
    2. Normalize Unicode characters to NFKC form
    3. Convert to lowercase
    4. Collapse multiple whitespace to single space
    5. Strip leading/trailing whitespace

    Args:
        text: Input text string

    Returns:
        Normalized text string

    Examples:
        >>> normalize_text("Where is the Canteen?")
        'where is the canteen?'
        >>> normalize_text("  Multiple   Spaces  ")
        'multiple spaces'
        >>> normalize_text("UPPERCASE TEXT")
        'uppercase text'
    """
    if not text:
        return ""

    # Normalize Unicode characters (NFKC form)
    # This handles things like fancy quotes, ligatures, etc.
    text = unicodedata.normalize('NFKC', text)

    # Convert to lowercase for case-insensitive matching
    text = text.lower()

    # Collapse multiple whitespace (spaces, tabs, newlines) to single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def normalize_for_display(text: str) -> str:
    """
    Light normalization for display purposes only.

    This preserves casing but cleans up whitespace issues.
    Used when we want readable text but with consistent formatting.

    Args:
        text: Input text string

    Returns:
        Lightly normalized text string
    """
    if not text:
        return ""

    # Normalize Unicode
    text = unicodedata.normalize('NFKC', text)

    # Collapse multiple whitespace to single space (preserve case)
    text = re.sub(r'\s+', ' ', text)

    # Strip edges
    text = text.strip()

    return text


def canonicalize_directory_query(query: str) -> str:
    """
    Transform directory queries into canonical "[subject] location" format.

    This improves semantic alignment with document text for embedding similarity.
    Should be called AFTER normalize_text() and ONLY for directory queries.

    Args:
        query: Normalized query string (lowercase, trimmed)

    Returns:
        Canonicalized query in "[subject] location" format

    Examples:
        >>> canonicalize_directory_query("where is canteen")
        'canteen location'
        >>> canonicalize_directory_query("where is the library")
        'library location'
        >>> canonicalize_directory_query("how do i get to sp303")
        'room sp303 location'
    """
    if not query:
        return ""

    # Patterns to strip (order matters - more specific first)
    patterns_to_remove = [
        r"^where is the\s+",
        r"^where's the\s+",
        r"^where is\s+",
        r"^where's\s+",
        r"^how do i get to the\s+",
        r"^how do i get to\s+",
        r"^how to get to the\s+",
        r"^how to get to\s+",
        r"^directions to the\s+",
        r"^directions to\s+",
        r"^where can i find the\s+",
        r"^where can i find\s+",
        r"^looking for the\s+",
        r"^looking for\s+",
        r"^find the\s+",
        r"^locate the\s+",
        r"^location of the\s+",
        r"^location of\s+",
        r"^which building is the\s+",
        r"^which building is\s+",
        r"^what building is the\s+",
        r"^what building is\s+",
        r"^which floor is the\s+",
        r"^which floor is\s+",
        r"^what floor is the\s+",
        r"^what floor is\s+",
        r"^what room is the\s+",
        r"^what room is\s+",
    ]

    subject = query
    for pattern in patterns_to_remove:
        subject = re.sub(pattern, "", subject)

    # Remove trailing question words/phrases
    trailing_patterns = [
        r"\s+located(\?)?$",
        r"\s+at(\?)?$",
        r"\s+in(\?)?$",
        r"\s+on(\?)?$",
        r"\?$",
    ]
    for pattern in trailing_patterns:
        subject = re.sub(pattern, "", subject)

    subject = subject.strip()

    if not subject:
        return query  # Return original if nothing extracted

    # Check if subject looks like a room number (e.g., sp303, sp-303)
    if re.match(r"^[a-z]{1,3}[-]?\d+", subject):
        return f"room {subject} location"

    return f"{subject} location"
