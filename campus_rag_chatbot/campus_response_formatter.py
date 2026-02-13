"""
Campus Response Formatter
=========================
Formats QueryResult objects into natural language responses.

Phase 49: Query Engine + Structural Proximity
Phase 53: Schema Alignment (outdoor location formatting)

Provides:
- CampusResponseFormatter: Format results for presentation
- Template-based response generation (deterministic)
- LLM-free formatting for all query types
- Outdoor location formatting (Phase 53)
"""

import logging
from typing import List, Optional, Any

try:
    from .campus_schema import Room, Building, Campus, OutdoorLocation, RoomType, FloorLevel
    from .structured_query import StructuredQuery, QueryIntent, QueryResult, FilterField
except ImportError:
    from campus_schema import Room, Building, Campus, OutdoorLocation, RoomType, FloorLevel
    from structured_query import StructuredQuery, QueryIntent, QueryResult, FilterField

logger = logging.getLogger(__name__)


class CampusResponseFormatter:
    """
    Formats query results into natural language responses.

    All formatting is template-based and deterministic.
    No LLM calls - facts come directly from the query result.
    """

    def __init__(self):
        """Initialize formatter."""
        pass

    def format(self, result: QueryResult) -> str:
        """
        Format a QueryResult into a natural language response.

        Args:
            result: QueryResult from executor

        Returns:
            Formatted response string
        """
        if not result.success:
            return self._format_error(result)

        query = result.query

        if query.intent == QueryIntent.LOCATE_SINGLE:
            return self._format_locate_single(result)

        elif query.intent == QueryIntent.LOCATE_MULTIPLE:
            return self._format_locate_multiple(result)

        elif query.intent == QueryIntent.NEAREST:
            return self._format_nearest(result)

        elif query.intent == QueryIntent.COUNT:
            return self._format_count(result)

        elif query.intent == QueryIntent.LIST:
            return self._format_list(result)

        return self._format_generic(result)

    def _format_error(self, result: QueryResult) -> str:
        """Format an error result."""
        if result.error:
            return f"I couldn't process that request: {result.error}"
        return "I couldn't process that request."

    def _format_locate_single(self, result: QueryResult) -> str:
        """Format a LOCATE_SINGLE result."""
        if result.is_empty():
            target = result.query.target_entity or "that location"
            return f"I don't have information about '{target}' in my directory. Please check with the campus information desk for assistance."

        entity = result.entities[0]
        entity_type = result.metadata.get("entity_type", "room")

        if entity_type == "building":
            return self._format_building(entity)
        elif entity_type == "campus":
            return self._format_campus(entity)
        elif entity_type == "outdoor":
            return self._format_outdoor_location(entity)
        else:
            return self._format_room(entity)

    def _format_room(self, room: Room) -> str:
        """Format a single room location."""
        parts = [f"{room.canonical_name} is located"]

        # Building and floor
        building_name = room.original_building_str or room.building_id.replace("_", " ").title()
        floor_name = room.original_floor_str or room.floor_level.display_name()

        parts.append(f"in {building_name}, {floor_name}")

        # Room number
        if room.room_number:
            parts.append(f"(Room {room.room_number})")

        response = " ".join(parts) + "."

        # Landmarks
        if room.landmarks:
            response += f" {room.landmarks}"

        return response

    def _format_building(self, building: Building) -> str:
        """Format a building location."""
        campus = building.campus_id.replace("_", " ").title()
        floors = len(building.floor_ids)

        response = f"{building.name} is located on {campus}."
        if floors > 0:
            response += f" It has {floors} floor(s)."

        return response

    def _format_campus(self, campus: Campus) -> str:
        """Format a campus."""
        buildings = len(campus.building_ids)
        response = f"{campus.name} has {buildings} building(s)."
        return response

    def _format_outdoor_location(self, location: OutdoorLocation) -> str:
        """
        Format an outdoor location (Phase 53).

        Args:
            location: OutdoorLocation entity

        Returns:
            Formatted response string
        """
        # Get campus name
        campus_name = location.campus_id.replace("_", " ").title()

        response = f"{location.canonical_name} is an outdoor area on {campus_name}."

        # Add tags description
        if location.tags:
            tag_desc = ", ".join(location.tags[:3])  # First 3 tags
            response += f" It is a {tag_desc} area."

        # Add landmarks
        if location.landmarks:
            response += f" {location.landmarks}"

        # Add description
        if location.description:
            response += f" {location.description}"

        return response

    def _format_locate_multiple(self, result: QueryResult) -> str:
        """Format a LOCATE_MULTIPLE result."""
        if result.is_empty():
            return self._format_no_results(result)

        rooms = result.entities
        count = len(rooms)

        # Build header
        header = self._build_result_header(result.query, count)

        # Format list
        if count <= 10:
            room_list = self._format_room_list(rooms)
            return f"{header}\n\n{room_list}"
        else:
            # Show first 10 with note
            room_list = self._format_room_list(rooms[:10])
            return f"{header}\n\n{room_list}\n\n...and {count - 10} more."

    def _format_nearest(self, result: QueryResult) -> str:
        """Format a NEAREST result."""
        if result.is_empty():
            target_type = result.query.target_type or "location"
            ref = result.query.reference_entity
            if ref:
                return f"I couldn't find any {target_type}s near {ref}."
            return f"I couldn't find any {target_type}s."

        # Check if no reference was provided
        if result.metadata.get("no_reference"):
            return result.message or self._format_locate_multiple(result)

        rooms = result.entities
        first_room = rooms[0]
        ref_name = result.metadata.get("reference_name", result.query.reference_entity)
        tier = result.metadata.get("proximity_tier", "nearby")

        # Format proximity description
        proximity_desc = self._format_proximity_tier(tier)

        response = f"The nearest {first_room.room_type.value} to {ref_name} is {first_room.canonical_name}"

        # Add location details
        building_name = first_room.original_building_str or first_room.building_id.replace("_", " ").title()
        floor_name = first_room.original_floor_str or first_room.floor_level.display_name()

        response += f", located {proximity_desc} in {building_name}, {floor_name}"

        if first_room.room_number:
            response += f" (Room {first_room.room_number})"

        response += "."

        # Add alternatives if available
        if len(rooms) > 1:
            alt_names = [r.canonical_name for r in rooms[1:3]]
            response += f" Other nearby options: {', '.join(alt_names)}."

        return response

    def _format_count(self, result: QueryResult) -> str:
        """Format a COUNT result."""
        count = result.count or 0
        desc = result.metadata.get("count_description", "rooms")

        # Handle irregular plurals for singular form
        def singularize(word):
            if word.endswith("ies"):
                return word[:-3] + "y"  # laboratories -> laboratory
            return word.rstrip("s")

        if count == 0:
            return f"There are no {desc} matching your criteria."
        elif count == 1:
            return f"There is 1 {singularize(desc)} matching your criteria."
        else:
            return f"There are {count} {desc} matching your criteria."

    def _format_list(self, result: QueryResult) -> str:
        """Format a LIST result."""
        if result.is_empty():
            return self._format_no_results(result)

        entity_type = result.metadata.get("entity_type", "item")
        entities = result.entities
        count = len(entities)

        if entity_type == "department":
            header = f"Departments ({count}):"
            items = [f"  - {dept}" for dept in entities]
            return f"{header}\n" + "\n".join(items)

        elif entity_type == "building":
            header = f"Buildings ({count}):"
            items = []
            for building in entities:
                campus = building.campus_id.replace("_", " ").title()
                items.append(f"  - {building.name} ({campus})")
            return f"{header}\n" + "\n".join(items)

        elif entity_type == "campus":
            header = f"Campuses ({count}):"
            items = [f"  - {campus.name}" for campus in entities]
            return f"{header}\n" + "\n".join(items)

        else:
            # List rooms
            return self._format_locate_multiple(result)

    def _format_no_results(self, result: QueryResult) -> str:
        """Format a no-results response."""
        query = result.query

        # Build description of what was searched
        parts = []
        for f in query.filters:
            if f.field == FilterField.ROOM_TYPE:
                parts.append(f"{f.value.value}s")
            elif f.field == FilterField.BUILDING:
                parts.append(f"in {f.value}")
            elif f.field == FilterField.FLOOR_LEVEL:
                parts.append(f"on {f.value.display_name()}")

        if parts:
            desc = " ".join(parts)
            return f"I couldn't find any {desc}."

        return "I couldn't find any locations matching your criteria."

    def _format_generic(self, result: QueryResult) -> str:
        """Format a generic result."""
        if result.message:
            return result.message
        if result.entities:
            return f"Found {len(result.entities)} result(s)."
        return "No results found."

    def _build_result_header(self, query: StructuredQuery, count: int) -> str:
        """Build a header describing the results."""
        parts = []

        # Get room type
        room_type_filter = query.get_filter(FilterField.ROOM_TYPE)
        if room_type_filter:
            type_name = room_type_filter.value.value
            parts.append(f"{type_name}s")
        else:
            parts.append("locations")

        # Get location filters
        floor_filter = query.get_filter(FilterField.FLOOR_LEVEL)
        building_filter = query.get_filter(FilterField.BUILDING)

        location_parts = []
        if floor_filter:
            location_parts.append(f"on {floor_filter.value.display_name()}")
        if building_filter:
            location_parts.append(f"in {building_filter.value}")

        if location_parts:
            parts.append(" ".join(location_parts))

        desc = " ".join(parts)

        if count == 0:
            return f"No {desc} found."
        elif count == 1:
            return f"Found 1 {desc.rstrip('s')}:"
        else:
            return f"Found {count} {desc}:"

    def _format_room_list(self, rooms: List[Room]) -> str:
        """Format a list of rooms."""
        lines = []
        for i, room in enumerate(rooms, 1):
            building_name = room.original_building_str or room.building_id.replace("_", " ").title()
            floor_name = room.original_floor_str or room.floor_level.display_name()

            line = f"  {i}. {room.canonical_name}"
            if room.room_number:
                line += f" (Room {room.room_number})"
            line += f" - {building_name}, {floor_name}"

            lines.append(line)

        return "\n".join(lines)

    def _format_proximity_tier(self, tier: str) -> str:
        """Format a proximity tier description."""
        tier_descriptions = {
            "same_floor": "on the same floor",
            "same_building": "in the same building",
            "same_campus": "on the same campus",
            "different_campus": "on a different campus"
        }
        return tier_descriptions.get(tier, "nearby")


# =============================================================================
# Convenience Functions
# =============================================================================

_formatter_instance: Optional[CampusResponseFormatter] = None


def get_formatter() -> CampusResponseFormatter:
    """Get or create the singleton formatter."""
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = CampusResponseFormatter()
    return _formatter_instance


def format_query_result(result: QueryResult) -> str:
    """
    Format a query result (convenience function).

    Args:
        result: QueryResult to format

    Returns:
        Formatted response string
    """
    return get_formatter().format(result)
