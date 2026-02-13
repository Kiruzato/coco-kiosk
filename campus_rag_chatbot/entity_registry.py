"""
Entity Registry for Directory Locations
========================================
Manages structured directory entities with canonical names and aliases.

This module provides:
- DirectoryEntity: Data class for location entities
- EntityRegistry: In-memory registry with fast alias-based lookup

Used by entity_resolver.py to resolve directory queries to specific locations.

Phase 47: Added CampusQueryIndex integration for structured queries.
The EntityRegistry now serves as a backward-compatibility wrapper that
can optionally use the hierarchical CampusQueryIndex for enhanced queries.
"""

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Phase 1: Module-level lock for atomic file operations (single-process safety)
_file_lock = threading.Lock()


@dataclass
class DirectoryEntity:
    """
    Structured representation of a campus directory location.

    Attributes:
        entity_id: Unique identifier (e.g., "CANTEEN", "LIBRARY")
        canonical_name: Official display name (e.g., "Main Library")
        aliases: List of alternative names/phrases that map to this entity
        building: Building name where the location is found
        floor: Floor level (e.g., "Ground Floor", "2nd Floor")
        room: Room number(s) if applicable, None otherwise
        campus: Campus where the location is found (e.g., "Main Campus")
        department: Department the location belongs to (optional)
        landmarks: Navigation hints to help find the location
        description: Brief description of the location's purpose
        status: Entity status - "active" or "inactive" (default: "active")
        last_updated: ISO timestamp of last modification
    """
    entity_id: str
    canonical_name: str
    aliases: List[str]
    building: str
    floor: str
    room: Optional[str]
    campus: str
    department: Optional[str]
    landmarks: Optional[str]
    description: Optional[str]
    status: str = "active"
    last_updated: Optional[str] = None


class EntityRegistry:
    """
    In-memory registry of directory entities with fast lookup.

    Features:
    - Loads entities from JSON file at initialization
    - Builds alias index for O(1) lookup by name/alias
    - Case-insensitive matching
    - Designed for lightweight deployment (Raspberry Pi compatible)
    """

    def __init__(self, json_path: str):
        """
        Initialize registry by loading entities from JSON file.

        Args:
            json_path: Path to directory_entities.json file
        """
        self.entities: Dict[str, DirectoryEntity] = {}
        self.alias_index: Dict[str, str] = {}  # normalized alias -> entity_id
        self._json_path = json_path
        self._load_entities()

    def _load_entities(self) -> None:
        """Load entities from JSON file and build alias index."""
        path = Path(self._json_path)

        if not path.exists():
            logger.warning(f"Entity registry file not found: {self._json_path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entities_data = data.get('entities', [])

            for entry in entities_data:
                entity = DirectoryEntity(
                    entity_id=entry['entity_id'],
                    canonical_name=entry['canonical_name'],
                    aliases=entry.get('aliases', []),
                    building=entry['building'],
                    floor=entry['floor'],
                    room=entry.get('room'),
                    campus=entry.get('campus', 'Main Campus'),  # Default for backward compat
                    department=entry.get('department'),
                    landmarks=entry.get('landmarks'),
                    description=entry.get('description'),
                    status=entry.get('status', 'active'),
                    last_updated=entry.get('last_updated')
                )

                # Store entity by ID (all entities, including inactive)
                self.entities[entity.entity_id] = entity

            # Build alias index (only active entities)
            self._rebuild_alias_index()

            active_count = len([e for e in self.entities.values() if e.status == "active"])
            logger.info(
                f"Loaded {len(self.entities)} directory entities "
                f"({active_count} active) with {len(self.alias_index)} aliases"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse entity registry JSON: {e}")
        except KeyError as e:
            logger.error(f"Missing required field in entity data: {e}")
        except Exception as e:
            logger.error(f"Error loading entity registry: {e}")

    def get_by_id(self, entity_id: str) -> Optional[DirectoryEntity]:
        """
        Get entity by its unique ID.

        Args:
            entity_id: Entity identifier (e.g., "LIBRARY")

        Returns:
            DirectoryEntity if found, None otherwise
        """
        return self.entities.get(entity_id)

    def get_by_alias(self, alias: str) -> Optional[DirectoryEntity]:
        """
        Get entity by any of its aliases or canonical name.

        Performs case-insensitive matching.

        Args:
            alias: Name or alias to look up (e.g., "library", "cafeteria")

        Returns:
            DirectoryEntity if found, None otherwise
        """
        normalized = alias.lower().strip()
        entity_id = self.alias_index.get(normalized)

        if entity_id:
            return self.entities.get(entity_id)
        return None

    def find_matching_entities(self, query: str) -> List[DirectoryEntity]:
        """
        Find all entities that could match a query term (Phase 14).

        Checks canonical names and aliases for partial matches.
        Used for disambiguation when multiple entities might match.

        Args:
            query: Search term (e.g., "court", "office")

        Returns:
            List of matching DirectoryEntity objects (may be 0, 1, or many)
        """
        query_lower = query.lower().strip()
        matches = []
        seen_ids = set()

        for entity in self.get_active_entities():
            if entity.entity_id in seen_ids:
                continue

            # Check canonical name
            if query_lower in entity.canonical_name.lower():
                matches.append(entity)
                seen_ids.add(entity.entity_id)
                continue

            # Check aliases
            for alias in entity.aliases:
                if query_lower in alias.lower() or alias.lower() in query_lower:
                    matches.append(entity)
                    seen_ids.add(entity.entity_id)
                    break

        return matches

    def get_all_aliases(self) -> List[str]:
        """
        Get all registered aliases and canonical names.

        Returns:
            List of all normalized aliases
        """
        return list(self.alias_index.keys())

    def get_all_entities(self) -> List[DirectoryEntity]:
        """
        Get all registered entities.

        Returns:
            List of all DirectoryEntity objects
        """
        return list(self.entities.values())

    def __len__(self) -> int:
        """Return number of entities in registry."""
        return len(self.entities)

    def __contains__(self, alias: str) -> bool:
        """Check if an alias exists in the registry."""
        return alias.lower().strip() in self.alias_index

    def _rebuild_alias_index(self) -> None:
        """Rebuild the alias index from current entities."""
        self.alias_index.clear()

        for entity in self.entities.values():
            # Only index active entities
            if entity.status != "active":
                continue

            # Index canonical name (normalized)
            canonical_normalized = entity.canonical_name.lower().strip()
            self.alias_index[canonical_normalized] = entity.entity_id

            # Index all aliases (normalized)
            for alias in entity.aliases:
                alias_normalized = alias.lower().strip()
                if alias_normalized not in self.alias_index:
                    self.alias_index[alias_normalized] = entity.entity_id

    def save_entities(self) -> Tuple[bool, str]:
        """
        Save all entities to the JSON file atomically.

        Phase 1: Uses temp file + os.replace() for atomic write.
        Thread-safe via module-level lock.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Build entity list for JSON
            entities_list = []
            for entity in self.entities.values():
                entity_dict = asdict(entity)
                entities_list.append(entity_dict)

            # Sort by entity_id for consistent output
            entities_list.sort(key=lambda x: x['entity_id'])

            data = {
                "version": "1.1",
                "last_updated": datetime.now().isoformat(),
                "entities": entities_list
            }

            path = Path(self._json_path)

            # Acquire lock for thread safety
            with _file_lock:
                # Write to temp file in same directory (ensures same filesystem)
                fd, temp_path = tempfile.mkstemp(
                    suffix='.tmp',
                    prefix='entities_',
                    dir=path.parent
                )
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    # Atomic overwrite using os.replace() - cross-platform safe
                    os.replace(temp_path, str(path))

                except Exception:
                    # Cleanup temp file on failure
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise

            logger.info(f"Saved {len(entities_list)} entities to {self._json_path}")
            return True, f"Saved {len(entities_list)} entities"

        except Exception as e:
            logger.error(f"Failed to save entities: {e}")
            return False, f"Failed to save entities: {str(e)}"

    def add_entity(
        self,
        entity_id: str,
        canonical_name: str,
        aliases: List[str],
        building: str,
        floor: str,
        room: Optional[str] = None,
        campus: str = "Main Campus",
        department: Optional[str] = None,
        landmarks: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add a new entity to the registry.

        Args:
            entity_id: Unique identifier (will be uppercased)
            canonical_name: Official display name
            aliases: List of alternative names
            building: Building name
            floor: Floor level
            room: Room number (optional)
            campus: Campus name (required)
            department: Department name (optional)
            landmarks: Navigation hints (optional)
            description: Brief description (optional)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Normalize entity_id
        entity_id = entity_id.upper().strip()

        # Validation
        if not entity_id:
            return False, "Entity ID cannot be empty"

        if entity_id in self.entities:
            return False, f"Entity ID '{entity_id}' already exists"

        if not canonical_name or not canonical_name.strip():
            return False, "Canonical name cannot be empty"

        if not building or not building.strip():
            return False, "Building cannot be empty"

        if not floor or not floor.strip():
            return False, "Floor cannot be empty"

        if not campus or not campus.strip():
            return False, "Campus cannot be empty"

        # Normalize aliases (lowercase, trimmed, deduplicated)
        normalized_aliases = []
        seen = set()
        for alias in aliases:
            normalized = alias.lower().strip()
            if normalized and normalized not in seen:
                normalized_aliases.append(normalized)
                seen.add(normalized)

        # Create entity
        entity = DirectoryEntity(
            entity_id=entity_id,
            canonical_name=canonical_name.strip(),
            aliases=normalized_aliases,
            building=building.strip(),
            floor=floor.strip(),
            room=room.strip() if room else None,
            campus=campus.strip(),
            department=department.strip() if department else None,
            landmarks=landmarks.strip() if landmarks else None,
            description=description.strip() if description else None,
            status="active",
            last_updated=datetime.now().isoformat()
        )

        # Add to registry
        self.entities[entity_id] = entity

        # Rebuild alias index
        self._rebuild_alias_index()

        # Save to file
        success, msg = self.save_entities()
        if not success:
            # Rollback on save failure
            del self.entities[entity_id]
            self._rebuild_alias_index()
            return False, msg

        logger.info(f"Added entity: {entity_id}")
        return True, f"Entity '{entity_id}' created successfully"

    def update_entity(
        self,
        entity_id: str,
        canonical_name: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        room: Optional[str] = None,
        campus: Optional[str] = None,
        department: Optional[str] = None,
        landmarks: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Update an existing entity.

        Args:
            entity_id: Entity to update
            Other args: Fields to update (None = keep existing)

        Returns:
            Tuple of (success: bool, message: str)
        """
        entity_id = entity_id.upper().strip()

        if entity_id not in self.entities:
            return False, f"Entity '{entity_id}' not found"

        entity = self.entities[entity_id]

        # Validate updates
        if canonical_name is not None:
            if not canonical_name.strip():
                return False, "Canonical name cannot be empty"
            entity.canonical_name = canonical_name.strip()

        if aliases is not None:
            # Normalize aliases
            normalized_aliases = []
            seen = set()
            for alias in aliases:
                normalized = alias.lower().strip()
                if normalized and normalized not in seen:
                    normalized_aliases.append(normalized)
                    seen.add(normalized)
            entity.aliases = normalized_aliases

        if building is not None:
            if not building.strip():
                return False, "Building cannot be empty"
            entity.building = building.strip()

        if floor is not None:
            if not floor.strip():
                return False, "Floor cannot be empty"
            entity.floor = floor.strip()

        if room is not None:
            entity.room = room.strip() if room.strip() else None

        if campus is not None:
            if not campus.strip():
                return False, "Campus cannot be empty"
            entity.campus = campus.strip()

        if department is not None:
            entity.department = department.strip() if department.strip() else None

        if landmarks is not None:
            entity.landmarks = landmarks.strip() if landmarks.strip() else None

        if description is not None:
            entity.description = description.strip() if description.strip() else None

        if status is not None:
            if status not in ("active", "inactive"):
                return False, "Status must be 'active' or 'inactive'"
            entity.status = status

        # Update timestamp
        entity.last_updated = datetime.now().isoformat()

        # Rebuild alias index
        self._rebuild_alias_index()

        # Save to file
        success, msg = self.save_entities()
        if not success:
            # Reload from file on save failure
            self.entities.clear()
            self.alias_index.clear()
            self._load_entities()
            return False, msg

        logger.info(f"Updated entity: {entity_id}")
        return True, f"Entity '{entity_id}' updated successfully"

    def delete_entity(self, entity_id: str, hard: bool = False) -> Tuple[bool, str]:
        """
        Delete an entity (soft or hard delete).

        Args:
            entity_id: Entity to delete
            hard: If True, permanently remove; if False, set status to inactive

        Returns:
            Tuple of (success: bool, message: str)
        """
        entity_id = entity_id.upper().strip()

        if entity_id not in self.entities:
            return False, f"Entity '{entity_id}' not found"

        if hard:
            # Hard delete - remove from registry
            del self.entities[entity_id]
            self._rebuild_alias_index()

            success, msg = self.save_entities()
            if not success:
                # Reload from file on save failure
                self.entities.clear()
                self.alias_index.clear()
                self._load_entities()
                return False, msg

            logger.info(f"Hard deleted entity: {entity_id}")
            return True, f"Entity '{entity_id}' permanently deleted"
        else:
            # Soft delete - set status to inactive
            return self.update_entity(entity_id, status="inactive")

    def get_active_entities(self) -> List[DirectoryEntity]:
        """
        Get all active entities.

        Returns:
            List of active DirectoryEntity objects
        """
        return [e for e in self.entities.values() if e.status == "active"]

    def reload(self) -> None:
        """Reload entities from file."""
        self.entities.clear()
        self.alias_index.clear()
        self._load_entities()

    def bulk_import(
        self,
        entities_data: List[dict]
    ) -> Tuple[bool, str, dict]:
        """
        Import multiple entities atomically (all-or-nothing).

        Rules:
        - If entity_id exists → update entity
        - If entity_id is new → create entity
        - If status is 'inactive' → soft delete
        - All changes applied only if ALL rows are valid

        Args:
            entities_data: List of entity dicts with keys:
                entity_id, canonical_name, aliases, building, floor,
                room, campus, department, landmarks, description, status

        Returns:
            Tuple of (success, message, stats)
            stats = {"created": N, "updated": N, "errors": [...]}
        """
        stats = {"created": 0, "updated": 0, "errors": []}

        # Phase 1: Validate all entities before applying any changes
        validated_entities = []

        for idx, data in enumerate(entities_data):
            row_num = idx + 2  # +2 for 1-indexed and header row

            # Required field validation
            entity_id = str(data.get('entity_id', '')).upper().strip()
            canonical_name = str(data.get('canonical_name', '')).strip()
            building = str(data.get('building', '')).strip()
            floor = str(data.get('floor', '')).strip()
            campus = str(data.get('campus', '')).strip()

            if not entity_id:
                stats["errors"].append(f"Row {row_num}: entity_id is required")
                continue

            if not canonical_name:
                stats["errors"].append(f"Row {row_num}: canonical_name is required")
                continue

            if not building:
                stats["errors"].append(f"Row {row_num}: building is required")
                continue

            if not floor:
                stats["errors"].append(f"Row {row_num}: floor is required")
                continue

            if not campus:
                stats["errors"].append(f"Row {row_num}: campus is required")
                continue

            # Optional fields
            aliases = data.get('aliases', [])
            if isinstance(aliases, str):
                # Parse semicolon-separated aliases
                aliases = [a.strip().lower() for a in aliases.split(';') if a.strip()]

            room = str(data.get('room', '')).strip() or None
            department = str(data.get('department', '')).strip() or None
            landmarks = str(data.get('landmarks', '')).strip() or None
            description = str(data.get('description', '')).strip() or None

            status = str(data.get('status', 'active')).strip().lower()
            if status not in ('active', 'inactive'):
                status = 'active'

            validated_entities.append({
                'entity_id': entity_id,
                'canonical_name': canonical_name,
                'aliases': aliases,
                'building': building,
                'floor': floor,
                'room': room,
                'campus': campus,
                'department': department,
                'landmarks': landmarks,
                'description': description,
                'status': status,
                'is_new': entity_id not in self.entities
            })

        # If any validation errors, abort
        if stats["errors"]:
            return False, f"Validation failed: {len(stats['errors'])} error(s)", stats

        # Phase 2: Apply all changes
        for entity_data in validated_entities:
            entity_id = entity_data['entity_id']
            is_new = entity_data['is_new']

            if is_new:
                # Create new entity
                entity = DirectoryEntity(
                    entity_id=entity_id,
                    canonical_name=entity_data['canonical_name'],
                    aliases=entity_data['aliases'],
                    building=entity_data['building'],
                    floor=entity_data['floor'],
                    room=entity_data['room'],
                    campus=entity_data['campus'],
                    department=entity_data['department'],
                    landmarks=entity_data['landmarks'],
                    description=entity_data['description'],
                    status=entity_data['status'],
                    last_updated=datetime.now().isoformat()
                )
                self.entities[entity_id] = entity
                stats["created"] += 1
            else:
                # Update existing entity
                entity = self.entities[entity_id]
                entity.canonical_name = entity_data['canonical_name']
                entity.aliases = entity_data['aliases']
                entity.building = entity_data['building']
                entity.floor = entity_data['floor']
                entity.room = entity_data['room']
                entity.campus = entity_data['campus']
                entity.department = entity_data['department']
                entity.landmarks = entity_data['landmarks']
                entity.description = entity_data['description']
                entity.status = entity_data['status']
                entity.last_updated = datetime.now().isoformat()
                stats["updated"] += 1

        # Rebuild alias index and save
        self._rebuild_alias_index()
        success, save_msg = self.save_entities()

        if not success:
            # Reload from file on save failure
            self.reload()
            return False, f"Import failed: {save_msg}", stats

        total = stats["created"] + stats["updated"]
        return True, f"Successfully imported {total} entities ({stats['created']} created, {stats['updated']} updated)", stats

    # -------------------------------------------------------------------------
    # Phase 47: CampusQueryIndex Integration
    # -------------------------------------------------------------------------

    def get_campus_query_index(self):
        """
        Get or create CampusQueryIndex for structured queries.

        Returns:
            CampusQueryIndex instance with hierarchical indexes

        Note:
            The CampusQueryIndex is created lazily and cached.
            It provides O(1) lookups for structured queries like:
            - "Show all classrooms on Ground Floor"
            - "List all offices in A Building"
            - "What's the nearest restroom?"
        """
        if not hasattr(self, '_campus_index') or self._campus_index is None:
            try:
                from .campus_index import CampusQueryIndex
            except ImportError:
                from campus_index import CampusQueryIndex

            self._campus_index = CampusQueryIndex()
            self._campus_index.load_from_flat_entities(self._json_path)
            logger.info(f"[PHASE47] CampusQueryIndex initialized with {len(self._campus_index.rooms)} rooms")

        return self._campus_index

    def get_rooms_by_type(self, room_type_str: str) -> List[DirectoryEntity]:
        """
        Get all rooms of a specific type.

        Args:
            room_type_str: Room type string (e.g., "classroom", "office", "restroom")

        Returns:
            List of matching DirectoryEntity objects
        """
        try:
            from .campus_schema import RoomType
        except ImportError:
            from campus_schema import RoomType

        index = self.get_campus_query_index()
        room_type = RoomType.from_string(room_type_str)

        rooms = index.get_rooms_by_type(room_type)
        return [self._room_to_entity(room) for room in rooms]

    def get_rooms_by_building(self, building_name: str) -> List[DirectoryEntity]:
        """
        Get all rooms in a building.

        Args:
            building_name: Building name or alias

        Returns:
            List of matching DirectoryEntity objects
        """
        index = self.get_campus_query_index()

        # Resolve building
        building = index.resolve_building(building_name)
        if not building:
            return []

        rooms = index.get_rooms_by_building(building.building_id)
        return [self._room_to_entity(room) for room in rooms]

    def get_rooms_by_floor(self, building_name: str, floor_str: str) -> List[DirectoryEntity]:
        """
        Get all rooms on a specific floor of a building.

        Args:
            building_name: Building name or alias
            floor_str: Floor string (e.g., "Ground Floor", "2nd Floor")

        Returns:
            List of matching DirectoryEntity objects
        """
        try:
            from .campus_schema import FloorLevel
        except ImportError:
            from campus_schema import FloorLevel

        index = self.get_campus_query_index()

        # Resolve building
        building = index.resolve_building(building_name)
        if not building:
            return []

        floor_level = FloorLevel.from_string(floor_str)
        rooms = index.get_rooms_by_building_and_floor(building.building_id, floor_level)
        return [self._room_to_entity(room) for room in rooms]

    def find_nearest(self, reference_alias: str, target_type_str: str, limit: int = 1) -> List[DirectoryEntity]:
        """
        Find nearest rooms of a given type using structural proximity.

        Tiers:
        0. Same Floor
        1. Same Building, Different Floor
        2. Same Campus, Different Building
        3. Different Campus

        Args:
            reference_alias: Alias of reference room
            target_type_str: Type of room to find (e.g., "restroom", "classroom")
            limit: Maximum number of results

        Returns:
            List of nearest matching DirectoryEntity objects
        """
        try:
            from .campus_schema import RoomType
        except ImportError:
            from campus_schema import RoomType

        index = self.get_campus_query_index()

        # Resolve reference room
        reference_room = index.resolve_room(reference_alias)
        if not reference_room:
            return []

        target_type = RoomType.from_string(target_type_str)
        rooms = index.find_nearest(reference_room, target_type, limit)
        return [self._room_to_entity(room) for room in rooms]

    def count_rooms_by_type(self, room_type_str: str) -> int:
        """
        Count rooms of a specific type.

        Args:
            room_type_str: Room type string

        Returns:
            Number of matching rooms
        """
        try:
            from .campus_schema import RoomType
        except ImportError:
            from campus_schema import RoomType

        index = self.get_campus_query_index()
        room_type = RoomType.from_string(room_type_str)
        return index.count_rooms_by_type(room_type)

    def _room_to_entity(self, room) -> DirectoryEntity:
        """
        Convert a Room object to DirectoryEntity for backward compatibility.

        Args:
            room: Room object from CampusQueryIndex

        Returns:
            DirectoryEntity object
        """
        return DirectoryEntity(
            entity_id=room.room_id,
            canonical_name=room.canonical_name,
            aliases=room.aliases,
            building=room.original_building_str or room.building_id,
            floor=room.original_floor_str or room.floor_level.display_name(),
            room=room.room_number,
            campus=room.campus_id.replace("_", " ").title(),
            department=room.department,
            landmarks=room.landmarks,
            description=room.description,
            status=room.status
        )

    def get_index_stats(self) -> Dict:
        """
        Get CampusQueryIndex statistics.

        Returns:
            Dictionary with index statistics
        """
        index = self.get_campus_query_index()
        return index.get_stats()

    def invalidate_campus_index(self) -> None:
        """
        Invalidate the cached CampusQueryIndex.

        Call this after modifying entities to force reloading.
        """
        if hasattr(self, '_campus_index'):
            self._campus_index = None
            logger.info("[PHASE47] CampusQueryIndex cache invalidated")
