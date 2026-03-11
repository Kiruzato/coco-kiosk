"""
Awards and Honors Extractor - Phase 27
======================================

Deterministic extraction of academic awards and honors from retrieved context.

No LLM usage - pure regex-based pattern matching.

Functions:
- is_awards_enumeration_query(): Intent detection (rule-based)
- extract_awards_from_text(): Extract award entities from text
- format_awards_list(): Format extracted awards into canonical response
"""

import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


# Intent detection patterns
ENUMERATION_TRIGGERS = [
    'what are',
    'list',
    'show',
    'all',
    'different',
    'types of',
    'kinds of',
    'tell me about',
    'enumerate'
]

AWARD_MARKERS = [
    'award',
    'awards',
    'honor',
    'honors',
    'recognition',
    'recognitions'
]

# Procedural patterns that indicate NOT an enumeration query
PROCEDURAL_PATTERNS = [
    'how to',
    'how do i',
    'how can i',
    'apply',
    'submit',
    'when is',
    'date',
    'deadline',
    'requirements for',
    'qualify',
    'get the',
    'receive the',
    'attain'
]


def is_awards_enumeration_query(query: str) -> bool:
    """
    Detect if query is requesting awards/honors enumeration.

    Rule-based detection (no ML):
    - Contains enumeration trigger: "what are", "list", "show", "all", etc.
    - Contains award marker: "award", "honors", "recognition"
    - Does NOT contain procedural patterns: "how to", "requirements for"

    Examples:
        >>> is_awards_enumeration_query("what are the academic awards")
        True
        >>> is_awards_enumeration_query("list all honors and awards")
        True
        >>> is_awards_enumeration_query("how do I get an award")
        False
        >>> is_awards_enumeration_query("requirements for dean's lister")
        False

    Args:
        query: User query string

    Returns:
        True if awards enumeration query, False otherwise
    """
    query_lower = query.lower()

    # Must have enumeration trigger
    has_trigger = any(trigger in query_lower for trigger in ENUMERATION_TRIGGERS)

    # Must have award marker
    has_marker = any(marker in query_lower for marker in AWARD_MARKERS)

    # Must NOT be a procedural query
    is_procedural = any(pattern in query_lower for pattern in PROCEDURAL_PATTERNS)

    result = has_trigger and has_marker and not is_procedural

    if result:
        logger.info(f"[PHASE27] Awards enumeration query detected: '{query}'")

    return result


def extract_awards_from_text(text: str) -> List[Dict[str, str]]:
    """
    Deterministically extract award entries from text.

    No LLM usage - pure regex-based extraction.

    Pattern detection:
    - Section numbered headers: "6. 4. 1 deans awards"
    - Award name followed by criteria: "leadership awards - scholastic standing..."
    - Recognizes common award categories

    Features:
    - Deduplication by normalized name
    - Preserves document order
    - Extracts criteria when available

    Args:
        text: Context text from retrieved chunks

    Returns:
        List of award dicts with:
        - name: Award name (normalized)
        - category: Award category
        - criteria: Eligibility criteria if found
        - raw_line: Original line for debugging
    """
    awards = []
    seen_names = set()  # For deduplication

    # Normalize text - handle line breaks and extra whitespace
    text = re.sub(r'\s+', ' ', text)

    # Known award names to look for (more precise matching)
    KNOWN_AWARDS = [
        (r"dean'?s?\s+awards?", "Dean's Award", "Academic"),
        (r"leadership\s+awards?", "Leadership Award", "Leadership"),
        (r"academic\s+performance\s+awards?", "Academic Performance Award", "Academic"),
        (r"community\s+service\s+awards?", "Community Service Award", "Service"),
        (r"st\.?\s*columban\s+community\s+service\s+awards?", "St. Columban Community Service Award", "Service"),
        (r"first\s+honors?", "First Honors", "Academic"),
        (r"second\s+honors?", "Second Honors", "Academic"),
        (r"third\s+honors?", "Third Honors", "Academic"),
        (r"dean'?s?\s+list(?:er)?", "Dean's Lister", "Academic"),
        (r"honorable\s+mention", "Honorable Mention", "Academic"),
        (r"academic\s+scholar", "Academic Scholar", "Academic"),
    ]

    # Match known awards only - use strict patterns
    for pattern, name, category in KNOWN_AWARDS:
        if re.search(pattern, text, re.IGNORECASE):
            name_key = name.lower()
            if name_key not in seen_names:
                seen_names.add(name_key)

                # Try to extract criteria for this award
                criteria = _extract_criteria_for_award(text, pattern)

                awards.append({
                    'name': name,
                    'category': category,
                    'criteria': criteria,
                    'section_num': '',
                    'raw_line': ''
                })

    # Sort: Academic first, then by name
    category_order = {'Academic': 0, 'Leadership': 1, 'Service': 2, 'Special': 3}
    awards.sort(key=lambda x: (category_order.get(x['category'], 4), x['name']))

    logger.info(f"[PHASE27] Extracted {len(awards)} awards from text")

    return awards


def _extract_criteria_for_award(text: str, award_pattern: str) -> str:
    """
    Try to extract criteria text following an award mention.
    """
    # Look for "award_name - criteria" or "award_name: criteria" pattern
    full_pattern = award_pattern + r'\s*[-–—:]\s*([^.;]{10,150})'
    match = re.search(full_pattern, text, re.IGNORECASE)
    if match:
        return _clean_criteria(match.group(1))
    return ""


def _normalize_award_name(name: str) -> str:
    """
    Normalize award name to title case.

    Examples:
        "deans awards" -> "Dean's Awards"
        "LEADERSHIP AWARD" -> "Leadership Award"
        "st. columban community service awards" -> "St. Columban Community Service Awards"
    """
    # Remove extra whitespace
    name = ' '.join(name.split())

    # Title case
    words = name.lower().split()
    normalized = []

    for i, word in enumerate(words):
        # Handle "deans" -> "Dean's"
        if word == 'deans':
            normalized.append("Dean's")
        # Handle "st." -> "St."
        elif word == 'st.' or word == 'st':
            normalized.append('St.')
        # Capitalize first letter of each word
        else:
            normalized.append(word.capitalize())

    return ' '.join(normalized)


def _detect_category(name: str) -> str:
    """
    Detect award category from name.

    Categories:
    - Academic Standing (dean's list, academic performance)
    - Leadership (leadership awards)
    - Service (community service, outreach)
    - Special (other awards)
    """
    name_lower = name.lower()

    if any(kw in name_lower for kw in ['dean', 'academic', 'scholar', 'performance']):
        return "Academic"
    elif 'leadership' in name_lower:
        return "Leadership"
    elif any(kw in name_lower for kw in ['service', 'community', 'outreach']):
        return "Service"
    else:
        return "Special"


def _clean_criteria(criteria: str) -> str:
    """
    Clean up criteria text.

    - Remove trailing page numbers
    - Remove incomplete sentences
    - Capitalize first letter
    """
    if not criteria:
        return ""

    # Remove trailing numbers (page numbers)
    criteria = re.sub(r'\s*\d+\s*$', '', criteria)

    # Remove trailing incomplete fragments
    criteria = re.sub(r'\s+(?:and|or|with)\s*$', '', criteria, flags=re.IGNORECASE)

    # Capitalize first letter
    if criteria:
        criteria = criteria[0].upper() + criteria[1:]

    return criteria.strip()


def format_awards_list(awards: List[Dict[str, str]]) -> str:
    """
    Format extracted awards into canonical response string.

    Output format:
        The academic awards and honors at Columban College are:

        **Academic:**
        1. Academic Performance Award - Consistent academic scholar for two consecutive semesters

        **Leadership:**
        2. Leadership Award - Active involvement in campus organizations

        ...

    Args:
        awards: List of award dicts from extract_awards_from_text()

    Returns:
        Formatted string ready for user display
    """
    if not awards:
        return "No awards found in the retrieved information."

    lines = ["The academic awards and honors at Columban College are:\n"]

    # Group by category
    categories = {}
    for award in awards:
        cat = award.get('category', 'Special')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(award)

    # Define category order
    category_order = ['Academic', 'Leadership', 'Service', 'Special']

    idx = 1
    for category in category_order:
        if category not in categories:
            continue

        cat_awards = categories[category]

        if len(categories) > 1:
            lines.append(f"\n**{category}:**")

        for award in cat_awards:
            name = award['name']
            criteria = award.get('criteria', '')

            if criteria:
                lines.append(f"{idx}. {name} - {criteria}")
            else:
                lines.append(f"{idx}. {name}")
            idx += 1

    return '\n'.join(lines)
