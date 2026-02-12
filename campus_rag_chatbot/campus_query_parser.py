"""
Campus Query Parser
===================
Unified parser for campus location queries with filter extraction.

Phase 48: Unified Query Parser

Provides:
- is_campus_query(): Detect if a query is a campus/location query
- CampusQueryParser: Parse queries into StructuredQuery objects
- Filter extraction for building, floor, room type, department

Supports all 5 query intents:
- LOCATE_SINGLE: "Where is SP303?", "Where is the library?"
- LOCATE_MULTIPLE: "Show all classrooms", "Where are the restrooms?"
- NEAREST: "What's the nearest restroom?", "Closest clinic to SP303"
- COUNT: "How many offices?", "Number of labs in A Building"
- LIST: "List all departments", "Show buildings"
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from .campus_schema import RoomType, FloorLevel
    from .structured_query import (
        StructuredQuery, QueryIntent, QueryFilter,
        FilterField, FilterOperator,
        single_entity_query, multi_entity_query, nearest_query, count_query, list_query
    )
except ImportError:
    from campus_schema import RoomType, FloorLevel
    from structured_query import (
        StructuredQuery, QueryIntent, QueryFilter,
        FilterField, FilterOperator,
        single_entity_query, multi_entity_query, nearest_query, count_query, list_query
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Query Detection Patterns
# =============================================================================

# Single-entity location patterns (existing directory patterns)
LOCATE_SINGLE_PATTERNS = [
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

# Multi-entity enumeration patterns
LOCATE_MULTIPLE_PATTERNS = [
    r"\bshow all\b",
    r"\blist all\b",
    r"\bwhat are the\b",
    r"\bwhat are all\b",
    r"\bwhere are the\b",
    r"\bwhere are all\b",
    r"\bshow me all\b",
    r"\bshow me the\b",
    r"\ball the\s+\w+s\b",  # "all the classrooms"
]

# Nearest/proximity patterns
NEAREST_PATTERNS = [
    r"\bnearest\b",
    r"\bclosest\b",
    r"\bnearby\b",
    r"\bnear here\b",
    r"\baround here\b",
    r"\bclose to\b",
    r"\bnear\s+(?:the\s+)?(\w+)\b",
]

# Count/aggregation patterns
COUNT_PATTERNS = [
    r"\bhow many\b",
    r"\bcount\b",
    r"\bnumber of\b",
    r"\btotal\s+(?:number\s+)?of\b",
]

# List patterns (explicit list request)
LIST_PATTERNS = [
    r"^list\b",
    r"\blist the\b",
    r"\bshow departments\b",
    r"\bshow buildings\b",
    r"\bshow campuses\b",
    r"\bwhat departments\b",
    r"\bwhat buildings\b",
]

# Room type keywords (plural and singular)
ROOM_TYPE_KEYWORDS = {
    # Classrooms
    "classrooms": RoomType.CLASSROOM,
    "classroom": RoomType.CLASSROOM,
    "class rooms": RoomType.CLASSROOM,
    "lecture rooms": RoomType.CLASSROOM,
    "lecture halls": RoomType.CLASSROOM,

    # Offices
    "offices": RoomType.OFFICE,
    "office": RoomType.OFFICE,

    # Laboratories
    "laboratories": RoomType.LABORATORY,
    "labs": RoomType.LABORATORY,
    "lab": RoomType.LABORATORY,
    "computer labs": RoomType.LABORATORY,
    "science labs": RoomType.LABORATORY,

    # Restrooms
    "restrooms": RoomType.RESTROOM,
    "restroom": RoomType.RESTROOM,
    "comfort rooms": RoomType.RESTROOM,
    "comfort room": RoomType.RESTROOM,
    "cr": RoomType.RESTROOM,
    "crs": RoomType.RESTROOM,
    "bathrooms": RoomType.RESTROOM,
    "bathroom": RoomType.RESTROOM,
    "toilets": RoomType.RESTROOM,
    "toilet": RoomType.RESTROOM,

    # Conference rooms
    "conference rooms": RoomType.CONFERENCE,
    "conference room": RoomType.CONFERENCE,
    "meeting rooms": RoomType.CONFERENCE,
    "meeting room": RoomType.CONFERENCE,

    # Facilities
    "canteen": RoomType.FACILITY,
    "canteens": RoomType.FACILITY,
    "cafeteria": RoomType.FACILITY,
    "gym": RoomType.FACILITY,
    "gymnasium": RoomType.FACILITY,
    "clinic": RoomType.FACILITY,
    "clinics": RoomType.FACILITY,
    "chapel": RoomType.FACILITY,
    "auditorium": RoomType.FACILITY,
    "court": RoomType.FACILITY,
    "courts": RoomType.FACILITY,

    # Library
    "library": RoomType.LIBRARY,
    "libraries": RoomType.LIBRARY,

    # Utility
    "storage": RoomType.STORAGE,
    "storage rooms": RoomType.STORAGE,
}

# Floor keywords
FLOOR_KEYWORDS = {
    "ground floor": FloorLevel.GROUND,
    "ground": FloorLevel.GROUND,
    "gf": FloorLevel.GROUND,
    "g/f": FloorLevel.GROUND,
    "first floor": FloorLevel.GROUND,  # Some buildings

    "second floor": FloorLevel.SECOND,
    "2nd floor": FloorLevel.SECOND,
    "2nd": FloorLevel.SECOND,
    "2f": FloorLevel.SECOND,

    "third floor": FloorLevel.THIRD,
    "3rd floor": FloorLevel.THIRD,
    "3rd": FloorLevel.THIRD,
    "3f": FloorLevel.THIRD,

    "fourth floor": FloorLevel.FOURTH,
    "4th floor": FloorLevel.FOURTH,
    "4th": FloorLevel.FOURTH,
    "4f": FloorLevel.FOURTH,

    "fifth floor": FloorLevel.FIFTH,
    "5th floor": FloorLevel.FIFTH,
    "5th": FloorLevel.FIFTH,
    "5f": FloorLevel.FIFTH,
}

# Building patterns
BUILDING_PATTERNS = [
    r"\bin\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+building\b",
    r"\bin\s+building\s+([A-Za-z])\b",
    r"\bin\s+([A-Za-z])\s+building\b",
    r"\bof\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+building\b",
    r"\bat\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+building\b",
    r"\b(st\.?\s*(?:augustine|patrick|agatha))\b",  # St. Augustine, St. Patrick, St. Agatha
]

# Department patterns
DEPARTMENT_PATTERNS = [
    r"\b(?:of|in|from)\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+department\b",
    r"\b(cba|coe|cas|ccs|ced|chs)\b",  # Common department abbreviations
    r"\b(college\s+of\s+[A-Za-z]+(?:\s+[A-Za-z]+)*)\b",
    r"\b(basic\s+education)\b",
]


# =============================================================================
# Detection Functions
# =============================================================================

def is_campus_query(query: str) -> bool:
    """
    Detect if a query is a campus/location query.

    This is the unified detection function that replaces:
    - is_directory_query()
    - is_structured_campus_query()

    Args:
        query: User query string

    Returns:
        True if the query is about campus locations
    """
    query_lower = query.lower().strip()

    # Check all pattern groups
    all_patterns = (
        LOCATE_SINGLE_PATTERNS +
        LOCATE_MULTIPLE_PATTERNS +
        NEAREST_PATTERNS +
        COUNT_PATTERNS +
        LIST_PATTERNS
    )

    for pattern in all_patterns:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return True

    # Check for room type keywords (even without location prefix)
    for keyword in ROOM_TYPE_KEYWORDS:
        if keyword in query_lower:
            # Must have some location-related context
            if any(word in query_lower for word in ["where", "show", "list", "find", "all", "how many", "nearest"]):
                return True

    return False


def detect_intent(query: str) -> QueryIntent:
    """
    Detect the primary intent of a campus query.

    Args:
        query: User query string

    Returns:
        QueryIntent enum value
    """
    query_lower = query.lower().strip()

    # Check NEAREST first (highest priority)
    for pattern in NEAREST_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryIntent.NEAREST

    # Check COUNT
    for pattern in COUNT_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryIntent.COUNT

    # Check LIST (explicit list request)
    for pattern in LIST_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryIntent.LIST

    # Check LOCATE_MULTIPLE
    for pattern in LOCATE_MULTIPLE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryIntent.LOCATE_MULTIPLE

    # Check LOCATE_SINGLE (default for location queries)
    for pattern in LOCATE_SINGLE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return QueryIntent.LOCATE_SINGLE

    return QueryIntent.UNKNOWN


# =============================================================================
# Filter Extraction
# =============================================================================

def extract_room_type(query: str) -> Optional[Tuple[RoomType, str]]:
    """
    Extract room type from query.

    Args:
        query: User query string

    Returns:
        Tuple of (RoomType, matched_text) or None
    """
    query_lower = query.lower()

    # Sort by length (longer matches first) to avoid partial matches
    sorted_keywords = sorted(ROOM_TYPE_KEYWORDS.keys(), key=len, reverse=True)

    for keyword in sorted_keywords:
        if keyword in query_lower:
            return (ROOM_TYPE_KEYWORDS[keyword], keyword)

    return None


def extract_floor_level(query: str) -> Optional[Tuple[FloorLevel, str]]:
    """
    Extract floor level from query.

    Args:
        query: User query string

    Returns:
        Tuple of (FloorLevel, matched_text) or None
    """
    query_lower = query.lower()

    # Check "on X floor" pattern
    floor_pattern = r"\bon\s+(?:the\s+)?(.+?)\s*(?:floor)?\b"
    match = re.search(floor_pattern, query_lower)
    if match:
        floor_text = match.group(1).strip()
        # Try to match floor keywords
        for keyword, level in FLOOR_KEYWORDS.items():
            if keyword in floor_text or floor_text in keyword:
                return (level, match.group(0))

    # Direct keyword match
    sorted_keywords = sorted(FLOOR_KEYWORDS.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in query_lower:
            return (FLOOR_KEYWORDS[keyword], keyword)

    return None


def extract_building(query: str) -> Optional[Tuple[str, str]]:
    """
    Extract building name from query.

    Args:
        query: User query string

    Returns:
        Tuple of (building_name, matched_text) or None
    """
    query_lower = query.lower()

    for pattern in BUILDING_PATTERNS:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            building_name = match.group(1).strip()
            return (building_name, match.group(0))

    # Check for single-letter building references
    single_letter = re.search(r"\b([a-h])\s+building\b", query_lower)
    if single_letter:
        return (single_letter.group(1).upper() + " Building", single_letter.group(0))

    return None


def extract_department(query: str) -> Optional[Tuple[str, str]]:
    """
    Extract department from query.

    Args:
        query: User query string

    Returns:
        Tuple of (department_name, matched_text) or None
    """
    query_lower = query.lower()

    for pattern in DEPARTMENT_PATTERNS:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            dept_name = match.group(1).strip()
            return (dept_name, match.group(0))

    return None


def extract_target_entity(query: str) -> Optional[str]:
    """
    Extract the target entity name from a single-entity query.

    Args:
        query: User query string (e.g., "Where is the library?")

    Returns:
        Entity name/alias or None
    """
    query_lower = query.lower().strip()

    # Patterns to extract subject
    patterns = [
        r"where is (?:the\s+)?(.+?)\??$",
        r"where's (?:the\s+)?(.+?)\??$",
        r"where can i find (?:the\s+)?(.+?)\??$",
        r"location of (?:the\s+)?(.+?)\??$",
        r"how do i get to (?:the\s+)?(.+?)\??$",
        r"how to get to (?:the\s+)?(.+?)\??$",
        r"directions to (?:the\s+)?(.+?)\??$",
        r"find (?:the\s+)?(.+?)\??$",
        r"looking for (?:the\s+)?(.+?)\??$",
        r"locate (?:the\s+)?(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            target = match.group(1).strip()
            # Remove trailing punctuation
            target = re.sub(r'[?!.,;:]+$', '', target).strip()
            if target:
                return target

    return None


def extract_reference_entity(query: str) -> Optional[str]:
    """
    Extract reference entity for NEAREST queries.

    Args:
        query: User query string (e.g., "nearest restroom to SP303")

    Returns:
        Reference entity name or None
    """
    query_lower = query.lower().strip()

    patterns = [
        r"(?:nearest|closest|nearby)\s+\w+\s+(?:to|from|near)\s+(?:the\s+)?(.+?)\??$",
        r"(?:to|from|near)\s+(?:the\s+)?(.+?)\??$",
        r"close to (?:the\s+)?(.+?)\??$",
    ]

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            ref = match.group(1).strip()
            ref = re.sub(r'[?!.,;:]+$', '', ref).strip()
            if ref:
                return ref

    return None


# =============================================================================
# Main Parser Class
# =============================================================================

class CampusQueryParser:
    """
    Unified parser for campus location queries.

    Parses natural language queries into StructuredQuery objects
    with extracted intents and filters.
    """

    def __init__(self, entity_registry=None):
        """
        Initialize parser.

        Args:
            entity_registry: Optional EntityRegistry for entity validation
        """
        self.entity_registry = entity_registry

    def parse(self, query: str) -> StructuredQuery:
        """
        Parse a query into a StructuredQuery.

        Args:
            query: User query string

        Returns:
            StructuredQuery object
        """
        query = query.strip()
        query_lower = query.lower()

        # Detect intent
        intent = detect_intent(query)

        if intent == QueryIntent.UNKNOWN:
            return StructuredQuery(
                raw_query=query,
                intent=QueryIntent.UNKNOWN,
                confidence=0.0,
                parse_method="failed"
            )

        # Extract filters
        filters = self._extract_filters(query)

        # Build query based on intent
        if intent == QueryIntent.LOCATE_SINGLE:
            return self._parse_locate_single(query, filters)

        elif intent == QueryIntent.LOCATE_MULTIPLE:
            return self._parse_locate_multiple(query, filters)

        elif intent == QueryIntent.NEAREST:
            return self._parse_nearest(query, filters)

        elif intent == QueryIntent.COUNT:
            return self._parse_count(query, filters)

        elif intent == QueryIntent.LIST:
            return self._parse_list(query, filters)

        return StructuredQuery(
            raw_query=query,
            intent=intent,
            filters=filters,
            confidence=0.5,
            parse_method="fallback"
        )

    def _extract_filters(self, query: str) -> List[QueryFilter]:
        """Extract all filters from a query."""
        filters = []

        # Extract room type
        room_type_result = extract_room_type(query)
        if room_type_result:
            room_type, raw_text = room_type_result
            filters.append(QueryFilter(
                field=FilterField.ROOM_TYPE,
                operator=FilterOperator.EQUALS,
                value=room_type,
                raw_text=raw_text
            ))

        # Extract floor level
        floor_result = extract_floor_level(query)
        if floor_result:
            floor_level, raw_text = floor_result
            filters.append(QueryFilter(
                field=FilterField.FLOOR_LEVEL,
                operator=FilterOperator.EQUALS,
                value=floor_level,
                raw_text=raw_text
            ))

        # Extract building
        building_result = extract_building(query)
        if building_result:
            building_name, raw_text = building_result
            filters.append(QueryFilter(
                field=FilterField.BUILDING,
                operator=FilterOperator.EQUALS,
                value=building_name,
                raw_text=raw_text
            ))

        # Extract department
        dept_result = extract_department(query)
        if dept_result:
            dept_name, raw_text = dept_result
            filters.append(QueryFilter(
                field=FilterField.DEPARTMENT,
                operator=FilterOperator.EQUALS,
                value=dept_name,
                raw_text=raw_text
            ))

        return filters

    def _parse_locate_single(self, query: str, filters: List[QueryFilter]) -> StructuredQuery:
        """Parse a LOCATE_SINGLE query."""
        target = extract_target_entity(query)

        # If we have a room type filter but no specific target,
        # this might be LOCATE_MULTIPLE instead
        if not target and filters:
            room_type_filter = next((f for f in filters if f.field == FilterField.ROOM_TYPE), None)
            if room_type_filter:
                return self._parse_locate_multiple(query, filters)

        return StructuredQuery(
            raw_query=query,
            intent=QueryIntent.LOCATE_SINGLE,
            target_entity=target,
            filters=filters,
            confidence=0.95 if target else 0.5,
            parse_method="pattern"
        )

    def _parse_locate_multiple(self, query: str, filters: List[QueryFilter]) -> StructuredQuery:
        """Parse a LOCATE_MULTIPLE query."""
        # Determine target type from filters
        room_type_filter = next((f for f in filters if f.field == FilterField.ROOM_TYPE), None)
        target_type = room_type_filter.value.value if room_type_filter else None

        return StructuredQuery(
            raw_query=query,
            intent=QueryIntent.LOCATE_MULTIPLE,
            target_type=target_type,
            filters=filters,
            confidence=0.9 if filters else 0.6,
            parse_method="pattern"
        )

    def _parse_nearest(self, query: str, filters: List[QueryFilter]) -> StructuredQuery:
        """Parse a NEAREST query."""
        # Extract target type (what we're looking for)
        room_type_result = extract_room_type(query)
        target_type = room_type_result[0].value if room_type_result else None

        # Extract reference entity (where we're searching from)
        reference = extract_reference_entity(query)

        return StructuredQuery(
            raw_query=query,
            intent=QueryIntent.NEAREST,
            target_type=target_type,
            reference_entity=reference,
            filters=filters,
            confidence=0.9 if target_type else 0.6,
            parse_method="pattern"
        )

    def _parse_count(self, query: str, filters: List[QueryFilter]) -> StructuredQuery:
        """Parse a COUNT query."""
        room_type_filter = next((f for f in filters if f.field == FilterField.ROOM_TYPE), None)
        target_type = room_type_filter.value.value if room_type_filter else None

        return StructuredQuery(
            raw_query=query,
            intent=QueryIntent.COUNT,
            target_type=target_type,
            filters=filters,
            confidence=0.9 if filters else 0.6,
            parse_method="pattern"
        )

    def _parse_list(self, query: str, filters: List[QueryFilter]) -> StructuredQuery:
        """Parse a LIST query."""
        query_lower = query.lower()

        # Determine what to list
        target_type = None
        if "department" in query_lower:
            target_type = "department"
        elif "building" in query_lower:
            target_type = "building"
        elif "campus" in query_lower:
            target_type = "campus"
        else:
            # Check for room type
            room_type_filter = next((f for f in filters if f.field == FilterField.ROOM_TYPE), None)
            if room_type_filter:
                target_type = room_type_filter.value.value

        return StructuredQuery(
            raw_query=query,
            intent=QueryIntent.LIST,
            target_type=target_type,
            filters=filters,
            confidence=0.85,
            parse_method="pattern"
        )


# =============================================================================
# Convenience Functions
# =============================================================================

# Singleton parser instance
_parser_instance: Optional[CampusQueryParser] = None


def get_parser(entity_registry=None) -> CampusQueryParser:
    """Get or create the singleton parser."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = CampusQueryParser(entity_registry)
    return _parser_instance


def parse_campus_query(query: str) -> StructuredQuery:
    """
    Parse a campus query (convenience function).

    Args:
        query: User query string

    Returns:
        StructuredQuery object
    """
    return get_parser().parse(query)
