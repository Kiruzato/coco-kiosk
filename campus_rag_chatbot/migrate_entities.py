"""
Entity Migration Script
=======================
Migrates flat v1.x directory_entities.json to hierarchical v2.0 format
and validates the CampusQueryIndex.

Phase 47: Data Model Foundation

Usage:
    python migrate_entities.py [--dry-run] [--verbose]

Options:
    --dry-run   Show what would be migrated without making changes
    --verbose   Show detailed migration information
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from campus_schema import (
    RoomType, FloorLevel,
    generate_building_id, generate_floor_id, generate_campus_id
)
from campus_index import CampusQueryIndex

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_entities(entities_path: str) -> Dict:
    """
    Analyze existing entities and generate migration statistics.

    Returns:
        Dictionary with analysis results
    """
    with open(entities_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entities = data.get('entities', [])

    stats = {
        'total_entities': len(entities),
        'active_entities': 0,
        'inactive_entities': 0,
        'campuses': set(),
        'buildings': set(),
        'floors': set(),
        'departments': set(),
        'room_types_inferred': defaultdict(int),
        'missing_fields': defaultdict(int),
        'alias_count': 0,
        'entities_by_campus': defaultdict(int),
        'entities_by_building': defaultdict(int),
        'entities_by_floor': defaultdict(int),
    }

    for entity in entities:
        # Count active/inactive
        status = entity.get('status', 'active')
        if status == 'active':
            stats['active_entities'] += 1
        else:
            stats['inactive_entities'] += 1

        # Collect unique values
        campus = entity.get('campus', 'Main Campus')
        building = entity.get('building', 'Unknown Building')
        floor = entity.get('floor', 'Ground Floor')
        department = entity.get('department')

        stats['campuses'].add(campus)
        stats['buildings'].add(building)
        stats['floors'].add(floor)
        if department:
            stats['departments'].add(department)

        stats['entities_by_campus'][campus] += 1
        stats['entities_by_building'][building] += 1
        stats['entities_by_floor'][floor] += 1

        # Count aliases
        aliases = entity.get('aliases', [])
        if isinstance(aliases, list):
            for alias in aliases:
                if ',' in alias:
                    stats['alias_count'] += len(alias.split(','))
                else:
                    stats['alias_count'] += 1
        elif isinstance(aliases, str):
            stats['alias_count'] += len(aliases.split(';'))

        # Check missing fields
        required_fields = ['entity_id', 'canonical_name', 'building', 'floor']
        for field in required_fields:
            if not entity.get(field):
                stats['missing_fields'][field] += 1

        # Infer room type
        room_type = _infer_room_type_for_stats(entity)
        stats['room_types_inferred'][room_type.value] += 1

    # Convert sets to lists for JSON serialization
    stats['campuses'] = sorted(stats['campuses'])
    stats['buildings'] = sorted(stats['buildings'])
    stats['floors'] = sorted(stats['floors'])
    stats['departments'] = sorted(stats['departments'])
    stats['room_types_inferred'] = dict(stats['room_types_inferred'])
    stats['missing_fields'] = dict(stats['missing_fields'])
    stats['entities_by_campus'] = dict(stats['entities_by_campus'])
    stats['entities_by_building'] = dict(stats['entities_by_building'])
    stats['entities_by_floor'] = dict(stats['entities_by_floor'])

    return stats


def _infer_room_type_for_stats(entity: dict) -> RoomType:
    """Infer room type from entity data (same logic as campus_index)."""
    canonical = entity.get('canonical_name', '').lower()
    entity_id = entity.get('entity_id', '').lower()

    if any(kw in canonical for kw in ['classroom', 'lecture', 'class room']):
        return RoomType.CLASSROOM
    if 'class' in entity_id and 'room' not in entity_id:
        return RoomType.CLASSROOM
    if 'office' in canonical:
        return RoomType.OFFICE
    if any(kw in canonical for kw in ['laboratory', 'lab ', ' lab', 'computer lab']):
        return RoomType.LABORATORY
    if any(kw in canonical for kw in ['comfort room', 'restroom', 'cr', 'toilet']):
        return RoomType.RESTROOM
    if 'crm' in entity_id or 'cr_' in entity_id:
        return RoomType.RESTROOM
    if any(kw in canonical for kw in ['conference', 'meeting room']):
        return RoomType.CONFERENCE
    if 'library' in canonical:
        return RoomType.LIBRARY
    if any(kw in canonical for kw in ['canteen', 'cafeteria', 'gym', 'clinic', 'chapel', 'auditorium', 'court']):
        return RoomType.FACILITY
    if any(kw in canonical for kw in ['electric', 'server', 'maintenance', 'storage']):
        return RoomType.UTILITY

    return RoomType.UNKNOWN


def validate_migration(entities_path: str) -> Tuple[bool, Dict]:
    """
    Validate that migration would succeed by loading into CampusQueryIndex.

    Returns:
        Tuple of (success, validation_results)
    """
    index = CampusQueryIndex()
    success = index.load_from_flat_entities(entities_path)

    if not success:
        return False, {'error': 'Failed to load entities into index'}

    # Validation checks
    results = {
        'success': True,
        'errors': [],
        'warnings': [],
        'stats': index.get_stats(),
        'index_coverage': {
            'rooms_with_aliases': len(index.alias_to_room),
            'buildings_indexed': len(index.buildings),
            'campuses_indexed': len(index.campuses),
            'room_types_indexed': len([rt for rt in RoomType if index.rooms_by_type.get(rt)]),
        }
    }

    # Check for rooms without aliases
    rooms_without_aliases = [
        r.room_id for r in index.rooms.values()
        if not r.aliases and r.status == 'active'
    ]
    if rooms_without_aliases:
        results['warnings'].append(
            f"{len(rooms_without_aliases)} active rooms have no aliases"
        )

    # Check for unknown room types
    unknown_rooms = [
        r.room_id for r in index.rooms.values()
        if r.room_type == RoomType.UNKNOWN and r.status == 'active'
    ]
    if unknown_rooms:
        results['warnings'].append(
            f"{len(unknown_rooms)} active rooms have UNKNOWN room type"
        )

    # Test structural proximity
    test_rooms = list(index.rooms.values())[:5]
    for room in test_rooms:
        nearest = index.find_nearest(room, RoomType.RESTROOM, limit=1)
        # Just verify it doesn't crash

    return True, results


def generate_hierarchical_json(entities_path: str, output_path: str) -> bool:
    """
    Generate hierarchical v2.0 JSON from flat entities.

    The v2.0 format nests buildings under campuses, floors under buildings, etc.
    This is optional - the CampusQueryIndex can load either format.

    Args:
        entities_path: Path to v1.x directory_entities.json
        output_path: Path for v2.0 output file

    Returns:
        True if successful
    """
    index = CampusQueryIndex()
    if not index.load_from_flat_entities(entities_path):
        return False

    # Build hierarchical structure
    hierarchical = {
        'version': '2.0',
        'schema': 'hierarchical',
        'generated': datetime.now().isoformat(),
        'campuses': []
    }

    for campus_id, campus in sorted(index.campuses.items()):
        campus_data = {
            'campus_id': campus.campus_id,
            'name': campus.name,
            'aliases': campus.aliases,
            'buildings': []
        }

        for building_id in campus.building_ids:
            building = index.buildings.get(building_id)
            if not building:
                continue

            building_data = {
                'building_id': building.building_id,
                'name': building.name,
                'aliases': building.aliases,
                'floors': []
            }

            for floor_id in building.floor_ids:
                floor = index.floors.get(floor_id)
                if not floor:
                    continue

                floor_data = {
                    'floor_id': floor.floor_id,
                    'level': floor.level.value,
                    'display_name': floor.display_name,
                    'rooms': []
                }

                for room_id in floor.room_ids:
                    room = index.rooms.get(room_id)
                    if not room:
                        continue

                    room_data = {
                        'room_id': room.room_id,
                        'room_number': room.room_number,
                        'room_type': room.room_type.value,
                        'canonical_name': room.canonical_name,
                        'aliases': room.aliases,
                        'department': room.department,
                        'landmarks': room.landmarks,
                        'description': room.description,
                        'status': room.status
                    }
                    floor_data['rooms'].append(room_data)

                building_data['floors'].append(floor_data)

            campus_data['buildings'].append(building_data)

        hierarchical['campuses'].append(campus_data)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(hierarchical, f, indent=2, ensure_ascii=False)

    logger.info(f"Generated hierarchical JSON: {output_path}")
    return True


def print_analysis_report(stats: Dict) -> None:
    """Print formatted analysis report."""
    print("\n" + "=" * 60)
    print("ENTITY MIGRATION ANALYSIS REPORT")
    print("=" * 60)

    print(f"\n[ENTITY COUNTS]")
    print(f"   Total entities:    {stats['total_entities']}")
    print(f"   Active entities:   {stats['active_entities']}")
    print(f"   Inactive entities: {stats['inactive_entities']}")
    print(f"   Total aliases:     {stats['alias_count']}")

    print(f"\n[HIERARCHY STATS]")
    print(f"   Campuses:    {len(stats['campuses'])}")
    for campus in stats['campuses']:
        count = stats['entities_by_campus'].get(campus, 0)
        print(f"     - {campus}: {count} entities")

    print(f"   Buildings:   {len(stats['buildings'])}")
    print(f"   Floor types: {len(stats['floors'])}")
    print(f"   Departments: {len(stats['departments'])}")

    print(f"\n[ROOM TYPE INFERENCE]")
    for room_type, count in sorted(stats['room_types_inferred'].items(), key=lambda x: -x[1]):
        print(f"   {room_type:15s}: {count:4d}")

    if stats['missing_fields']:
        print(f"\n[WARNING] MISSING FIELDS:")
        for field, count in stats['missing_fields'].items():
            print(f"   {field}: {count} entities")

    print("\n" + "=" * 60)


def print_validation_report(results: Dict) -> None:
    """Print formatted validation report."""
    print("\n" + "=" * 60)
    print("MIGRATION VALIDATION REPORT")
    print("=" * 60)

    print(f"\n[OK] Index loaded successfully")

    stats = results.get('stats', {})
    print(f"\n[INDEX STATS]")
    print(f"   Rooms indexed:     {stats.get('rooms', 0)}")
    print(f"   Active rooms:      {stats.get('active_rooms', 0)}")
    print(f"   Buildings indexed: {stats.get('buildings', 0)}")
    print(f"   Campuses indexed:  {stats.get('campuses', 0)}")
    print(f"   Total aliases:     {stats.get('aliases', 0)}")

    coverage = results.get('index_coverage', {})
    print(f"\n[INDEX COVERAGE]")
    print(f"   Rooms with aliases: {coverage.get('rooms_with_aliases', 0)}")
    print(f"   Room types indexed: {coverage.get('room_types_indexed', 0)}")

    if results.get('warnings'):
        print(f"\n[WARNINGS]")
        for warning in results['warnings']:
            print(f"   - {warning}")

    if results.get('errors'):
        print(f"\n[ERRORS]")
        for error in results['errors']:
            print(f"   - {error}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate flat entities to hierarchical CampusQueryIndex'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed migration information'
    )
    parser.add_argument(
        '--generate-v2',
        action='store_true',
        help='Generate hierarchical v2.0 JSON file'
    )
    parser.add_argument(
        '--entities-path',
        type=str,
        default='data/directory_entities.json',
        help='Path to directory_entities.json'
    )

    args = parser.parse_args()

    # Resolve path
    script_dir = Path(__file__).parent
    entities_path = script_dir / args.entities_path

    if not entities_path.exists():
        logger.error(f"Entities file not found: {entities_path}")
        sys.exit(1)

    print(f"\n[FILE] Analyzing: {entities_path}")

    # Step 1: Analyze existing entities
    stats = analyze_entities(str(entities_path))
    print_analysis_report(stats)

    # Step 2: Validate migration
    print("\n[VALIDATING] Migration...")
    success, results = validate_migration(str(entities_path))

    if not success:
        logger.error("Migration validation failed!")
        print_validation_report(results)
        sys.exit(1)

    print_validation_report(results)

    # Step 3: Generate v2.0 JSON if requested
    if args.generate_v2 and not args.dry_run:
        output_path = entities_path.parent / 'directory_entities_v2.json'
        print(f"\n[GENERATING] Hierarchical JSON: {output_path}")
        if generate_hierarchical_json(str(entities_path), str(output_path)):
            print("[OK] Hierarchical JSON generated successfully")
        else:
            print("[ERROR] Failed to generate hierarchical JSON")

    print("\n[OK] Migration validation complete!")
    print("   The CampusQueryIndex can load existing flat entities.")
    print("   No changes to directory_entities.json required.")


if __name__ == '__main__':
    main()
