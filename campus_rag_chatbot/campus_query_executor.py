"""
Campus Query Executor
=====================
Executes structured queries against the CampusQueryIndex.

Phase 49: Query Engine + Structural Proximity

Provides:
- CampusQueryExecutor: Execute StructuredQuery objects
- Index-based lookups for all 5 query intents
- Structural proximity search for NEAREST queries
- Filter intersection for multi-filter queries
"""

import logging
from typing import List, Optional

try:
    from .campus_schema import RoomType, FloorLevel, Room
    from .campus_index import CampusQueryIndex, get_campus_index
    from .structured_query import (
        StructuredQuery, QueryIntent, QueryResult, QueryFilter,
        FilterField, FilterOperator
    )
except ImportError:
    from campus_schema import RoomType, FloorLevel, Room
    from campus_index import CampusQueryIndex, get_campus_index
    from structured_query import (
        StructuredQuery, QueryIntent, QueryResult, QueryFilter,
        FilterField, FilterOperator
    )

logger = logging.getLogger(__name__)


class CampusQueryExecutor:
    """
    Executes structured queries against the CampusQueryIndex.

    All execution is deterministic - no LLM calls.
    Results are always grounded in the entity registry.
    """

    def __init__(self, index: CampusQueryIndex):
        """
        Initialize executor with a CampusQueryIndex.

        Args:
            index: CampusQueryIndex instance
        """
        self.index = index

    def execute(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a structured query.

        Args:
            query: Parsed StructuredQuery

        Returns:
            QueryResult with entities/count
        """
        if not query.is_valid():
            return QueryResult(
                query=query,
                success=False,
                error="Invalid query: missing required fields"
            )

        try:
            if query.intent == QueryIntent.LOCATE_SINGLE:
                return self._execute_locate_single(query)

            elif query.intent == QueryIntent.LOCATE_MULTIPLE:
                return self._execute_locate_multiple(query)

            elif query.intent == QueryIntent.NEAREST:
                return self._execute_nearest(query)

            elif query.intent == QueryIntent.COUNT:
                return self._execute_count(query)

            elif query.intent == QueryIntent.LIST:
                return self._execute_list(query)

            else:
                return QueryResult(
                    query=query,
                    success=False,
                    error=f"Unknown intent: {query.intent}"
                )

        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return QueryResult(
                query=query,
                success=False,
                error=str(e)
            )

    def _execute_locate_single(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a LOCATE_SINGLE query.

        Looks up a single entity by alias or ID.
        """
        target = query.target_entity
        if not target:
            return QueryResult(
                query=query,
                success=False,
                error="No target entity specified"
            )

        # Try room lookup first
        room = self.index.resolve_room(target)
        if room:
            return QueryResult(
                query=query,
                success=True,
                entities=[room],
                execution_mode="index_alias"
            )

        # Try building lookup
        building = self.index.resolve_building(target)
        if building:
            return QueryResult(
                query=query,
                success=True,
                entities=[building],
                execution_mode="index_building",
                metadata={"entity_type": "building"}
            )

        # Try campus lookup
        campus = self.index.resolve_campus(target)
        if campus:
            return QueryResult(
                query=query,
                success=True,
                entities=[campus],
                execution_mode="index_campus",
                metadata={"entity_type": "campus"}
            )

        # Not found
        return QueryResult(
            query=query,
            success=True,
            entities=[],
            execution_mode="index_miss",
            message=f"No location found matching '{target}'"
        )

    def _execute_locate_multiple(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a LOCATE_MULTIPLE query.

        Uses filter intersection to find matching rooms.
        """
        # Start with all active rooms
        all_room_ids = set(r.room_id for r in self.index.get_all_active_rooms())

        # Apply filters via intersection
        for filter in query.filters:
            matching_ids = self._get_matching_room_ids(filter)
            all_room_ids &= matching_ids

        # Get room objects
        rooms = [self.index.rooms[rid] for rid in all_room_ids if rid in self.index.rooms]

        # Sort by building, then floor, then room number
        rooms.sort(key=lambda r: (r.building_id, r.floor_level.value, r.room_number or ""))

        return QueryResult(
            query=query,
            success=True,
            entities=rooms,
            count=len(rooms),
            execution_mode="index_filter"
        )

    def _execute_nearest(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a NEAREST query using structural proximity.

        Tiers:
        0. Same Floor
        1. Same Building, Different Floor
        2. Same Campus, Different Building
        3. Different Campus
        """
        # Determine target room type
        target_type = None
        room_type_filter = query.get_filter(FilterField.ROOM_TYPE)
        if room_type_filter:
            target_type = room_type_filter.value
        elif query.target_type:
            target_type = RoomType.from_string(query.target_type)

        if not target_type or target_type == RoomType.UNKNOWN:
            return QueryResult(
                query=query,
                success=False,
                error="Could not determine target room type for nearest search"
            )

        # Resolve reference entity
        reference_room = None
        if query.reference_entity:
            reference_room = self.index.resolve_room(query.reference_entity)

        # If no reference, try to use a default location or return all of that type
        if not reference_room:
            # Without reference, just return all rooms of that type
            rooms = self.index.get_rooms_by_type(target_type)
            if rooms:
                return QueryResult(
                    query=query,
                    success=True,
                    entities=rooms[:5],  # Limit to 5
                    execution_mode="index_type",
                    metadata={"no_reference": True},
                    message=f"Found {len(rooms)} {target_type.value}(s). Specify a location for nearest search."
                )
            return QueryResult(
                query=query,
                success=True,
                entities=[],
                message=f"No {target_type.value}s found"
            )

        # Execute structural proximity search
        nearest_rooms = self.index.find_nearest(reference_room, target_type, limit=3)

        if nearest_rooms:
            # Determine proximity tier
            first_room = nearest_rooms[0]
            tier = self._determine_proximity_tier(reference_room, first_room)

            return QueryResult(
                query=query,
                success=True,
                entities=nearest_rooms,
                execution_mode="structural_proximity",
                metadata={
                    "reference": reference_room.room_id,
                    "reference_name": reference_room.canonical_name,
                    "proximity_tier": tier
                }
            )

        return QueryResult(
            query=query,
            success=True,
            entities=[],
            message=f"No {target_type.value}s found near {reference_room.canonical_name}"
        )

    def _execute_count(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a COUNT query.

        Returns the count of matching rooms.
        """
        # Use the same logic as LOCATE_MULTIPLE but return count
        all_room_ids = set(r.room_id for r in self.index.get_all_active_rooms())

        for filter in query.filters:
            matching_ids = self._get_matching_room_ids(filter)
            all_room_ids &= matching_ids

        count = len(all_room_ids)

        # Build description of what was counted
        count_desc = self._build_count_description(query.filters)

        return QueryResult(
            query=query,
            success=True,
            count=count,
            execution_mode="index_count",
            metadata={"count_description": count_desc}
        )

    def _execute_list(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a LIST query.

        Lists entities of a specific type.
        """
        target_type = query.target_type

        if target_type == "department":
            # List unique departments from rooms
            departments = set()
            for room in self.index.get_all_active_rooms():
                if room.department:
                    departments.add(room.department)
            departments = sorted(departments)

            return QueryResult(
                query=query,
                success=True,
                entities=list(departments),
                count=len(departments),
                execution_mode="index_aggregate",
                metadata={"entity_type": "department"}
            )

        elif target_type == "building":
            buildings = list(self.index.buildings.values())
            buildings.sort(key=lambda b: b.name)

            return QueryResult(
                query=query,
                success=True,
                entities=buildings,
                count=len(buildings),
                execution_mode="index_aggregate",
                metadata={"entity_type": "building"}
            )

        elif target_type == "campus":
            campuses = list(self.index.campuses.values())

            return QueryResult(
                query=query,
                success=True,
                entities=campuses,
                count=len(campuses),
                execution_mode="index_aggregate",
                metadata={"entity_type": "campus"}
            )

        else:
            # List rooms matching filters (same as LOCATE_MULTIPLE)
            return self._execute_locate_multiple(query)

    def _get_matching_room_ids(self, filter: QueryFilter) -> set:
        """
        Get room IDs matching a single filter.

        Args:
            filter: QueryFilter to apply

        Returns:
            Set of matching room IDs
        """
        if filter.field == FilterField.ROOM_TYPE:
            room_type = filter.value
            if isinstance(room_type, str):
                room_type = RoomType.from_string(room_type)
            return set(self.index.rooms_by_type.get(room_type, []))

        elif filter.field == FilterField.FLOOR_LEVEL:
            floor_level = filter.value
            if isinstance(floor_level, str):
                floor_level = FloorLevel.from_string(floor_level)

            # Collect rooms from all buildings at this floor level
            matching = set()
            for (building_id, level), room_ids in self.index.rooms_by_building_floor.items():
                if level == floor_level:
                    matching.update(room_ids)
            return matching

        elif filter.field == FilterField.BUILDING:
            building_name = filter.value
            # Try to resolve building
            building = self.index.resolve_building(building_name)
            if building:
                return set(self.index.rooms_by_building.get(building.building_id, []))

            # Try partial match on building ID
            building_upper = building_name.upper().replace(" ", "_")
            for building_id in self.index.buildings:
                if building_upper in building_id or building_id in building_upper:
                    return set(self.index.rooms_by_building.get(building_id, []))

            return set()

        elif filter.field == FilterField.CAMPUS:
            campus_name = filter.value
            campus = self.index.resolve_campus(campus_name)
            if campus:
                return set(self.index.rooms_by_campus.get(campus.campus_id, []))
            return set()

        elif filter.field == FilterField.DEPARTMENT:
            dept_name = filter.value.lower()
            # Scan rooms for department match
            matching = set()
            for room in self.index.rooms.values():
                if room.department and dept_name in room.department.lower():
                    matching.add(room.room_id)
            return matching

        return set()

    def _determine_proximity_tier(self, reference: Room, target: Room) -> str:
        """
        Determine the structural proximity tier between two rooms.
        """
        if reference.floor_id == target.floor_id:
            return "same_floor"
        elif reference.building_id == target.building_id:
            return "same_building"
        elif reference.campus_id == target.campus_id:
            return "same_campus"
        else:
            return "different_campus"

    def _build_count_description(self, filters: List[QueryFilter]) -> str:
        """Build a description of what was counted."""
        parts = []

        def pluralize(word):
            """Simple pluralization handling common cases."""
            if word.endswith("y"):
                return word[:-1] + "ies"  # laboratory -> laboratories
            return word + "s"

        for f in filters:
            if f.field == FilterField.ROOM_TYPE:
                parts.append(pluralize(f.value.value))
            elif f.field == FilterField.BUILDING:
                parts.append(f"in {f.value}")
            elif f.field == FilterField.FLOOR_LEVEL:
                parts.append(f"on {f.value.display_name()}")
            elif f.field == FilterField.CAMPUS:
                parts.append(f"at {f.value}")
            elif f.field == FilterField.DEPARTMENT:
                parts.append(f"in {f.value}")

        if parts:
            return " ".join(parts)
        return "rooms"


# =============================================================================
# Convenience Functions
# =============================================================================

_executor_instance: Optional[CampusQueryExecutor] = None


def get_executor(index: Optional[CampusQueryIndex] = None) -> CampusQueryExecutor:
    """
    Get or create the singleton executor.

    Args:
        index: CampusQueryIndex (required on first call)

    Returns:
        CampusQueryExecutor instance
    """
    global _executor_instance

    if _executor_instance is None:
        if index is None:
            raise ValueError("index required on first call")
        _executor_instance = CampusQueryExecutor(index)

    return _executor_instance


def execute_campus_query(query: StructuredQuery, index: CampusQueryIndex) -> QueryResult:
    """
    Execute a structured query (convenience function).

    Args:
        query: StructuredQuery to execute
        index: CampusQueryIndex to query against

    Returns:
        QueryResult
    """
    executor = CampusQueryExecutor(index)
    return executor.execute(query)
