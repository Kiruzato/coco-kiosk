"""
Campus Query Index
==================
Pre-built indexes for O(1) structured queries in the Campus Query Engine.

Phase 47: Data Model Foundation
Phase 51: Schema Alignment (OutdoorLocation, Tags, RoomPrimaryType)

Provides:
- Primary indexes: campuses, buildings, floors, rooms, outdoor_locations by ID
- Alias indexes: alias -> entity_id mapping (including floor aliases)
- Relationship indexes: rooms_by_floor, rooms_by_building, rooms_by_type
- Tag indexes: rooms_by_tag, outdoor_by_tag (Phase 51)
- Structural proximity support: floor_level ordering
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

try:
    from .campus_schema import (
        Campus, Building, Floor, Room, Department, OutdoorLocation,
        RoomType, RoomPrimaryType, FloorLevel,
        generate_building_id, generate_floor_id, generate_campus_id,
        normalize_id, floor_level_to_number
    )
except ImportError:
    from campus_schema import (
        Campus, Building, Floor, Room, Department, OutdoorLocation,
        RoomType, RoomPrimaryType, FloorLevel,
        generate_building_id, generate_floor_id, generate_campus_id,
        normalize_id, floor_level_to_number
    )

logger = logging.getLogger(__name__)

# Phase 55: Outdoor location marker for flat entity format
OUTDOOR_MARKER = "_OUTDOOR"


class CampusQueryIndex:
    """
    Pre-built indexes for O(1) campus queries.

    All indexes are built at load time from hierarchical JSON data.
    Supports both hierarchical (v2) and flat (v1) entity formats.

    Phase 51: Added outdoor_locations, tag indexes, floor aliases.
    """

    def __init__(self):
        # Primary indexes (entity_id -> entity)
        self.campuses: Dict[str, Campus] = {}
        self.buildings: Dict[str, Building] = {}
        self.floors: Dict[str, Floor] = {}
        self.rooms: Dict[str, Room] = {}
        self.departments: Dict[str, Department] = {}
        self.outdoor_locations: Dict[str, OutdoorLocation] = {}  # Phase 51

        # Alias indexes (normalized alias -> entity_id)
        self.alias_to_room: Dict[str, str] = {}
        self.alias_to_building: Dict[str, str] = {}
        self.alias_to_campus: Dict[str, str] = {}
        self.alias_to_department: Dict[str, str] = {}
        self.alias_to_outdoor: Dict[str, str] = {}  # Phase 51
        self.alias_to_floor: Dict[str, str] = {}    # Phase 51

        # Relationship indexes (for filtered queries)
        self.rooms_by_floor: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_building: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_campus: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_type: Dict[RoomType, List[str]] = defaultdict(list)
        self.rooms_by_department: Dict[str, List[str]] = defaultdict(list)

        # Phase 51: Tag indexes
        self.rooms_by_tag: Dict[str, List[str]] = defaultdict(list)
        self.outdoor_by_tag: Dict[str, List[str]] = defaultdict(list)
        self.rooms_by_primary_type: Dict[RoomPrimaryType, List[str]] = defaultdict(list)
        self.outdoor_by_campus: Dict[str, List[str]] = defaultdict(list)

        # Composite indexes
        self.rooms_by_building_floor: Dict[Tuple[str, FloorLevel], List[str]] = defaultdict(list)
        self.rooms_by_building_level: Dict[Tuple[str, int], List[str]] = defaultdict(list)  # Phase 51

        # Floors by building (for structural proximity)
        self.floors_by_building: Dict[str, List[str]] = defaultdict(list)
        self.buildings_by_campus: Dict[str, List[str]] = defaultdict(list)

        # Statistics
        self._stats = {
            "rooms": 0,
            "active_rooms": 0,
            "buildings": 0,
            "campuses": 0,
            "aliases": 0,
            "outdoor_locations": 0,  # Phase 51
            "tags": 0                # Phase 51
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

                # Phase 55: Skip outdoor entities for building/floor collection
                is_outdoor = (
                    building_name.upper() == OUTDOOR_MARKER or
                    floor_str.upper() == OUTDOOR_MARKER
                )
                if is_outdoor:
                    continue

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
                level_number = floor_level_to_number(floor_level)

                # Generate floor aliases
                floor_aliases = self._generate_floor_aliases(floor_str, level_number)

                floor = Floor(
                    floor_id=floor_id,
                    building_id=building_id,
                    level=floor_level,
                    display_name=floor_str,
                    level_number=level_number,
                    aliases=floor_aliases
                )
                self.floors[floor_id] = floor
                self._index_floor_aliases(floor)

                # Add to building
                if building_id in self.buildings:
                    if floor_id not in self.buildings[building_id].floor_ids:
                        self.buildings[building_id].floor_ids.append(floor_id)

                # Add to floors_by_building index
                if floor_id not in self.floors_by_building[building_id]:
                    self.floors_by_building[building_id].append(floor_id)

            # Second pass: create Room and OutdoorLocation entities
            for entity in entities:
                building_name = entity.get('building', '')
                floor_str = entity.get('floor', '')

                # Phase 55: Check for outdoor location marker
                is_outdoor = (
                    building_name.upper() == OUTDOOR_MARKER or
                    floor_str.upper() == OUTDOOR_MARKER
                )

                if is_outdoor:
                    outdoor = self._convert_to_outdoor_location(entity)
                    if outdoor:
                        self._index_outdoor_location(outdoor)
                else:
                    room = self._convert_flat_entity_to_room(entity)
                    if room:
                        self.rooms[room.room_id] = room
                        self._index_room(room)

            self._compute_stats()
            logger.info(
                f"Loaded CampusQueryIndex: {self._stats['rooms']} rooms, "
                f"{self._stats.get('outdoor_locations', 0)} outdoor locations, "
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
            level_number = floor_level_to_number(floor_level)

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

            # Infer room type from various signals (legacy)
            room_type = self._infer_room_type(entity)

            # Phase 51: Convert to primary_type and tags
            primary_type = room_type.to_primary_type()
            tags = room_type.to_tags().copy()

            # Add any explicit tags from entity
            entity_tags = entity.get('tags', [])
            if isinstance(entity_tags, list):
                for tag in entity_tags:
                    if tag and tag.lower() not in tags:
                        tags.append(tag.lower())

            # Infer additional tags from canonical name
            tags.extend(self._infer_tags_from_name(entity.get('canonical_name', ''), tags))

            # Phase 51: Department ID
            department_str = entity.get('department')
            department_id = normalize_id(department_str) if department_str else None

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
                # Phase 51 fields
                primary_type=primary_type,
                tags=tags,
                level_number=level_number,
                department_id=department_id,
                # Legacy fields
                department=department_str,
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

    def _convert_to_outdoor_location(self, entity: dict) -> Optional[OutdoorLocation]:
        """
        Convert a flat entity with _OUTDOOR marker to an OutdoorLocation.

        Phase 55: Admin Directory Management System

        Args:
            entity: Flat entity dict with building="_OUTDOOR" or floor="_OUTDOOR"

        Returns:
            OutdoorLocation object or None if conversion fails
        """
        try:
            entity_id = entity.get('entity_id', '')
            if not entity_id:
                return None

            campus_name = entity.get('campus', 'Main Campus')
            campus_id = generate_campus_id(campus_name)

            # Parse aliases
            aliases = entity.get('aliases', [])
            if isinstance(aliases, str):
                aliases = [a.strip().lower() for a in aliases.split(';') if a.strip()]
            elif isinstance(aliases, list):
                parsed_aliases = []
                for alias in aliases:
                    if ',' in alias:
                        parsed_aliases.extend([a.strip().lower() for a in alias.split(',') if a.strip()])
                    else:
                        parsed_aliases.append(alias.lower().strip())
                aliases = parsed_aliases

            # Parse tags
            tags = entity.get('tags', [])
            if isinstance(tags, str):
                tags = [t.strip().lower() for t in tags.split(';') if t.strip()]
            elif isinstance(tags, list):
                tags = [t.lower().strip() for t in tags if t]

            # Ensure "outdoor" tag is present
            if 'outdoor' not in tags:
                tags.append('outdoor')

            outdoor = OutdoorLocation(
                location_id=entity_id,
                campus_id=campus_id,
                canonical_name=entity.get('canonical_name', entity_id),
                tags=tags,
                aliases=aliases,
                description=entity.get('description'),
                landmarks=entity.get('landmarks'),
                status=entity.get('status', 'active')
            )

            logger.debug(f"Created outdoor location: {entity_id}")
            return outdoor

        except Exception as e:
            logger.warning(f"Failed to convert outdoor entity {entity.get('entity_id')}: {e}")
            return None

    def _infer_tags_from_name(self, canonical_name: str, existing_tags: List[str]) -> List[str]:
        """Infer additional tags from canonical name."""
        tags = []
        name_lower = canonical_name.lower()

        # Facility-specific tags
        tag_keywords = {
            "canteen": "canteen",
            "cafeteria": "canteen",
            "gym": "gym",
            "gymnasium": "gym",
            "clinic": "clinic",
            "chapel": "chapel",
            "auditorium": "auditorium",
            "court": "court",
            "library": "library",
            "computer": "computer",
            "science": "science",
            "engineering": "engineering",
        }

        for keyword, tag in tag_keywords.items():
            if keyword in name_lower and tag not in existing_tags and tag not in tags:
                tags.append(tag)

        return tags

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

        # Phase 51: Tag and primary_type indexes
        self.rooms_by_primary_type[room.primary_type].append(room_id)
        for tag in room.tags:
            tag_normalized = tag.lower().strip()
            if tag_normalized:
                self.rooms_by_tag[tag_normalized].append(room_id)

        # Phase 51: Integer floor level index
        self.rooms_by_building_level[(room.building_id, room.level_number)].append(room_id)

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

    def _generate_floor_aliases(self, floor_str: str, level_number: int) -> List[str]:
        """Generate aliases for a floor based on its display name and level."""
        aliases = []
        floor_lower = floor_str.lower()

        # Common abbreviations
        alias_patterns = {
            "ground floor": ["gf", "g/f", "ground"],
            "first floor": ["1f", "1/f", "1st", "1st floor"],
            "second floor": ["2f", "2/f", "2nd", "2nd floor"],
            "third floor": ["3f", "3/f", "3rd", "3rd floor"],
            "fourth floor": ["4f", "4/f", "4th", "4th floor"],
            "fifth floor": ["5f", "5/f", "5th", "5th floor"],
            "basement": ["b1", "b/1", "b-1"],
        }

        for pattern, pattern_aliases in alias_patterns.items():
            if pattern in floor_lower:
                aliases.extend(pattern_aliases)

        # Add level number variations
        if level_number > 0:
            aliases.append(f"{level_number}f")
            aliases.append(f"{level_number}/f")
        elif level_number < 0:
            aliases.append(f"b{abs(level_number)}")

        return list(set(aliases))

    def _index_floor_aliases(self, floor: Floor) -> None:
        """Index floor aliases."""
        self.alias_to_floor[floor.display_name.lower().strip()] = floor.floor_id
        for alias in floor.aliases:
            normalized = alias.lower().strip()
            if normalized:
                self.alias_to_floor[normalized] = floor.floor_id

    def _index_outdoor_location(self, location: OutdoorLocation) -> None:
        """Add outdoor location to all relevant indexes (Phase 51)."""
        if location.status != "active":
            return

        location_id = location.location_id

        # Alias index
        canonical_normalized = location.canonical_name.lower().strip()
        self.alias_to_outdoor[canonical_normalized] = location_id

        for alias in location.aliases:
            alias_normalized = alias.lower().strip()
            if alias_normalized and alias_normalized not in self.alias_to_outdoor:
                self.alias_to_outdoor[alias_normalized] = location_id

        # Campus index
        self.outdoor_by_campus[location.campus_id].append(location_id)

        # Tag index
        for tag in location.tags:
            tag_normalized = tag.lower().strip()
            if tag_normalized:
                self.outdoor_by_tag[tag_normalized].append(location_id)

    def add_outdoor_location(self, location: OutdoorLocation) -> None:
        """Add an outdoor location to the index (Phase 51)."""
        self.outdoor_locations[location.location_id] = location
        self._index_outdoor_location(location)

    def _index_department_aliases(self, department: Department) -> None:
        """Index department aliases (Phase 60)."""
        self.alias_to_department[department.name.lower().strip()] = department.department_id
        for alias in department.aliases:
            normalized = alias.lower().strip()
            if normalized:
                self.alias_to_department[normalized] = department.department_id

    def _compute_stats(self) -> None:
        """Compute index statistics."""
        self._stats["campuses"] = len(self.campuses)
        self._stats["buildings"] = len(self.buildings)
        self._stats["rooms"] = len(self.rooms)
        self._stats["active_rooms"] = len([r for r in self.rooms.values() if r.status == "active"])
        self._stats["aliases"] = (
            len(self.alias_to_room) + len(self.alias_to_building) +
            len(self.alias_to_campus) + len(self.alias_to_outdoor) +
            len(self.alias_to_floor)
        )
        # Phase 51 stats
        self._stats["outdoor_locations"] = len(self.outdoor_locations)
        self._stats["tags"] = len(self.rooms_by_tag) + len(self.outdoor_by_tag)

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
    # Phase 51: Outdoor Location Queries
    # -------------------------------------------------------------------------

    def resolve_outdoor_location(self, alias: str) -> Optional[OutdoorLocation]:
        """
        Resolve an outdoor location by alias or canonical name.

        Args:
            alias: Name or alias to look up (case-insensitive)

        Returns:
            OutdoorLocation if found, None otherwise
        """
        normalized = alias.lower().strip()
        location_id = self.alias_to_outdoor.get(normalized)
        if location_id:
            return self.outdoor_locations.get(location_id)
        return None

    def get_outdoor_by_campus(self, campus_id: str) -> List[OutdoorLocation]:
        """Get all outdoor locations on a campus."""
        location_ids = self.outdoor_by_campus.get(campus_id, [])
        return [self.outdoor_locations[lid] for lid in location_ids if lid in self.outdoor_locations]

    def get_all_outdoor_locations(self) -> List[OutdoorLocation]:
        """Get all outdoor locations."""
        return [loc for loc in self.outdoor_locations.values() if loc.status == "active"]

    # -------------------------------------------------------------------------
    # Phase 51: Tag-Based Queries
    # -------------------------------------------------------------------------

    def get_rooms_by_tag(self, tag: str) -> List[Room]:
        """Get all rooms with a specific tag."""
        tag_normalized = tag.lower().strip()
        room_ids = self.rooms_by_tag.get(tag_normalized, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms and self.rooms[rid].status == "active"]

    def get_outdoor_by_tag(self, tag: str) -> List[OutdoorLocation]:
        """Get all outdoor locations with a specific tag."""
        tag_normalized = tag.lower().strip()
        location_ids = self.outdoor_by_tag.get(tag_normalized, [])
        return [self.outdoor_locations[lid] for lid in location_ids
                if lid in self.outdoor_locations and self.outdoor_locations[lid].status == "active"]

    def get_entities_by_tag(self, tag: str) -> List[Union[Room, OutdoorLocation]]:
        """Get all entities (rooms and outdoor locations) with a specific tag."""
        rooms = self.get_rooms_by_tag(tag)
        outdoor = self.get_outdoor_by_tag(tag)
        return rooms + outdoor

    def get_rooms_by_primary_type(self, primary_type: RoomPrimaryType) -> List[Room]:
        """Get all rooms of a specific primary type."""
        room_ids = self.rooms_by_primary_type.get(primary_type, [])
        return [self.rooms[rid] for rid in room_ids if rid in self.rooms and self.rooms[rid].status == "active"]

    def resolve_floor(self, alias: str) -> Optional[Floor]:
        """Resolve a floor by alias."""
        normalized = alias.lower().strip()
        floor_id = self.alias_to_floor.get(normalized)
        if floor_id:
            return self.floors.get(floor_id)
        return None

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
