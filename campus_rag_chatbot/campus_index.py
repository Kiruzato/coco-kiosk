"""
Campus Query Index
==================
Pre-built indexes for O(1) structured queries in the Campus Query Engine.

Phase 47: Data Model Foundation

Provides:
- Primary indexes: campuses, buildings, floors, rooms by ID
- Alias indexes: alias -> entity_id mapping
- Relationship indexes: rooms_by_floor, rooms_by_building, rooms_by_type
- Structural proximity support: floor_level ordering
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from .campus_schema import (
        Campus, Building, Floor, Room, Department,
        RoomType, FloorLevel,
        generate_building_id, generate_floor_id, generate_campus_id,
        normalize_id
    )
except ImportError:
    from campus_schema import (
        Campus, Building, Floor, Room, Department,
        RoomType, FloorLevel,
        generate_building_id, generate_floor_id, generate_campus_id,
        normalize_id
    )

logger = logging.getLogger(__name__)


class CampusQueryIndex:
    """
    Pre-built indexes for O(1) campus queries.

    All indexes are built at load time from hierarchical JSON data.
    Supports both hierarchical (v2) and flat (v1) entity formats.
    """

    def __init__(self):
        # Primary indexes (entity_id -> entity)
        self.campuses: Dict[str, Campus] = {}
        self.buildings: Dict[str, Building] = {}
        self.floors: Dict[str, Floor] = {}
        self.rooms: Dict[str, Room] = {}
        self.departments: Dict[str, Department] = {}

        # Alias indexes (normalized alias -> entity_id)
        self.alias_to_room: Dict[str, str] = {}
        self.alias_to_building: Dict[str, str] = {}
        self.alias_to_campus: Dict[str, str] = {}
        self.alias_to_department: Dict[str, str] = {}

        # Relationship indexes (for filtered queries)
        self.rooms_by_floor: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_building: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_campus: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_type: Dict[RoomType, List[str]] = defaultdict(list)
        self.rooms_by_department: Dict[str, List[str]] = defaultdict(list)

        # Composite indexes
        self.rooms_by_building_floor: Dict[Tuple[str, FloorLevel], List[str]] = defaultdict(list)

        # Floors by building (for structural proximity)
        self.floors_by_building: Dict[str, List[str]] = defaultdict(list)
        self.buildings_by_campus: Dict[str, List[str]] = defaultdict(list)

        # Statistics
        self._stats = {
            "rooms": 0,
            "active_rooms": 0,
            "buildings": 0,
            "campuses": 0,
            "aliases": 0
        }

    def load_from_flat_entities(self, entities_json_path: str) -> bool:
        """
        Load index from flat v1.x directory_entities.json format.

        This is the primary loading method for existing data.

        Args:
            entities_json_path: Path to directory_entities.json

        Returns:
            True if successful, False otherwise
        """
        path = Path(entities_json_path)

        if not path.exists():
            logger.warning(f"Entity file not found: {entities_json_path}")
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entities = data.get('entities', [])

            # First pass: collect unique campuses, buildings, floors
            campus_names: Set[str] = set()
            building_names: Dict[str, str] = {}  # building_name -> campus_id
            floor_keys: Set[Tuple[str, str, str]] = set()  # (building_id, floor_str, campus_id)

            for entity in entities:
                campus_name = entity.get('campus', 'Main Campus')
                building_name = entity.get('building', 'Unknown Building')
                floor_str = entity.get('floor', 'Ground Floor')

                campus_names.add(campus_name)

                campus_id = generate_campus_id(campus_name)
                building_id = generate_building_id(building_name)

                building_names[building_name] = campus_id
                floor_keys.add((building_id, floor_str, campus_id))

            # Create Campus entities
            for campus_name in campus_names:
                campus_id = generate_campus_id(campus_name)
                campus = Campus(
                    campus_id=campus_id,
                    name=campus_name,
                    aliases=[campus_name.lower()]
                )
                self.campuses[campus_id] = campus
                self._index_campus_aliases(campus)

            # Create Building entities
            for building_name, campus_id in building_names.items():
                building_id = generate_building_id(building_name)

                # Generate aliases
                aliases = [building_name.lower()]
                # Add common variations
                name_lower = building_name.lower()
                if "building" in name_lower:
                    aliases.append(name_lower.replace(" building", ""))
                    aliases.append(name_lower.replace("building", "").strip())

                building = Building(
                    building_id=building_id,
                    name=building_name,
                    aliases=aliases,
                    campus_id=campus_id
                )
                self.buildings[building_id] = building
                self._index_building_aliases(building)

                # Add to campus
                if campus_id in self.campuses:
                    if building_id not in self.campuses[campus_id].building_ids:
                        self.campuses[campus_id].building_ids.append(building_id)

                # Add to buildings_by_campus index
                if building_id not in self.buildings_by_campus[campus_id]:
                    self.buildings_by_campus[campus_id].append(building_id)

            # Create Floor entities
            for building_id, floor_str, campus_id in floor_keys:
                floor_level = FloorLevel.from_string(floor_str)
                floor_id = generate_floor_id(building_id, floor_level)

                floor = Floor(
                    floor_id=floor_id,
                    building_id=building_id,
                    level=floor_level,
                    display_name=floor_str
                )
                self.floors[floor_id] = floor

                # Add to building
                if building_id in self.buildings:
                    if floor_id not in self.buildings[building_id].floor_ids:
                        self.buildings[building_id].floor_ids.append(floor_id)

                # Add to floors_by_building index
                if floor_id not in self.floors_by_building[building_id]:
                    self.floors_by_building[building_id].append(floor_id)

            # Second pass: create Room entities
            for entity in entities:
                room = self._convert_flat_entity_to_room(entity)
                if room:
                    self.rooms[room.room_id] = room
                    self._index_room(room)

            self._compute_stats()
            logger.info(
                f"Loaded CampusQueryIndex: {self._stats['rooms']} rooms, "
                f"{self._stats['buildings']} buildings, "
                f"{self._stats['campuses']} campuses, "
                f"{self._stats['aliases']} aliases"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load campus index: {e}")
            return False

    def _convert_flat_entity_to_room(self, entity: dict) -> Optional[Room]:
        """Convert a flat v1.x entity dict to a Room object."""
        try:
            entity_id = entity.get('entity_id', '')
            if not entity_id:
                return None

            campus_name = entity.get('campus', 'Main Campus')
            building_name = entity.get('building', 'Unknown Building')
            floor_str = entity.get('floor', 'Ground Floor')

            campus_id = generate_campus_id(campus_name)
            building_id = generate_building_id(building_name)
            floor_level = FloorLevel.from_string(floor_str)
            floor_id = generate_floor_id(building_id, floor_level)

            # Parse aliases (may be list or semicolon-separated string)
            aliases = entity.get('aliases', [])
            if isinstance(aliases, str):
                aliases = [a.strip().lower() for a in aliases.split(';') if a.strip()]
            elif isinstance(aliases, list):
                # Handle single-item list with comma-separated values
                parsed_aliases = []
                for alias in aliases:
                    if ',' in alias:
                        parsed_aliases.extend([a.strip().lower() for a in alias.split(',') if a.strip()])
                    else:
                        parsed_aliases.append(alias.lower().strip())
                aliases = parsed_aliases

            # Infer room type from various signals
            room_type = self._infer_room_type(entity)

            room = Room(
                room_id=entity_id,
                room_number=entity.get('room'),
                room_type=room_type,
                canonical_name=entity.get('canonical_name', entity_id),
                aliases=aliases,
                floor_id=floor_id,
                building_id=building_id,
                campus_id=campus_id,
                floor_level=floor_level,
                department=entity.get('department'),
                landmarks=entity.get('landmarks'),
                description=entity.get('description'),
                status=entity.get('status', 'active'),
                original_floor_str=floor_str,
                original_building_str=building_name
            )

            return room

        except Exception as e:
            logger.warning(f"Failed to convert entity {entity.get('entity_id')}: {e}")
            return None

    def _infer_room_type(self, entity: dict) -> RoomType:
        """Infer room type from entity data."""
        # Check explicit room_type field first
        if 'room_type' in entity:
            return RoomType.from_string(entity['room_type'])

        # Infer from canonical name
        canonical = entity.get('canonical_name', '').lower()
        entity_id = entity.get('entity_id', '').lower()
        description = entity.get('description', '').lower()

        # Classroom detection
        if any(kw in canonical for kw in ['classroom', 'lecture', 'class room']):
            return RoomType.CLASSROOM
        if 'class' in entity_id and 'room' not in entity_id:
            return RoomType.CLASSROOM

        # Office detection
        if 'office' in canonical:
            return RoomType.OFFICE

        # Laboratory detection
        if any(kw in canonical for kw in ['laboratory', 'lab ', ' lab', 'computer lab']):
            return RoomType.LABORATORY

        # Restroom detection
        if any(kw in canonical for kw in ['comfort room', 'restroom', 'cr', 'toilet', 'lavatory']):
            return RoomType.RESTROOM
        if 'crm' in entity_id.lower() or 'cr_' in entity_id.lower():
            return RoomType.RESTROOM

        # Conference detection
        if any(kw in canonical for kw in ['conference', 'meeting room', 'boardroom']):
            return RoomType.CONFERENCE

        # Library detection
        if 'library' in canonical:
            return RoomType.LIBRARY

        # Facility detection
        if any(kw in canonical for kw in ['canteen', 'cafeteria', 'gym', 'gymnasium', 'clinic', 'chapel', 'auditorium', 'court']):
            return RoomType.FACILITY

        # Utility detection
        if any(kw in canonical for kw in ['electric', 'server', 'maintenance', 'storage']):
            return RoomType.UTILITY

        # Check description as fallback
        if description:
            if 'classroom' in description:
                return RoomType.CLASSROOM
            if 'office' in description:
                return RoomType.OFFICE

        return RoomType.UNKNOWN

    def _index_room(self, room: Room) -> None:
        """Add room to all relevant indexes."""
        if room.status != "active":
            return

        room_id = room.room_id

        # Alias index
        canonical_normalized = room.canonical_name.lower().strip()
        self.alias_to_room[canonical_normalized] = room_id

        for alias in room.aliases:
            alias_normalized = alias.lower().strip()
            if alias_normalized and alias_normalized not in self.alias_to_room:
                self.alias_to_room[alias_normalized] = room_id

        # Relationship indexes
        self.rooms_by_floor[room.floor_id].append(room_id)
        self.rooms_by_building[room.building_id].append(room_id)
        self.rooms_by_campus[room.campus_id].append(room_id)
        self.rooms_by_type[room.room_type].append(room_id)

        if room.department:
            dept_id = normalize_id(room.department)
            self.rooms_by_department[dept_id].append(room_id)

        # Composite index
        self.rooms_by_building_floor[(room.building_id, room.floor_level)].append(room_id)

        # Add to floor's room list
        if room.floor_id in self.floors:
            if room_id not in self.floors[room.floor_id].room_ids:
                self.floors[room.floor_id].room_ids.append(room_id)

    def _index_campus_aliases(self, campus: Campus) -> None:
        """Index campus aliases."""
        self.alias_to_campus[campus.name.lower().strip()] = campus.campus_id
        for alias in campus.aliases:
            normalized = alias.lower().strip()
            if normalized:
                self.alias_to_campus[normalized] = campus.campus_id

    def _index_building_aliases(self, building: Building) -> None:
        """Index building aliases."""
        self.alias_to_building[building.name.lower().strip()] = building.building_id
        for alias in building.aliases:
            normalized = alias.lower().strip()
            if normalized:
                self.alias_to_building[normalized] = building.building_id

    def _compute_stats(self) -> None:
        """Compute index statistics."""
        self._stats["campuses"] = len(self.campuses)
        self._stats["buildings"] = len(self.buildings)
        self._stats["rooms"] = len(self.rooms)
        self._stats["active_rooms"] = len([r for r in self.rooms.values() if r.status == "active"])
        self._stats["aliases"] = len(self.alias_to_room) + len(self.alias_to_building) + len(self.alias_to_campus)

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def resolve_room(self, alias: str) -> Optional[Room]:
        """
        Resolve a room by alias or canonical name.

        Args:
            alias: Name or alias to look up (case-insensitive)

        Returns:
            Room if found, None otherwise
        """
        normalized = alias.lower().strip()
        room_id = self.alias_to_room.get(normalized)
        if room_id:
            return self.rooms.get(room_id)
        return None

    def resolve_building(self, alias: str) -> Optional[Building]:
        """Resolve a building by alias or name."""
        normalized = alias.lower().strip()
        building_id = self.alias_to_building.get(normalized)
        if building_id:
            return self.buildings.get(building_id)
        return None

    def resolve_campus(self, alias: str) -> Optional[Campus]:
        """Resolve a campus by alias or name."""
        normalized = alias.lower().strip()
        campus_id = self.alias_to_campus.get(normalized)
        if campus_id:
            return self.campuses.get(campus_id)
        return None

    def get_rooms_by_type(self, room_type: RoomType) -> List[Room]:
        """Get all rooms of a specific type."""
        room_ids = self.rooms_by_type.get(room_type, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    def get_rooms_by_building(self, building_id: str) -> List[Room]:
        """Get all rooms in a building."""
        room_ids = self.rooms_by_building.get(building_id, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    def get_rooms_by_floor(self, floor_id: str) -> List[Room]:
        """Get all rooms on a floor."""
        room_ids = self.rooms_by_floor.get(floor_id, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    def get_rooms_by_building_and_floor(
        self,
        building_id: str,
        floor_level: FloorLevel
    ) -> List[Room]:
        """Get all rooms on a specific floor of a building."""
        room_ids = self.rooms_by_building_floor.get((building_id, floor_level), [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    def get_rooms_by_campus(self, campus_id: str) -> List[Room]:
        """Get all rooms on a campus."""
        room_ids = self.rooms_by_campus.get(campus_id, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    def get_rooms_by_department(self, department: str) -> List[Room]:
        """Get all rooms belonging to a department."""
        dept_id = normalize_id(department)
        room_ids = self.rooms_by_department.get(dept_id, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms]

    # -------------------------------------------------------------------------
    # Structural Proximity (NEAREST)
    # -------------------------------------------------------------------------

    def find_nearest(
        self,
        reference: Room,
        target_type: RoomType,
        limit: int = 1
    ) -> List[Room]:
        """
        Find nearest rooms of a given type using structural proximity.

        Tiers:
        0. Same Floor
        1. Same Building, Different Floor
        2. Same Campus, Different Building
        3. Different Campus

        Args:
            reference: Reference room to search from
            target_type: Type of room to find
            limit: Maximum number of results

        Returns:
            List of matching rooms, sorted by structural proximity
        """
        results: List[Room] = []

        # Tier 0: Same Floor
        candidates = self.rooms_by_building_floor.get(
            (reference.building_id, reference.floor_level), []
        )
        for room_id in candidates:
            if room_id == reference.room_id:
                continue
            room = self.rooms.get(room_id)
            if room and room.room_type == target_type and room.status == "active":
                results.append(room)
                if len(results) >= limit:
                    return results

        # Tier 1: Same Building, Different Floor
        building_rooms = self.rooms_by_building.get(reference.building_id, [])
        # Sort by floor proximity
        tier1_candidates = []
        for room_id in building_rooms:
            if room_id == reference.room_id:
                continue
            room = self.rooms.get(room_id)
            if room and room.room_type == target_type and room.status == "active":
                if room.floor_level != reference.floor_level:
                    floor_distance = abs(room.floor_level.value - reference.floor_level.value)
                    tier1_candidates.append((floor_distance, room))

        tier1_candidates.sort(key=lambda x: (x[0], x[1].room_id))
        for _, room in tier1_candidates:
            if room not in results:
                results.append(room)
                if len(results) >= limit:
                    return results

        # Tier 2: Same Campus, Different Building
        campus_rooms = self.rooms_by_campus.get(reference.campus_id, [])
        for room_id in sorted(campus_rooms):
            room = self.rooms.get(room_id)
            if room and room.room_type == target_type and room.status == "active":
                if room.building_id != reference.building_id:
                    if room not in results:
                        results.append(room)
                        if len(results) >= limit:
                            return results

        # Tier 3: Different Campus (if needed)
        for campus_id, campus in self.campuses.items():
            if campus_id == reference.campus_id:
                continue
            campus_rooms = self.rooms_by_campus.get(campus_id, [])
            for room_id in sorted(campus_rooms):
                room = self.rooms.get(room_id)
                if room and room.room_type == target_type and room.status == "active":
                    if room not in results:
                        results.append(room)
                        if len(results) >= limit:
                            return results

        return results

    # -------------------------------------------------------------------------
    # Aggregation Queries
    # -------------------------------------------------------------------------

    def count_rooms_by_type(self, room_type: RoomType) -> int:
        """Count rooms of a specific type."""
        return len([r for r in self.rooms_by_type.get(room_type, [])
                    if r in self.rooms and self.rooms[r].status == "active"])

    def count_rooms_in_building(self, building_id: str) -> int:
        """Count rooms in a building."""
        return len([r for r in self.rooms_by_building.get(building_id, [])
                    if r in self.rooms and self.rooms[r].status == "active"])

    def count_rooms_on_floor(self, building_id: str, floor_level: FloorLevel) -> int:
        """Count rooms on a specific floor."""
        return len([r for r in self.rooms_by_building_floor.get((building_id, floor_level), [])
                    if r in self.rooms and self.rooms[r].status == "active"])

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_all_active_rooms(self) -> List[Room]:
        """Get all active rooms."""
        return [r for r in self.rooms.values() if r.status == "active"]

    def get_stats(self) -> Dict:
        """Get index statistics."""
        return self._stats.copy()

    def get_all_room_types(self) -> List[RoomType]:
        """Get all room types that have at least one room."""
        return [rt for rt in RoomType if self.rooms_by_type.get(rt)]

    def get_all_buildings(self) -> List[Building]:
        """Get all buildings."""
        return list(self.buildings.values())

    def get_all_campuses(self) -> List[Campus]:
        """Get all campuses."""
        return list(self.campuses.values())


# Singleton instance
_index_instance: Optional[CampusQueryIndex] = None


def get_campus_index(entities_json_path: Optional[str] = None) -> CampusQueryIndex:
    """
    Get or create the singleton CampusQueryIndex.

    Args:
        entities_json_path: Path to directory_entities.json (required on first call)

    Returns:
        CampusQueryIndex instance
    """
    global _index_instance

    if _index_instance is None:
        if entities_json_path is None:
            raise ValueError("entities_json_path required on first call")

        _index_instance = CampusQueryIndex()
        _index_instance.load_from_flat_entities(entities_json_path)

    return _index_instance


def reset_campus_index() -> None:
    """Reset the singleton index (for testing)."""
    global _index_instance
    _index_instance = None
