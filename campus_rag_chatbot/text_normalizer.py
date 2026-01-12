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
