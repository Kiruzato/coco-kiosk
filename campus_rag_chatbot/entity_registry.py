"""
Entity Registry for Directory Locations
========================================
Manages structured directory entities with canonical names and aliases.

This module provides:
- DirectoryEntity: Data class for location entities
- EntityRegistry: In-memory registry with fast alias-based lookup

Used by entity_resolver.py to resolve directory queries to specific locations.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


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
        landmarks: Navigation hints to help find the location
        description: Brief description of the location's purpose
    """
    entity_id: str
    canonical_name: str
    aliases: List[str]
    building: str
    floor: str
    room: Optional[str]
    landmarks: Optional[str]
    description: Optional[str]


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
                    landmarks=entry.get('landmarks'),
                    description=entry.get('description')
                )

                # Store entity by ID
                self.entities[entity.entity_id] = entity

                # Index canonical name (normalized)
                canonical_normalized = entity.canonical_name.lower().strip()
                self.alias_index[canonical_normalized] = entity.entity_id

                # Index all aliases (normalized)
                for alias in entity.aliases:
                    alias_normalized = alias.lower().strip()
                    if alias_normalized in self.alias_index:
                        # Log collision but don't override
                        existing = self.alias_index[alias_normalized]
                        logger.debug(
                            f"Alias collision: '{alias_normalized}' maps to both "
                            f"{existing} and {entity.entity_id}"
                        )
                    else:
                        self.alias_index[alias_normalized] = entity.entity_id

            logger.info(
                f"Loaded {len(self.entities)} directory entities with "
                f"{len(self.alias_index)} aliases"
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
