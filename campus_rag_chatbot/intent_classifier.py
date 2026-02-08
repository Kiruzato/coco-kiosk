"""
Intent Classifier Module - Phase 6 + Phase 8
=============================================
This module classifies user query intent to enable dual-mode answering:
- Campus queries → RAG pipeline with campus documents
- General queries → Direct LLM without retrieval
- Ambiguous queries → Ask for clarification
- Directory queries → Strict location/wayfinding with high confidence (Phase 8)

Intent classification uses the existing LLM (gpt-4o-mini) with a structured prompt.
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

# Patterns that indicate a location/directory query
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


def is_directory_query(query: str) -> bool:
    """
    Detect if query is asking for location/directory information.

    Phase 8: Uses lightweight regex patterns to identify wayfinding questions
    before LLM classification. This enables stricter answering policies for
    location queries.

    Args:
        query: User query string

    Returns:
        True if the query matches directory/location patterns
    """
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in DIRECTORY_PATTERNS)


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
