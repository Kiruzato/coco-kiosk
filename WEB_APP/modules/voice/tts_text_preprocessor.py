"""
TTS Text Preprocessor
=====================

Context-aware text preprocessing for speech synthesis.

Expands abbreviations based on surrounding context so that Piper TTS
pronounces them correctly. Operates only on text sent to the TTS engine;
the displayed chatbot response remains unchanged.

Design:
- Lightweight regex-based rules (no external NLP models)
- Suitable for Raspberry Pi hardware
- Extensible: add new abbreviation rules without modifying TTS service
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CONTEXT-AWARE ABBREVIATION RULES
# =============================================================================

# Words that indicate a street/address context BEFORE "St."
_STREET_CONTEXT_WORDS = {
    'main', 'elm', 'oak', 'pine', 'maple', 'cedar', 'park', 'market',
    'broad', 'high', 'wall', 'baker', 'king', 'queen', 'church',
    'north', 'south', 'east', 'west', '1st', '2nd', '3rd', '4th', '5th',
}

# Pattern: "St." followed by a capitalized word (likely "Saint [Name]")
_ST_SAINT_PATTERN = re.compile(
    r'\bSt\.\s+([A-Z][a-z])',
)

# Pattern: word before "St." that suggests street context
# e.g., "Main St.", "Elm St.", or a number like "123 St."
_ST_STREET_PATTERN = re.compile(
    r'(\b\w+)\s+St\.(?:\s|$|,|;)',
)


def _expand_st(text: str) -> str:
    """
    Context-aware expansion of "St." to "Saint" or "Street".

    Rules:
    1. "St." followed by a capitalized name → "Saint" (e.g., St. Thomas → Saint Thomas)
    2. "St." preceded by a street-context word or number → "Street" (e.g., Main St. → Main Street)
    3. Standalone or ambiguous "St." at end of sentence → "Street" (default for standalone)

    In a campus kiosk context, "St." followed by a name is overwhelmingly "Saint".
    """
    # Pass 1: Replace "St. [CapitalizedName]" with "Saint [Name]"
    # This must run first to catch saint names before the street pass
    text = _ST_SAINT_PATTERN.sub(r'Saint \1', text)

    # Pass 2: Replace remaining "St." (not followed by capital) with "Street"
    # These are typically address contexts like "Main St." or trailing "St."
    text = re.sub(r'\bSt\.', 'Street', text)

    return text


# Unambiguous abbreviations — always expand the same way
_SIMPLE_ABBREVIATIONS: List[Tuple[str, str]] = [
    ('Dr.', 'Doctor'),
    ('Engr.', 'Engineer'),
    ('Atty.', 'Attorney'),
    ('Prof.', 'Professor'),
    ('Bldg.', 'Building'),
    ('Rm.', 'Room'),
    ('Flr.', 'Floor'),
    ('Ave.', 'Avenue'),
    ('Blvd.', 'Boulevard'),
    ('Dept.', 'Department'),
    ('Govt.', 'Government'),
    ('Univ.', 'University'),
    ('vs.', 'versus'),
    ('etc.', 'etcetera'),
    ('e.g.', 'for example'),
    ('i.e.', 'that is'),
    ('Jr.', 'Junior'),
    ('Sr.', 'Senior'),
    ('Mr.', 'Mister'),
    ('Mrs.', 'Misses'),
    ('Ms.', 'Miss'),
    ('Arch.', 'Architect'),
]

# Acronym pronunciation hints
_ACRONYM_EXPANSIONS: List[Tuple[str, str]] = [
    ('CCIT', 'C C I T'),
    ('CoCo', 'Coco'),
]


def preprocess_for_tts(text: str) -> str:
    """
    Preprocess text for TTS synthesis with context-aware abbreviation expansion.

    This function transforms text to improve pronunciation accuracy in Piper TTS
    without modifying the displayed response. It should be called only in the
    TTS pipeline, after markdown stripping and before synthesis.

    Processing order:
    1. Context-aware "St." expansion (Saint vs Street)
    2. Simple abbreviation expansion (Dr., Prof., etc.)
    3. Acronym expansion (CCIT, CoCo)

    Args:
        text: Raw text to preprocess for speech

    Returns:
        Text with abbreviations expanded for correct pronunciation
    """
    if not text:
        return text

    # Step 1: Context-aware expansions (must run before simple replacements)
    text = _expand_st(text)

    # Step 2: Simple abbreviations (unambiguous, direct replacement)
    for abbr, expansion in _SIMPLE_ABBREVIATIONS:
        text = text.replace(abbr, expansion)

    # Step 3: Acronym expansions
    for acronym, pronunciation in _ACRONYM_EXPANSIONS:
        text = text.replace(acronym, pronunciation)

    return text
