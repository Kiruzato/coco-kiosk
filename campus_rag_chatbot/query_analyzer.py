"""
Query Analyzer - Phase 45: Response Style Policy
=================================================
Classifies queries for appropriate response formatting.

This is separate from intent classification - it's about HOW to format
responses, not WHERE to route them.

Purpose:
- Detect query type (math, greeting, definition, etc.)
- Determine complexity level (simple, moderate, detailed)
- Decide if LaTeX is appropriate
- Provide style hints for kiosk/voice-friendly responses
- Normalize common ASR transcription errors
"""

import re
import logging
from enum import Enum
from typing import Dict, Any

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class QueryComplexity(Enum):
    """Query complexity levels for response formatting."""
    SIMPLE = "simple"      # One-shot answers (math, yes/no, greetings)
    MODERATE = "moderate"  # Short explanations (definitions, facts)
    DETAILED = "detailed"  # Full explanations (campus info, procedures)


class QueryType(Enum):
    """Query types for response style adaptation."""
    MATH = "math"              # Mathematical calculations
    GREETING = "greeting"      # Hi, hello, thanks, bye
    FACTUAL = "factual"        # General knowledge facts
    DEFINITION = "definition"  # "What is X?"
    CONVERSATIONAL = "conversational"  # Casual chat
    CAMPUS = "campus"          # Campus-specific queries


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

# Simple math patterns (arithmetic, no LaTeX needed)
SIMPLE_MATH_PATTERNS = [
    r'^\s*\d+\s*[\+\-\*\/x]\s*\d+',                    # "5 + 3" or "5 x 3"
    r'^\s*(what\s+is\s+)?\d+\s*[\+\-\*\/x]\s*\d+',     # "what is 5 + 3"
    r'(add|subtract|multiply|divide)\s+\d+',
    r'\d+\s*(plus|minus|times|divided by)\s+\d+',
    r'(how much|how many)\s+is\s+\d+',
    r'calculate\s+\d+',
    r'(\d+\s*[\+\-\*\/]\s*)+\d+',                      # Chain: "5 + 3 - 2"
    r'\d+\s*(x|\*)\s*\d+',                             # multiplication
    r'what\s+(is|does|equals?)\s+\d+',                 # "what is 5..."
]

# Complex math patterns (may need LaTeX for clarity)
COMPLEX_MATH_PATTERNS = [
    r'(integral|derivative|equation|solve\s+for|quadratic|polynomial)',
    r'(matrix|vector|determinant|eigenvalue)',
    r'(logarithm|exponential|trigonometr)',
    r'\^\d+',                                           # Exponents like x^2
    r'\\frac|\\sqrt|\\sum|\\int',                       # Existing LaTeX in query
    r'(factor|simplify|expand)\s+(the\s+)?(expression|equation)',
]

# Greeting patterns
GREETING_PATTERNS = [
    r'^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|greetings)\b',
    r'^(thanks|thank you|bye|goodbye|see you|take care)\b',
    r'^(how are you|what\'?s up|how\'?s it going)\b',
    r'^(yo|sup|hiya)\b',
]

# Definition patterns
DEFINITION_PATTERNS = [
    r'^(what is|what are|what\'s)\s+(?!(\d|my|your|the time|the date))',
    r'^(define|explain|describe)\s+',
    r'^(who is|who are|who was)\s+',
    r'^(when is|when was|when did)\s+',
    r'^tell me (about|what)',
]

# ASR transcription error corrections
ASR_CORRECTIONS = {
    # "times" variants
    r'\b(thymes|tines|timz|time\'s)\b': 'times',
    # "plus" variants
    r'\b(pluss|pless|pluz|plus\'s)\b': 'plus',
    # "minus" variants
    r'\b(minuss|mynus|mine us)\b': 'minus',
    # "equals" variants
    r'\b(equalz|equal|equels|equals\')\b': 'equals',
    # "divided by" variants
    r'\b(divide by|diveded by|divided bi)\b': 'divided by',
    # Number words to digits (common ASR issues)
    r'\bwon\b': '1',
    r'\btoo\b': '2',
    r'\bto\b(?=\s*[\+\-\*\/])': '2',  # "to" before operator → "2"
    r'\bfor\b(?=\s*[\+\-\*\/])': '4',  # "for" before operator → "4"
    r'\bate\b': '8',
}


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def normalize_asr_query(query: str) -> str:
    """
    Normalize common ASR transcription errors.

    Args:
        query: Raw query text (possibly from speech recognition)

    Returns:
        Normalized query with common errors corrected
    """
    result = query
    for pattern, replacement in ASR_CORRECTIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def analyze_query(query: str) -> Dict[str, Any]:
    """
    Analyze query for response formatting purposes.

    Args:
        query: The user's question

    Returns:
        Dict with:
        - query_type: QueryType enum
        - complexity: QueryComplexity enum
        - needs_latex: bool (should LaTeX be used)
        - is_voice_friendly: bool (current query easily spoken)
        - formatting_hints: dict with specific guidance
    """
    # Normalize ASR errors first
    normalized = normalize_asr_query(query)
    query_lower = normalized.lower().strip()

    # Check for simple math
    is_simple_math = any(re.search(p, query_lower) for p in SIMPLE_MATH_PATTERNS)
    is_complex_math = any(re.search(p, query_lower) for p in COMPLEX_MATH_PATTERNS)

    if is_simple_math and not is_complex_math:
        logger.debug(f"[QUERY-ANALYZER] Detected simple math: {query[:30]}")
        return {
            "query_type": QueryType.MATH,
            "complexity": QueryComplexity.SIMPLE,
            "needs_latex": False,
            "is_voice_friendly": True,
            "formatting_hints": {
                "max_sentences": 1,
                "avoid_notation": True,
                "conversational_style": True,
                "style_key": "math_simple"
            }
        }

    if is_complex_math:
        logger.debug(f"[QUERY-ANALYZER] Detected complex math: {query[:30]}")
        return {
            "query_type": QueryType.MATH,
            "complexity": QueryComplexity.MODERATE,
            "needs_latex": True,  # Only case where LaTeX is appropriate
            "is_voice_friendly": False,
            "formatting_hints": {
                "max_sentences": 5,
                "explain_steps": True,
                "style_key": "math_complex"
            }
        }

    # Check for greetings
    if any(re.search(p, query_lower) for p in GREETING_PATTERNS):
        logger.debug(f"[QUERY-ANALYZER] Detected greeting: {query[:30]}")
        return {
            "query_type": QueryType.GREETING,
            "complexity": QueryComplexity.SIMPLE,
            "needs_latex": False,
            "is_voice_friendly": True,
            "formatting_hints": {
                "max_sentences": 2,
                "warm_tone": True,
                "no_disclaimers": True,
                "style_key": "greeting"
            }
        }

    # Check for definitions
    if any(re.search(p, query_lower) for p in DEFINITION_PATTERNS):
        logger.debug(f"[QUERY-ANALYZER] Detected definition query: {query[:30]}")
        return {
            "query_type": QueryType.DEFINITION,
            "complexity": QueryComplexity.MODERATE,
            "needs_latex": False,
            "is_voice_friendly": True,
            "formatting_hints": {
                "max_sentences": 4,
                "start_with_answer": True,
                "style_key": "definition"
            }
        }

    # Default: conversational
    logger.debug(f"[QUERY-ANALYZER] Default conversational: {query[:30]}")
    return {
        "query_type": QueryType.CONVERSATIONAL,
        "complexity": QueryComplexity.MODERATE,
        "needs_latex": False,
        "is_voice_friendly": True,
        "formatting_hints": {
            "max_sentences": 5,
            "natural_style": True,
            "style_key": "default"
        }
    }


def is_simple_calculation(query: str) -> bool:
    """
    Quick check if query is a simple math calculation.

    Args:
        query: The user's question

    Returns:
        True if this is a simple arithmetic query
    """
    normalized = normalize_asr_query(query)
    query_lower = normalized.lower().strip()
    is_simple = any(re.search(p, query_lower) for p in SIMPLE_MATH_PATTERNS)
    is_complex = any(re.search(p, query_lower) for p in COMPLEX_MATH_PATTERNS)
    return is_simple and not is_complex


def is_greeting(query: str) -> bool:
    """
    Quick check if query is a greeting/farewell.

    Args:
        query: The user's question

    Returns:
        True if this is a greeting or farewell
    """
    query_lower = query.lower().strip()
    return any(re.search(p, query_lower) for p in GREETING_PATTERNS)


def get_style_key(query: str) -> str:
    """
    Get the style key for a query (for prompt template selection).

    Args:
        query: The user's question

    Returns:
        Style key string (e.g., "math_simple", "greeting", "default")
    """
    analysis = analyze_query(query)
    return analysis["formatting_hints"].get("style_key", "default")
