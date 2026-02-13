"""
Entity Manager Service
======================
High-level entity management with validation and CQE index rebuild.

Phase 55-56: Admin Directory Management System

Provides:
- EntityManager: Wraps EntityRegistry with validation + index management
- Validation rules for all entity fields
- Tag normalization (lowercase, trimmed, no duplicates)
- Automatic CQE index rebuild after CRUD operations
- OutdoorLocation support via _OUTDOOR marker convention
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .entity_registry import EntityRegistry, DirectoryEntity
    from .campus_index import CampusQueryIndex
except ImportError:
    from entity_registry import EntityRegistry, DirectoryEntity
    from campus_index import CampusQueryIndex

logger = logging.getLogger(__name__)

# Constants
OUTDOOR_MARKER = "_OUTDOOR"

# Valid floor patterns
FLOOR_PATTERNS = [
    r"^ground\s*floor$",
    r"^basement$",
    r"^(\d+)(st|nd|rd|th)\s*floor$",
    r"^floor\s*(\d+)$",
    r"^[bgm]?\d+[f]?$",  # B1, G, M, 1F, 2F etc.
    r"^_outdoor$",  # Special marker for outdoor locations
]


@dataclass
class ValidationResult:
    """Result of entity validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    normalized_data: Optional[Dict[str, Any]] = None


class EntityManager:
    """
    High-level entity management with validation and index rebuild.

    Wraps EntityRegistry with additional safety guarantees:
    - Field validation before any CRUD operation
    - Tag normalization (lowercase, trimmed, no duplicates)
    - Automatic CQE index rebuild after changes
    - Reference validation (building/floor/campus existence)
    """

    def __init__(
        self,
        registry: EntityRegistry,
        index_path: str,
        on_index_rebuild: Optional[Callable[[], None]] = None
    ):
        """
        Initialize EntityManager.

        Args:
            registry: EntityRegistry instance
            index_path: Path to directory_entities.json for index rebuilding
            on_index_rebuild: Optional callback after index rebuild
        """
        self.registry = registry
        self.index_path = index_path
        self._on_index_rebuild = on_index_rebuild
        self._index: Optional[CampusQueryIndex] = None

    def get_index(self) -> CampusQueryIndex:
        """Get or create the CampusQueryIndex."""
        if self._index is None:
            self._index = CampusQueryIndex()
            self._index.load_from_flat_entities(self.index_path)
        return self._index

    def rebuild_index(self) -> Tuple[bool, Dict[str, int]]:
        """
        Force rebuild the CQE index from JSON.

        Returns:
            Tuple of (success, stats dict with room/building/campus counts)
        """
        try:
            self._index = CampusQueryIndex()
            self._index.load_from_flat_entities(self.index_path)

            stats = {
                "rooms": len(self._index.rooms),
                "buildings": len(self._index.buildings),
                "campuses": len(self._index.campuses),
                "outdoor_locations": len(self._index.outdoor_locations),
                "aliases": (
                    len(self._index.alias_to_room) +
                    len(self._index.alias_to_building) +
                    len(self._index.alias_to_campus) +
                    len(self._index.alias_to_outdoor)
                )
            }

            logger.info(f"[EntityManager] Index rebuilt: {stats}")

            if self._on_index_rebuild:
                self._on_index_rebuild()

            return True, stats
        except Exception as e:
            logger.error(f"[EntityManager] Index rebuild failed: {e}")
            return False, {}

    def get_index_stats(self) -> Dict[str, int]:
        """Get current index statistics."""
        index = self.get_index()
        return {
            "rooms": len(index.rooms),
            "active_rooms": len([r for r in index.rooms.values() if r.status == "active"]),
            "buildings": len(index.buildings),
            "campuses": len(index.campuses),
            "outdoor_locations": len(index.outdoor_locations),
            "departments": len(index.departments),
            "total_aliases": (
                len(index.alias_to_room) +
                len(index.alias_to_building) +
                len(index.alias_to_campus) +
                len(index.alias_to_outdoor)
            )
        }

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_entity(
        self,
        data: Dict[str, Any],
        is_update: bool = False,
        existing_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate entity data before create/update.

        Args:
            data: Entity data dict
            is_update: True if this is an update operation
            existing_id: Entity ID being updated (for uniqueness check)

        Returns:
            ValidationResult with errors, warnings, and normalized data
        """
        errors = []
        warnings = []
        normalized = {}

        # Get current index for reference validation
        index = self.get_index()

        # --- entity_id validation ---
        entity_id = str(data.get('entity_id', '')).upper().strip()
        if not is_update:
            if not entity_id:
                errors.append("entity_id is required")
            elif not re.match(r'^[A-Z0-9_]+$', entity_id):
                errors.append("entity_id must contain only letters, numbers, and underscores")
            elif entity_id in self.registry.entities:
                errors.append(f"entity_id '{entity_id}' already exists")
        normalized['entity_id'] = entity_id

        # --- canonical_name validation ---
        canonical_name = str(data.get('canonical_name', '')).strip()
        if not is_update or 'canonical_name' in data:
            if not canonical_name:
                errors.append("canonical_name is required")
        normalized['canonical_name'] = canonical_name

        # --- Check if outdoor location ---
        is_outdoor = (
            str(data.get('building', '')).upper().strip() == OUTDOOR_MARKER or
            str(data.get('floor', '')).upper().strip() == OUTDOOR_MARKER
        )

        # --- building validation ---
        building = str(data.get('building', '')).strip()
        if not is_update or 'building' in data:
            if not building:
                errors.append("building is required")
            elif building.upper() != OUTDOOR_MARKER:
                # Check if building exists
                existing_buildings = set(b.name for b in index.buildings.values())
                if building not in existing_buildings:
                    warnings.append(f"Building '{building}' does not exist - will be created")
        normalized['building'] = building

        # --- floor validation ---
        floor = str(data.get('floor', '')).strip()
        if not is_update or 'floor' in data:
            if not floor:
                errors.append("floor is required")
            elif floor.upper() != OUTDOOR_MARKER:
                # Validate floor format
                if not self._is_valid_floor_format(floor):
                    warnings.append(f"Floor '{floor}' has non-standard format")
        normalized['floor'] = floor

        # --- campus validation ---
        campus = str(data.get('campus', '')).strip()
        if not is_update or 'campus' in data:
            if not campus:
                errors.append("campus is required")
            else:
                existing_campuses = set(c.name for c in index.campuses.values())
                if campus not in existing_campuses:
                    warnings.append(f"Campus '{campus}' does not exist - will be created")
        normalized['campus'] = campus

        # --- room validation (optional) ---
        room = data.get('room')
        if room:
            room = str(room).strip()
            if room and not re.match(r'^[A-Za-z0-9\-\s]+$', room):
                warnings.append(f"Room '{room}' contains special characters")
        normalized['room'] = room if room else None

        # --- aliases validation ---
        aliases = data.get('aliases', [])
        if isinstance(aliases, str):
            # Handle comma or semicolon separated strings
            aliases = [a.strip() for a in re.split(r'[;,]', aliases) if a.strip()]
        normalized_aliases = self.normalize_aliases(aliases)
        normalized['aliases'] = normalized_aliases

        # --- tags validation ---
        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in re.split(r'[;,]', tags) if t.strip()]
        original_tags = list(tags) if tags else []
        normalized_tags = self.normalize_tags(tags)
        if original_tags and normalized_tags != original_tags:
            warnings.append(f"Tags normalized: {original_tags} -> {normalized_tags}")
        normalized['tags'] = normalized_tags

        # --- department validation (optional) ---
        department = data.get('department')
        if department:
            department = str(department).strip()
        normalized['department'] = department if department else None

        # --- landmarks validation (optional) ---
        landmarks = data.get('landmarks')
        if landmarks:
            landmarks = str(landmarks).strip()
        normalized['landmarks'] = landmarks if landmarks else None

        # --- description validation (optional) ---
        description = data.get('description')
        if description:
            description = str(description).strip()
        normalized['description'] = description if description else None

        # --- status validation ---
        status = str(data.get('status', 'active')).lower().strip()
        if status not in ('active', 'inactive'):
            errors.append(f"status must be 'active' or 'inactive', got '{status}'")
        normalized['status'] = status

        # Return result
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized if len(errors) == 0 else None
        )

    def normalize_tags(self, tags: List[str]) -> List[str]:
        """
        Normalize tags: lowercase, trimmed, no duplicates, sorted.

        Args:
            tags: List of tag strings

        Returns:
            Normalized list of tags
        """
        if not tags:
            return []

        normalized = []
        seen = set()
        for tag in tags:
            if tag:
                clean = str(tag).lower().strip()
                # Remove any special characters except hyphen and underscore
                clean = re.sub(r'[^\w\s\-]', '', clean)
                clean = clean.strip()
                if clean and clean not in seen:
                    normalized.append(clean)
                    seen.add(clean)
        return sorted(normalized)

    def normalize_aliases(self, aliases: List[str]) -> List[str]:
        """
        Normalize aliases: lowercase, trimmed, no duplicates.

        Args:
            aliases: List of alias strings

        Returns:
            Normalized list of aliases
        """
        if not aliases:
            return []

        normalized = []
        seen = set()
        for alias in aliases:
            if alias:
                clean = str(alias).lower().strip()
                if clean and clean not in seen:
                    normalized.append(clean)
                    seen.add(clean)
        return normalized

    def _is_valid_floor_format(self, floor: str) -> bool:
        """Check if floor string matches valid patterns."""
        floor_lower = floor.lower().strip()
        for pattern in FLOOR_PATTERNS:
            if re.match(pattern, floor_lower, re.IGNORECASE):
                return True
        return False

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_entity(self, data: Dict[str, Any]) -> Tuple[bool, str, ValidationResult]:
        """
        Create a new entity with validation.

        Args:
            data: Entity data dict

        Returns:
            Tuple of (success, message, validation_result)
        """
        # Validate
        result = self.validate_entity(data, is_update=False)
        if not result.valid:
            return False, f"Validation failed: {'; '.join(result.errors)}", result

        # Extract normalized data
        nd = result.normalized_data

        # Create via registry
        success, message = self.registry.add_entity(
            entity_id=nd['entity_id'],
            canonical_name=nd['canonical_name'],
            aliases=nd['aliases'],
            building=nd['building'],
            floor=nd['floor'],
            room=nd['room'],
            campus=nd['campus'],
            department=nd['department'],
            landmarks=nd['landmarks'],
            description=nd['description']
        )

        if success:
            # Rebuild index
            self.rebuild_index()
            logger.info(f"[EntityManager] Created entity: {nd['entity_id']}")

        return success, message, result

    def update_entity(
        self,
        entity_id: str,
        data: Dict[str, Any]
    ) -> Tuple[bool, str, ValidationResult]:
        """
        Update an existing entity with validation.

        Args:
            entity_id: Entity to update
            data: Fields to update

        Returns:
            Tuple of (success, message, validation_result)
        """
        entity_id = entity_id.upper().strip()

        # Check entity exists
        if entity_id not in self.registry.entities:
            return False, f"Entity '{entity_id}' not found", ValidationResult(
                valid=False, errors=[f"Entity '{entity_id}' not found"], warnings=[]
            )

        # Merge with existing data for validation
        existing = self.registry.entities[entity_id]
        merged = {
            'entity_id': entity_id,
            'canonical_name': data.get('canonical_name', existing.canonical_name),
            'aliases': data.get('aliases', existing.aliases),
            'building': data.get('building', existing.building),
            'floor': data.get('floor', existing.floor),
            'room': data.get('room', existing.room),
            'campus': data.get('campus', existing.campus),
            'department': data.get('department', existing.department),
            'landmarks': data.get('landmarks', existing.landmarks),
            'description': data.get('description', existing.description),
            'status': data.get('status', existing.status),
            'tags': data.get('tags', []),  # Tags not in DirectoryEntity yet
        }

        # Validate
        result = self.validate_entity(merged, is_update=True, existing_id=entity_id)
        if not result.valid:
            return False, f"Validation failed: {'; '.join(result.errors)}", result

        # Extract fields to update
        nd = result.normalized_data

        # Update via registry
        success, message = self.registry.update_entity(
            entity_id=entity_id,
            canonical_name=nd['canonical_name'] if 'canonical_name' in data else None,
            aliases=nd['aliases'] if 'aliases' in data else None,
            building=nd['building'] if 'building' in data else None,
            floor=nd['floor'] if 'floor' in data else None,
            room=nd['room'] if 'room' in data else None,
            campus=nd['campus'] if 'campus' in data else None,
            department=nd['department'] if 'department' in data else None,
            landmarks=nd['landmarks'] if 'landmarks' in data else None,
            description=nd['description'] if 'description' in data else None,
            status=nd['status'] if 'status' in data else None
        )

        if success:
            # Rebuild index
            self.rebuild_index()
            logger.info(f"[EntityManager] Updated entity: {entity_id}")

        return success, message, result

    def delete_entity(
        self,
        entity_id: str,
        hard: bool = False
    ) -> Tuple[bool, str]:
        """
        Delete an entity (soft or hard delete).

        Args:
            entity_id: Entity to delete
            hard: If True, permanently remove; if False, set status to inactive

        Returns:
            Tuple of (success, message)
        """
        success, message = self.registry.delete_entity(entity_id, hard=hard)

        if success:
            # Rebuild index
            self.rebuild_index()
            logger.info(f"[EntityManager] Deleted entity: {entity_id} (hard={hard})")

        return success, message

    def bulk_import(
        self,
        entities_data: List[Dict[str, Any]]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Import multiple entities with validation.

        Args:
            entities_data: List of entity dicts

        Returns:
            Tuple of (success, message, stats)
        """
        # Pre-validate all entities
        all_errors = []
        all_warnings = []
        validated_data = []

        for idx, data in enumerate(entities_data):
            row_num = idx + 2  # +2 for 1-indexed and header row
            entity_id = str(data.get('entity_id', '')).upper().strip()
            is_update = entity_id in self.registry.entities

            result = self.validate_entity(data, is_update=is_update)

            if not result.valid:
                for error in result.errors:
                    all_errors.append(f"Row {row_num}: {error}")
            else:
                validated_data.append(result.normalized_data)
                for warning in result.warnings:
                    all_warnings.append(f"Row {row_num}: {warning}")

        # If any errors, abort
        if all_errors:
            return False, f"Validation failed with {len(all_errors)} error(s)", {
                "errors": all_errors,
                "warnings": all_warnings,
                "created": 0,
                "updated": 0
            }

        # Import via registry
        success, message, stats = self.registry.bulk_import(entities_data)

        if success:
            # Rebuild index
            self.rebuild_index()
            logger.info(f"[EntityManager] Bulk import: {stats}")
            stats['warnings'] = all_warnings

        return success, message, stats

    # =========================================================================
    # Query helpers
    # =========================================================================

    def get_all_entities(self) -> List[DirectoryEntity]:
        """Get all entities."""
        return self.registry.get_all_entities()

    def get_active_entities(self) -> List[DirectoryEntity]:
        """Get all active entities."""
        return self.registry.get_active_entities()

    def get_entity(self, entity_id: str) -> Optional[DirectoryEntity]:
        """Get a single entity by ID."""
        return self.registry.get_by_id(entity_id)

    def get_existing_buildings(self) -> List[str]:
        """Get list of existing building names."""
        index = self.get_index()
        return sorted(set(b.name for b in index.buildings.values()))

    def get_existing_campuses(self) -> List[str]:
        """Get list of existing campus names."""
        index = self.get_index()
        return sorted(set(c.name for c in index.campuses.values()))

    def get_existing_floors(self) -> List[str]:
        """Get list of existing floor display names."""
        index = self.get_index()
        return sorted(set(f.display_name for f in index.floors.values()))


# =============================================================================
# Convenience Functions
# =============================================================================

_manager_instance: Optional[EntityManager] = None


def get_entity_manager(
    registry: Optional[EntityRegistry] = None,
    index_path: Optional[str] = None
) -> EntityManager:
    """
    Get or create the singleton EntityManager.

    Args:
        registry: EntityRegistry (required on first call)
        index_path: Path to entities JSON (required on first call)

    Returns:
        EntityManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        if registry is None or index_path is None:
            raise ValueError("registry and index_path required on first call")
        _manager_instance = EntityManager(registry, index_path)

    return _manager_instance
