"""
Campus Query Engine Schema
==========================
Hierarchical dataclasses and enums for the Campus Query Engine (CQE).

Phase 47: Data Model Foundation

Hierarchy:
    Campus (Level 0)
        └── Building (Level 1)
              └── Floor (Level 2)
                    └── Room (Level 3)
                          └── RoomType, Department (Attributes)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RoomType(Enum):
    """
    Enumeration of room types for structured queries.

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
    """
    room_id: str                        # Unique ID (e.g., "A103_CLASSROOM")
    room_number: Optional[str]          # Room number (e.g., "A103", "SP303")
    room_type: RoomType                 # Type for structured queries
    canonical_name: str                 # Display name
    aliases: List[str]                  # Alternative lookup names

    # Hierarchical references
    floor_id: str                       # FK to Floor
    building_id: str                    # Denormalized for fast filtering
    campus_id: str                      # Denormalized for fast filtering
    floor_level: FloorLevel             # Denormalized for proximity

    # Optional metadata
    department: Optional[str] = None
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
    """
    floor_id: str                       # Unique ID (e.g., "A_BUILDING_GF")
    building_id: str                    # FK to Building
    level: FloorLevel                   # Numeric level for ordering
    display_name: str                   # Human-readable name
    room_ids: List[str] = field(default_factory=list)  # Child rooms


@dataclass
class Building:
    """
    Represents a building within a campus.
    """
    building_id: str                    # Unique ID (e.g., "A_BUILDING")
    name: str                           # Display name (e.g., "A Building")
    aliases: List[str] = field(default_factory=list)  # Alternative names
    campus_id: str = ""                 # FK to Campus
    floor_ids: List[str] = field(default_factory=list)  # Child floors


@dataclass
class Campus:
    """
    Represents a campus (top-level entity).
    """
    campus_id: str                      # Unique ID (e.g., "MAIN")
    name: str                           # Display name (e.g., "Main Campus")
    aliases: List[str] = field(default_factory=list)  # Alternative names
    building_ids: List[str] = field(default_factory=list)  # Child buildings


@dataclass
class Department:
    """
    Represents an academic/administrative department.

    Departments can span multiple rooms across buildings.
    """
    department_id: str                  # Unique ID (e.g., "CBA")
    name: str                           # Display name
    aliases: List[str] = field(default_factory=list)
    campus_id: str = ""                 # Primary campus
    office_room_ids: List[str] = field(default_factory=list)  # Primary offices


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


def generate_floor_id(building_id: str, floor_level: FloorLevel) -> str:
    """Generate a floor ID from building and level."""
    floor_suffix = {
        FloorLevel.BASEMENT: "B1",
        FloorLevel.GROUND: "GF",
        FloorLevel.FIRST: "1F",
        FloorLevel.SECOND: "2F",
        FloorLevel.THIRD: "3F",
        FloorLevel.FOURTH: "4F",
        FloorLevel.FIFTH: "5F",
    }
    return f"{building_id}_{floor_suffix.get(floor_level, 'GF')}"


def generate_campus_id(campus_name: str) -> str:
    """Generate a campus ID from campus name."""
    # Special handling for known campuses
    name_lower = campus_name.lower()
    if "main" in name_lower:
        return "MAIN"
    if "barretto" in name_lower or "baretto" in name_lower:
        return "BARRETTO"
    return normalize_id(campus_name)
