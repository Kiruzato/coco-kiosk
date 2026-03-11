"""
Input Preprocessor - Phase 46: Arithmetic Query Processing
===========================================================
Preprocesses raw input (especially from STT) before downstream processing.

Purpose:
- Normalize numbers (remove commas, fix decimal confusion)
- Clean operator artifacts from STT (spurious periods, etc.)
- Apply ASR transcription corrections
- Prepare expressions for math engine detection

This layer sits between STT output and query analysis.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PREPROCESSING FUNCTION
# =============================================================================

def preprocess_input(text: str, source: str = "text") -> str:
    """
    Preprocess input for downstream processing.

    Args:
        text: Raw input text (possibly from STT)
        source: "voice" or "text" - voice gets more aggressive cleanup

    Returns:
        Cleaned and normalized text
    """
    if not text:
        return ""

    original = text
    result = text

    # Step 1: Normalize numbers (commas, thousands separators)
    result = normalize_numbers(result)

    # Step 2: Clean operator artifacts (spurious punctuation)
    result = clean_operators(result)

    # Step 3: Handle word-to-number conversions for math
    result = convert_number_words(result)

    # Step 4: Clean up trailing punctuation that breaks parsing
    result = clean_trailing_punctuation(result)

    # Step 5: Normalize whitespace
    result = re.sub(r' +', ' ', result).strip()

    # Log if preprocessing changed the input
    if result != original:
        logger.debug(f"[PREPROCESSOR] '{original[:50]}' -> '{result[:50]}'")

    return result


# =============================================================================
# NUMBER NORMALIZATION
# =============================================================================

def normalize_numbers(text: str) -> str:
    """
    Normalize number formatting.

    Handles:
    - Thousands separators: "5,000" -> "5000"
    - Millions: "1,000,000" -> "1000000"
    - Spoken numbers: "five thousand" -> "5000" (partial)

    Args:
        text: Input text

    Returns:
        Text with normalized numbers
    """
    result = text

    # Remove commas in numbers (thousands separators)
    # Match: digit, comma, exactly 3 digits (not followed by more digits)
    # Apply twice to handle millions (1,000,000)
    result = re.sub(r'(\d),(\d{3})(?!\d)', r'\1\2', result)
    result = re.sub(r'(\d),(\d{3})(?!\d)', r'\1\2', result)

    # Handle "X thousand" -> "X000"
    result = re.sub(r'(\d+)\s*thousand\b', lambda m: str(int(m.group(1)) * 1000), result, flags=re.IGNORECASE)

    # Handle "X million" -> "X000000"
    result = re.sub(r'(\d+)\s*million\b', lambda m: str(int(m.group(1)) * 1000000), result, flags=re.IGNORECASE)

    # Handle "X hundred" -> "X00"
    result = re.sub(r'(\d+)\s*hundred\b', lambda m: str(int(m.group(1)) * 100), result, flags=re.IGNORECASE)

    return result


# =============================================================================
# OPERATOR CLEANUP
# =============================================================================

def clean_operators(text: str) -> str:
    """
    Remove spurious punctuation around operators.

    STT often produces artifacts like:
    - "5." before an operator -> "5"
    - "5," before an operator -> "5"
    - ". *" -> " * "

    Args:
        text: Input text

    Returns:
        Text with cleaned operators
    """
    result = text

    # Remove period before operator: "5. *" -> "5 *"
    result = re.sub(r'(\d)\.\s*([+\-*/x])', r'\1 \2', result)

    # Remove comma before operator: "5, +" -> "5 +"
    result = re.sub(r'(\d),\s*([+\-*/x])', r'\1 \2', result)

    # Remove period after operator: "* .5" -> "* 5" (less common)
    result = re.sub(r'([+\-*/x])\s*\.(\d)', r'\1 \2', result)

    # Clean up multiple spaces around operators
    result = re.sub(r'\s*([+\-*/])\s*', r' \1 ', result)

    # Handle "x" as multiplication (case insensitive, with word boundaries)
    # Only replace "x" between numbers: "5 x 3" -> "5 * 3"
    result = re.sub(r'(\d)\s*[xX]\s*(\d)', r'\1 * \2', result)

    return result


# =============================================================================
# NUMBER WORD CONVERSION
# =============================================================================

def convert_number_words(text: str) -> str:
    """
    Convert common number words to digits (for math expressions).

    Handles common ASR substitutions:
    - "won" -> "1" (before operators)
    - "too/to" -> "2" (before operators)
    - "for" -> "4" (before operators)
    - "ate" -> "8" (before operators)

    Args:
        text: Input text

    Returns:
        Text with number words converted
    """
    result = text

    # Only convert when followed by operators (to avoid false positives)
    # "won" -> "1"
    result = re.sub(r'\bwon\b(?=\s*[+\-*/])', '1', result, flags=re.IGNORECASE)

    # "to/too" -> "2" (before operator)
    result = re.sub(r'\b(to|too)\b(?=\s*[+\-*/])', '2', result, flags=re.IGNORECASE)

    # "for" -> "4" (before operator)
    result = re.sub(r'\bfor\b(?=\s*[+\-*/])', '4', result, flags=re.IGNORECASE)

    # "ate" -> "8" (before operator)
    result = re.sub(r'\bate\b(?=\s*[+\-*/])', '8', result, flags=re.IGNORECASE)

    # Basic number words (only when in math context)
    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12'
    }

    for word, digit in number_words.items():
        # Only replace if near operators or other digits
        result = re.sub(
            rf'\b{word}\b(?=\s*[+\-*/\d])',
            digit,
            result,
            flags=re.IGNORECASE
        )
        result = re.sub(
            rf'(?<=[+\-*/\d]\s)\b{word}\b',
            digit,
            result,
            flags=re.IGNORECASE
        )

    return result


# =============================================================================
# TRAILING PUNCTUATION CLEANUP
# =============================================================================

def clean_trailing_punctuation(text: str) -> str:
    """
    Clean trailing punctuation that breaks math parsing.

    STT often adds sentence-ending punctuation to math expressions:
    - "5 + 3." -> "5 + 3"
    - "what is 10 divided by 2?" -> "what is 10 divided by 2"

    Args:
        text: Input text

    Returns:
        Text with trailing punctuation removed from numbers
    """
    result = text

    # Remove period/question mark after final number
    result = re.sub(r'(\d)[.?!]+\s*$', r'\1', result)

    # Remove period after number if followed by end or whitespace only
    result = re.sub(r'(\d)\.\s*$', r'\1', result)

    return result


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_math_like(text: str) -> bool:
    """
    Quick check if text looks like it might contain math.

    Args:
        text: Input text

    Returns:
        True if text contains math-like patterns
    """
    # Contains digits and operators
    has_digits = bool(re.search(r'\d', text))
    has_operators = bool(re.search(r'[+\-*/x]', text, re.IGNORECASE))

    # Or contains math words
    math_words = ['plus', 'minus', 'times', 'divided', 'multiply', 'add', 'subtract']
    has_math_words = any(word in text.lower() for word in math_words)

    return (has_digits and has_operators) or (has_digits and has_math_words)


def preprocess_for_math(text: str) -> Tuple[str, bool]:
    """
    Preprocess specifically for math evaluation.

    Args:
        text: Input text

    Returns:
        Tuple of (preprocessed_text, was_modified)
    """
    original = text
    result = preprocess_input(text, source="voice")
    return result, result != original
