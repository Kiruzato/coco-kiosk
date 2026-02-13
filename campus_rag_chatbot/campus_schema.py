"""
Campus Query Engine Schema
==========================
Hierarchical dataclasses and enums for the Campus Query Engine (CQE).

Phase 47: Data Model Foundation
Phase 51: Schema Alignment (OutdoorLocation, Tags, RoomPrimaryType)

Hierarchy:
    Campus (Level 0)
        └── Building (Level 1)
        │     └── Floor (Level 2)
        │           └── Room (Level 3)
        │                 └── RoomPrimaryType, Tags, Department (Attributes)
        └── OutdoorLocation (Level 1, no floor/building)
        └── Department (Level 1, spans multiple rooms)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union


class RoomPrimaryType(Enum):
    """
    Primary room type classification (Phase 51 schema).

    Simplified to 4 categories. Use tags for secondary classification
    (e.g., primary_type=OTHER + tags=["laboratory", "engineering"]).
    """
    CLASSROOM = "classroom"
    OFFICE = "office"
    RESTROOM = "restroom"
    OTHER = "other"

    @classmethod
    def from_string(cls, value: str) -> "RoomPrimaryType":
        """Parse primary type from string."""
        if not value:
            return cls.OTHER
        value_lower = value.lower().strip()
        for ptype in cls:
            if ptype.value == value_lower:
                return ptype
        return cls.OTHER


class RoomType(Enum):
    """
    Enumeration of room types for structured queries.

    LEGACY: Kept for backward compatibility. Maps to RoomPrimaryType + tags.
    New code should use RoomPrimaryType with tags for secondary classification.

    Enables queries like "Show all classrooms" or "Find nearest restroom".
    """
    CLASSROOM = "classroom"
    OFFICE = "office"
    LABORATORY = "laboratory"
    RESTROOM = "restroom"
    CONFERENCE = "conference"
    FACILITY = "facility"      # gym, canteen, clinic, chapel
    STORAGE = "storage"
    UTILITY = "utility"        # electric room, server room
    LIBRARY = "library"
    UNKNOWN = "unknown"

    def to_primary_type(self) -> RoomPrimaryType:
        """Convert legacy RoomType to RoomPrimaryType."""
        mapping = {
            RoomType.CLASSROOM: RoomPrimaryType.CLASSROOM,
            RoomType.OFFICE: RoomPrimaryType.OFFICE,
            RoomType.RESTROOM: RoomPrimaryType.RESTROOM,
        }
        return mapping.get(self, RoomPrimaryType.OTHER)

    def to_tags(self) -> List[str]:
        """Get tags for this RoomType (for non-primary types)."""
        tag_mapping = {
            RoomType.LABORATORY: ["laboratory"],
            RoomType.CONFERENCE: ["conference"],
            RoomType.FACILITY: ["facility"],
            RoomType.STORAGE: ["storage"],
            RoomType.UTILITY: ["utility"],
            RoomType.LIBRARY: ["library"],
        }
        return tag_mapping.get(self, [])

    @classmethod
    def from_string(cls, value: str) -> "RoomType":
        """
        Parse room type from string, with fuzzy matching.

        Args:
            value: Room type string (case-insensitive)

        Returns:
            Matching RoomType enum value, or UNKNOWN if no match
        """
        if not value:
            return cls.UNKNOWN

        value_lower = value.lower().strip()

        # Direct enum match
        for room_type in cls:
            if room_type.value == value_lower:
                return room_type

        # Fuzzy matching for common variations
        type_mapping = {
            # Classroom variations
            "class": cls.CLASSROOM,
            "lecture": cls.CLASSROOM,
            "lecture room": cls.CLASSROOM,
            "lecture hall": cls.CLASSROOM,

            # Office variations
            "offices": cls.OFFICE,
            "admin": cls.OFFICE,
            "administrative": cls.OFFICE,

            # Laboratory variations
            "lab": cls.LABORATORY,
            "labs": cls.LABORATORY,
            "computer lab": cls.LABORATORY,
            "science lab": cls.LABORATORY,

            # Restroom variations
            "comfort room": cls.RESTROOM,
            "cr": cls.RESTROOM,
            "bathroom": cls.RESTROOM,
            "toilet": cls.RESTROOM,
            "washroom": cls.RESTROOM,
            "lavatory": cls.RESTROOM,

            # Conference variations
            "meeting room": cls.CONFERENCE,
            "conference room": cls.CONFERENCE,
            "boardroom": cls.CONFERENCE,

            # Facility variations
            "canteen": cls.FACILITY,
            "cafeteria": cls.FACILITY,
            "gym": cls.FACILITY,
            "gymnasium": cls.FACILITY,
            "clinic": cls.FACILITY,
            "chapel": cls.FACILITY,
            "auditorium": cls.FACILITY,
            "court": cls.FACILITY,

            # Utility variations
            "electric": cls.UTILITY,
            "electric room": cls.UTILITY,
            "server room": cls.UTILITY,
            "maintenance": cls.UTILITY,

            # Library
            "lib": cls.LIBRARY,
            "reading room": cls.LIBRARY,
        }

        return type_mapping.get(value_lower, cls.UNKNOWN)


class FloorLevel(Enum):
    """
    Enumeration of floor levels with numeric ordering.

    The value is the numeric floor number for sorting/proximity calculations.
    """
    BASEMENT = -1
    GROUND = 0
    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5

    @classmethod
    def from_string(cls, value: str) -> "FloorLevel":
        """
        Parse floor level from string.

        Args:
            value: Floor string (e.g., "Ground Floor", "2nd Floor", "2F")

        Returns:
            Matching FloorLevel enum value, or GROUND as default
        """
        if not value:
            return cls.GROUND

        value_lower = value.lower().strip()

        # Direct mappings
        floor_mapping = {
            # Ground floor variations
            "ground": cls.GROUND,
            "ground floor": cls.GROUND,
            "gf": cls.GROUND,
            "g/f": cls.GROUND,
            "1st floor": cls.GROUND,  # Some buildings call ground "1st"
            "first floor": cls.GROUND,

            # Second floor variations
            "second": cls.SECOND,
            "second floor": cls.SECOND,
            "2nd": cls.SECOND,
            "2nd floor": cls.SECOND,
            "2f": cls.SECOND,
            "2/f": cls.SECOND,

            # Third floor variations
            "third": cls.THIRD,
            "third floor": cls.THIRD,
            "3rd": cls.THIRD,
            "3rd floor": cls.THIRD,
            "3f": cls.THIRD,
            "3/f": cls.THIRD,

            # Fourth floor variations
            "fourth": cls.FOURTH,
            "fourth floor": cls.FOURTH,
            "4th": cls.FOURTH,
            "4th floor": cls.FOURTH,
            "4f": cls.FOURTH,
            "4/f": cls.FOURTH,

            # Fifth floor variations
            "fifth": cls.FIFTH,
            "fifth floor": cls.FIFTH,
            "5th": cls.FIFTH,
            "5th floor": cls.FIFTH,
            "5f": cls.FIFTH,
            "5/f": cls.FIFTH,

            # Basement
            "basement": cls.BASEMENT,
            "b1": cls.BASEMENT,
            "b/1": cls.BASEMENT,
        }

        return floor_mapping.get(value_lower, cls.GROUND)

    def display_name(self) -> str:
        """Get human-readable floor name."""
        names = {
            FloorLevel.BASEMENT: "Basement",
            FloorLevel.GROUND: "Ground Floor",
            FloorLevel.FIRST: "First Floor",
            FloorLevel.SECOND: "Second Floor",
            FloorLevel.THIRD: "Third Floor",
            FloorLevel.FOURTH: "Fourth Floor",
            FloorLevel.FIFTH: "Fifth Floor",
        }
        return names.get(self, "Unknown Floor")


@dataclass
class Room:
    """
    Represents a room/location within a floor.

    This is the leaf node in the campus hierarchy.
    Denormalized fields (building_id, campus_id) enable fast filtering.

    Phase 51: Added primary_type, tags, level_number for new schema alignment.
    """
    room_id: str                        # Unique ID (e.g., "A103_CLASSROOM")
    room_number: Optional[str]          # Room number (e.g., "A103", "SP303")
    room_type: RoomType                 # LEGACY: Type for structured queries
    canonical_name: str                 # Display name
    aliases: List[str]                  # Alternative lookup names

    # Hierarchical references
    floor_id: str                       # FK to Floor
    building_id: str                    # Denormalized for fast filtering
    campus_id: str                      # Denormalized for fast filtering
    floor_level: FloorLevel             # LEGACY: Denormalized for proximity

    # Phase 51: New schema fields
    primary_type: RoomPrimaryType = RoomPrimaryType.OTHER  # New 4-value type
    tags: List[str] = field(default_factory=list)          # Free-form tags
    level_number: int = 0                                  # Integer floor level
    department_id: Optional[str] = None                    # FK to Department

    # Optional metadata
    department: Optional[str] = None    # LEGACY: String department name
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"

    # Original entity data for backward compatibility
    original_floor_str: str = ""        # Original floor string (e.g., "Ground Floor")
    original_building_str: str = ""     # Original building string


@dataclass
class Floor:
    """
    Represents a floor within a building.

    Phase 51: Added level_number (int) and aliases.
    """
    floor_id: str                       # Unique ID (e.g., "A_BUILDING_GF")
    building_id: str                    # FK to Building
    level: FloorLevel                   # LEGACY: Numeric level for ordering
    display_name: str                   # Human-readable name
    room_ids: List[str] = field(default_factory=list)  # Child rooms

    # Phase 51: New schema fields
    level_number: int = 0               # Integer floor level (-2, -1, 0, 1, 2...)
    aliases: List[str] = field(default_factory=list)   # Alternative names (e.g., ["GF", "G/F"])


@dataclass
class Building:
    """
    Represents a building within a campus.

    Phase 5: Added description and landmarks fields.
    """
    building_id: str                    # Unique ID (e.g., "A_BUILDING")
    name: str                           # Display name (e.g., "A Building")
    aliases: List[str] = field(default_factory=list)  # Alternative names
    campus_id: str = ""                 # FK to Campus
    floor_ids: List[str] = field(default_factory=list)  # Child floors
    description: Optional[str] = None   # Phase 5: Building description
    landmarks: Optional[str] = None     # Phase 5: Nearby landmarks


@dataclass
class Campus:
    """
    Represents a campus (top-level entity).

    Phase 5: Added description and landmarks fields.
    """
    campus_id: str                      # Unique ID (e.g., "MAIN")
    name: str                           # Display name (e.g., "Main Campus")
    aliases: List[str] = field(default_factory=list)  # Alternative names
    building_ids: List[str] = field(default_factory=list)  # Child buildings
    description: Optional[str] = None   # Phase 5: Campus description
    landmarks: Optional[str] = None     # Phase 5: Nearby landmarks


@dataclass
class Department:
    """
    Represents an academic/administrative department.

    Departments can span multiple rooms across buildings.
    Phase 51: Now a first-class entity with FK relationship from Room.
    Phase 5: Added landmarks field.
    """
    department_id: str                  # Unique ID (e.g., "DEPT_CBA")
    name: str                           # Display name
    aliases: List[str] = field(default_factory=list)
    campus_id: str = ""                 # Primary campus
    office_room_ids: List[str] = field(default_factory=list)  # Primary offices
    description: Optional[str] = None
    landmarks: Optional[str] = None     # Phase 5: Nearby landmarks
    status: str = "active"


@dataclass
class OutdoorLocation:
    """
    Represents an outdoor location on campus (Phase 51).

    OutdoorLocations are campus-level entities without building/floor hierarchy.
    Examples: Covered Court, Parking Area, Garden, Field, Plaza.
    """
    location_id: str                    # Unique ID (e.g., "MAIN_COVERED_COURT")
    campus_id: str                      # FK to Campus
    canonical_name: str                 # Display name

    # Phase 51: Tag-based classification
    tags: List[str] = field(default_factory=list)   # e.g., ["court", "sports", "covered"]
    aliases: List[str] = field(default_factory=list)

    # Optional metadata
    description: Optional[str] = None
    landmarks: Optional[str] = None
    status: str = "active"


# Utility functions for ID generation

def normalize_id(value: str) -> str:
    """
    Normalize a string for use as an ID.

    - Uppercase
    - Replace spaces with underscores
    - Remove special characters except underscores
    """
    if not value:
        return ""

    # Uppercase and replace spaces
    normalized = value.upper().strip().replace(" ", "_")

    # Keep only alphanumeric and underscores
    normalized = "".join(c for c in normalized if c.isalnum() or c == "_")

    # Remove consecutive underscores
    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    return normalized.strip("_")


def generate_building_id(building_name: str) -> str:
    """Generate a building ID from building name."""
    return normalize_id(building_name)


def generate_floor_id(building_id: str, floor_level: Union[FloorLevel, int]) -> str:
    """
    Generate a floor ID from building and level.

    Args:
        building_id: Building ID
        floor_level: FloorLevel enum or integer level number

    Returns:
        Floor ID string
    """
    # Convert to integer if FloorLevel enum
    if isinstance(floor_level, FloorLevel):
        level_num = floor_level.value
    else:
        level_num = floor_level

    # Generate suffix based on level number
    if level_num < 0:
        return f"{building_id}_B{abs(level_num)}"
    elif level_num == 0:
        return f"{building_id}_GF"
    else:
        return f"{building_id}_{level_num}F"


def floor_level_to_number(floor_level: FloorLevel) -> int:
    """Convert FloorLevel enum to integer level_number."""
    return floor_level.value


def number_to_display_name(level_number: int) -> str:
    """
    Convert integer level_number to display name.

    Args:
        level_number: Integer floor level (-2, -1, 0, 1, 2...)

    Returns:
        Human-readable floor name
    """
    if level_number < 0:
        return f"Basement {abs(level_number)}" if abs(level_number) > 1 else "Basement"
    elif level_number == 0:
        return "Ground Floor"
    else:
        ordinals = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
                   6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth"}
        ordinal = ordinals.get(level_number, f"{level_number}th")
        return f"{ordinal} Floor"


def generate_campus_id(campus_name: str) -> str:
    """Generate a campus ID from campus name."""
    # Special handling for known campuses
    name_lower = campus_name.lower()
    if "main" in name_lower:
        return "MAIN"
    if "barretto" in name_lower or "baretto" in name_lower:
        return "BARRETTO"
    return normalize_id(campus_name)
