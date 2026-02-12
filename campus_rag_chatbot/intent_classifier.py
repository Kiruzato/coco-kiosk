"""
Intent Classifier Module - Phase 6 + Phase 8 + Phase 50
========================================================
This module classifies user query intent to enable dual-mode answering:
- Campus queries → RAG pipeline with campus documents
- General queries → Direct LLM without retrieval
- Ambiguous queries → Ask for clarification
- Directory queries → Strict location/wayfinding with high confidence (Phase 8)
- Structured queries → Campus Query Engine (Phase 49-50)

Intent classification uses the existing LLM (gpt-4o-mini) with a structured prompt.

Phase 50 Update:
- Structured campus queries now route to Campus Query Engine (CQE)
- CQE handles: LOCATE_SINGLE, LOCATE_MULTIPLE, NEAREST, COUNT, LIST intents
- is_directory_query() preserved for backward compatibility
- New is_structured_campus_query() delegates to campus_query_parser.is_campus_query()
"""

import re
from enum import Enum
from typing import Tuple, Dict, Any, List
from langchain_openai import ChatOpenAI


class QueryIntent(Enum):
    """Query intent classification enumeration."""
    CAMPUS = "campus"
    GENERAL = "general"
    AMBIGUOUS = "ambiguous"
    DIRECTORY = "directory"  # Phase 8: Location/wayfinding queries
    STRUCTURED = "structured"  # Phase 50: Campus Query Engine structured queries


# ==============================================================================
# CAMPUS KEYWORDS
# ==============================================================================

# Keywords for campus-related topics (used in safety checks)
CAMPUS_KEYWORDS = [
    "library", "dining", "parking", "campus", "student",
    "college", "columban", "building", "hours",
    "employment", "wifi", "it services", "meal plan",
    "registration", "housing", "event", "facility",
    "gym", "rec center", "academic", "advisor",
    "dorm", "residence", "tuition", "financial aid"
]


# ==============================================================================
# DIRECTORY QUERY DETECTION - Phase 8
# ==============================================================================

# Patterns that indicate a location/directory query (legacy - Phase 8)
DIRECTORY_PATTERNS = [
    r"\bwhere is\b",
    r"\bwhere's\b",
    r"\bwhere can i find\b",
    r"\blocation of\b",
    r"\bhow do i get to\b",
    r"\bhow to get to\b",
    r"\bdirections to\b",
    r"\bfind the\b",
    r"\blooking for\b",
    r"\bwhich building\b",
    r"\bwhich floor\b",
    r"\bwhat room\b",
    r"\bwhat building\b",
    r"\bwhere do i go\b",
    r"\blocate the\b",
    r"\broom number\b",
    r"\bwhat floor\b",
]


# ==============================================================================
# CAMPUS QUERY ENGINE PATTERNS - Phase 50
# ==============================================================================

# Additional patterns for CQE intents (comprehensive list for reference)
# These are also defined in campus_query_parser.py - kept here for documentation

CQE_LOCATE_MULTIPLE_PATTERNS = [
    r"\bshow all\b",
    r"\blist all\b",
    r"\bwhat are the\b",
    r"\bwhere are the\b",
    r"\bshow me all\b",
]

CQE_NEAREST_PATTERNS = [
    r"\bnearest\b",
    r"\bclosest\b",
    r"\bnearby\b",
    r"\bnear here\b",
]

CQE_COUNT_PATTERNS = [
    r"\bhow many\b",
    r"\bcount\b",
    r"\bnumber of\b",
    r"\btotal\s+(?:number\s+)?of\b",
]

CQE_LIST_PATTERNS = [
    r"^list\b",
    r"\blist the\b",
    r"\bshow departments\b",
    r"\bshow buildings\b",
]


def is_directory_query(query: str) -> bool:
    """
    Detect if query is asking for location/directory information.

    Phase 8: Uses lightweight regex patterns to identify wayfinding questions
    before LLM classification. This enables stricter answering policies for
    location queries.

    NOTE: Phase 50 - This function is preserved for backward compatibility.
    Prefer using is_structured_campus_query() which uses the Campus Query Engine
    for comprehensive location query handling (LOCATE_SINGLE, LOCATE_MULTIPLE,
    NEAREST, COUNT, LIST).

    Args:
        query: User query string

    Returns:
        True if the query matches directory/location patterns
    """
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in DIRECTORY_PATTERNS)


def is_structured_campus_query(query: str) -> bool:
    """
    Detect if query should be handled by Campus Query Engine.

    Phase 50: Delegates to campus_query_parser.is_campus_query() for unified
    detection of all 5 CQE intents:
    - LOCATE_SINGLE: "Where is SP303?", "Where is the library?"
    - LOCATE_MULTIPLE: "Show all classrooms", "Where are the restrooms?"
    - NEAREST: "What's the nearest restroom?", "Closest clinic to SP303"
    - COUNT: "How many offices?", "Number of labs in A Building"
    - LIST: "List all departments", "Show buildings"

    Args:
        query: User query string

    Returns:
        True if the query should be handled by CQE
    """
    try:
        from campus_query_parser import is_campus_query
        return is_campus_query(query)
    except ImportError:
        # CQE not available, fall back to legacy directory detection
        return is_directory_query(query)


# ==============================================================================
# INTENT CLASSIFICATION
# ==============================================================================

def classify_intent(
    query: str,
    llm: ChatOpenAI
) -> Tuple[QueryIntent, Dict[str, Any]]:
    """
    Classify user query intent using LLM.

    Args:
        query: User query string
        llm: ChatOpenAI instance for classification

    Returns:
        Tuple of (QueryIntent, metadata_dict)

        metadata_dict contains:
            - intent: Intent enum value
            - reasoning: Why this intent was chosen
            - raw_classification: Raw LLM response
            - query_length: Length of query string
    """
    # Classification prompt with clear examples
    prompt = f"""You are a query intent classifier for a campus information kiosk.

Classify the user's query into ONE category:

1. CAMPUS - Questions about Columban College, Inc. campus:
   - Campus facilities, services, policies, hours, locations
   - Examples: "library hours?", "where is parking?", "dining hall menu?"

2. GENERAL - General knowledge not requiring campus documents:
   - Math calculations, general facts, definitions, greetings
   - Examples: "what is 15 * 23?", "hello", "capital of France?", "what is photosynthesis?"

3. AMBIGUOUS - Unclear or vague questions:
   - Questions that could be either campus or general
   - Questions needing more context
   - Examples: "hours", "services", "help"

User Query: "{query}"

Respond with ONLY one word: CAMPUS, GENERAL, or AMBIGUOUS"""

    # Call LLM for classification
    response = llm.invoke(prompt)
    classification = response.content.strip().upper()

    # Parse classification result
    if "CAMPUS" in classification:
        intent = QueryIntent.CAMPUS
        reasoning = "Query is about campus-specific information"
    elif "GENERAL" in classification:
        intent = QueryIntent.GENERAL
        reasoning = "Query is general knowledge, not campus-specific"
    elif "AMBIGUOUS" in classification:
        intent = QueryIntent.AMBIGUOUS
        reasoning = "Query intent is unclear"
    else:
        # Default to CAMPUS for safety (never risk answering campus questions in general mode)
        intent = QueryIntent.CAMPUS
        reasoning = "Classification unclear, defaulting to campus mode for safety"

    # Build metadata dictionary (following confidence_scorer.py pattern)
    metadata = {
        "intent": intent.value,
        "reasoning": reasoning,
        "raw_classification": classification,
        "query_length": len(query)
    }

    return intent, metadata


# ==============================================================================
# SAFETY CHECKS
# ==============================================================================

def safety_check_general_mode(query: str) -> Dict[str, Any]:
    """
    Safety check: Prevent general mode from answering campus questions.

    Uses keyword matching as a secondary safety layer to catch any
    campus questions that might have been misclassified as general.

    Args:
        query: User query string

    Returns:
        Dictionary with safety check results:
            - is_safe: True if safe for general mode, False if should redirect
            - campus_keywords_found: List of campus keywords detected
            - reason: Explanation of the safety decision
    """
    query_lower = query.lower()
    matches = [kw for kw in CAMPUS_KEYWORDS if kw in query_lower]

    return {
        "is_safe": len(matches) == 0,
        "campus_keywords_found": matches,
        "reason": "Possible campus question detected" if matches else "Safe for general mode"
    }


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def format_intent_display(intent: QueryIntent, metadata: Dict[str, Any]) -> str:
    """
    Format intent classification for display/debugging.

    Args:
        intent: Classified intent
        metadata: Classification metadata

    Returns:
        Formatted string for display
    """
    output = f"Intent: {intent.value.upper()}"
    output += f"\nReasoning: {metadata['reasoning']}"
    output += f"\nRaw Classification: {metadata['raw_classification']}"

    return output
