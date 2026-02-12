"""
Structured Query Representation
===============================
Data structures for representing parsed campus queries.

Phase 48: Unified Query Parser

Provides:
- QueryIntent: Enum of query intents (LOCATE_SINGLE, LOCATE_MULTIPLE, NEAREST, COUNT, LIST)
- QueryFilter: Filter conditions extracted from queries
- StructuredQuery: Complete parsed query representation
- QueryResult: Result of executing a structured query
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from .campus_schema import RoomType, FloorLevel
except ImportError:
    from campus_schema import RoomType, FloorLevel


class QueryIntent(Enum):
    """
    Enumeration of campus query intents.

    Each intent maps to a specific execution strategy in the Campus Query Engine.
    """
    # Single-entity location queries
    LOCATE_SINGLE = "locate_single"      # "Where is SP303?", "Where is the library?"

    # Multi-entity enumeration queries
    LOCATE_MULTIPLE = "locate_multiple"  # "Show all classrooms", "Where are the restrooms?"

    # Structural proximity queries
    NEAREST = "nearest"                  # "What's the nearest restroom?", "Closest clinic to SP303"

    # Aggregation queries
    COUNT = "count"                      # "How many offices?", "Number of labs in A Building"

    # List/enumeration queries
    LIST = "list"                        # "List all departments", "Show buildings"

    # Unknown/fallback
    UNKNOWN = "unknown"                  # Could not determine intent


class FilterField(Enum):
    """
    Fields that can be filtered on in structured queries.
    """
    ROOM_TYPE = "room_type"
    FLOOR_LEVEL = "floor_level"
    BUILDING = "building"
    CAMPUS = "campus"
    DEPARTMENT = "department"


class FilterOperator(Enum):
    """
    Filter operators for query conditions.
    """
    EQUALS = "eq"           # Exact match
    IN = "in"               # Value in list
    CONTAINS = "contains"   # Substring match
    LIKE = "like"           # Fuzzy match


@dataclass
class QueryFilter:
    """
    A single filter condition extracted from a query.

    Example:
        "Show all classrooms on Ground Floor"
        -> [QueryFilter(field=ROOM_TYPE, operator=EQUALS, value=RoomType.CLASSROOM),
            QueryFilter(field=FLOOR_LEVEL, operator=EQUALS, value=FloorLevel.GROUND)]
    """
    field: FilterField
    operator: FilterOperator
    value: Any
    raw_text: str = ""  # Original text that produced this filter

    def matches(self, entity_value: Any) -> bool:
        """
        Check if an entity value matches this filter.

        Args:
            entity_value: Value from entity to check

        Returns:
            True if the value matches the filter
        """
        if self.operator == FilterOperator.EQUALS:
            return entity_value == self.value
        elif self.operator == FilterOperator.IN:
            return entity_value in self.value
        elif self.operator == FilterOperator.CONTAINS:
            if isinstance(entity_value, str) and isinstance(self.value, str):
                return self.value.lower() in entity_value.lower()
            return False
        elif self.operator == FilterOperator.LIKE:
            if isinstance(entity_value, str) and isinstance(self.value, str):
                return self.value.lower() in entity_value.lower() or entity_value.lower() in self.value.lower()
            return False
        return False


@dataclass
class StructuredQuery:
    """
    Complete parsed representation of a campus query.

    This is the output of the CampusQueryParser and input to the QueryExecutor.
    """
    # Original query
    raw_query: str

    # Detected intent
    intent: QueryIntent

    # Target entity for single-entity queries
    target_entity: Optional[str] = None

    # Target type for type-based queries (e.g., "room", "building", "floor")
    target_type: Optional[str] = None

    # Reference entity for NEAREST queries (e.g., "nearest restroom to SP303")
    reference_entity: Optional[str] = None

    # Filters extracted from the query
    filters: List[QueryFilter] = field(default_factory=list)

    # Parsing confidence (0.0 to 1.0)
    confidence: float = 0.0

    # How the query was parsed
    parse_method: str = "unknown"  # "pattern", "template", "semantic"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_filter(self, field: FilterField) -> bool:
        """Check if query has a filter for the given field."""
        return any(f.field == field for f in self.filters)

    def get_filter(self, field: FilterField) -> Optional[QueryFilter]:
        """Get the first filter for a given field."""
        for f in self.filters:
            if f.field == field:
                return f
        return None

    def get_filter_value(self, field: FilterField) -> Optional[Any]:
        """Get the value of the first filter for a given field."""
        f = self.get_filter(field)
        return f.value if f else None

    def is_valid(self) -> bool:
        """Check if the query is valid for execution."""
        if self.intent == QueryIntent.UNKNOWN:
            return False
        if self.intent == QueryIntent.LOCATE_SINGLE and not self.target_entity:
            return False
        return True

    def __str__(self) -> str:
        """Human-readable representation."""
        parts = [f"Intent: {self.intent.value}"]
        if self.target_entity:
            parts.append(f"Target: {self.target_entity}")
        if self.reference_entity:
            parts.append(f"Reference: {self.reference_entity}")
        if self.filters:
            filter_strs = [f"{f.field.value}={f.value}" for f in self.filters]
            parts.append(f"Filters: [{', '.join(filter_strs)}]")
        parts.append(f"Confidence: {self.confidence:.2f}")
        return " | ".join(parts)


@dataclass
class QueryResult:
    """
    Result of executing a structured query.
    """
    # The query that was executed
    query: StructuredQuery

    # Whether execution succeeded
    success: bool = True

    # Result entities (for LOCATE_SINGLE, LOCATE_MULTIPLE, NEAREST, LIST)
    entities: List[Any] = field(default_factory=list)

    # Count result (for COUNT queries)
    count: Optional[int] = None

    # Execution mode
    execution_mode: str = "index"  # "index", "scan", "hybrid"

    # Response message (pre-formatted)
    message: Optional[str] = None

    # Error message if failed
    error: Optional[str] = None

    # Execution metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if result has no entities."""
        return len(self.entities) == 0 and self.count in (None, 0)


# Convenience constructors

def single_entity_query(raw_query: str, target: str, confidence: float = 1.0) -> StructuredQuery:
    """Create a LOCATE_SINGLE query."""
    return StructuredQuery(
        raw_query=raw_query,
        intent=QueryIntent.LOCATE_SINGLE,
        target_entity=target,
        confidence=confidence,
        parse_method="pattern"
    )


def multi_entity_query(
    raw_query: str,
    filters: List[QueryFilter],
    confidence: float = 0.9
) -> StructuredQuery:
    """Create a LOCATE_MULTIPLE query."""
    return StructuredQuery(
        raw_query=raw_query,
        intent=QueryIntent.LOCATE_MULTIPLE,
        filters=filters,
        confidence=confidence,
        parse_method="pattern"
    )


def nearest_query(
    raw_query: str,
    target_type: str,
    reference: Optional[str] = None,
    confidence: float = 0.9
) -> StructuredQuery:
    """Create a NEAREST query."""
    return StructuredQuery(
        raw_query=raw_query,
        intent=QueryIntent.NEAREST,
        target_type=target_type,
        reference_entity=reference,
        confidence=confidence,
        parse_method="pattern"
    )


def count_query(
    raw_query: str,
    filters: List[QueryFilter],
    confidence: float = 0.9
) -> StructuredQuery:
    """Create a COUNT query."""
    return StructuredQuery(
        raw_query=raw_query,
        intent=QueryIntent.COUNT,
        filters=filters,
        confidence=confidence,
        parse_method="pattern"
    )


def list_query(
    raw_query: str,
    target_type: str,
    filters: Optional[List[QueryFilter]] = None,
    confidence: float = 0.9
) -> StructuredQuery:
    """Create a LIST query."""
    return StructuredQuery(
        raw_query=raw_query,
        intent=QueryIntent.LIST,
        target_type=target_type,
        filters=filters or [],
        confidence=confidence,
        parse_method="pattern"
    )
