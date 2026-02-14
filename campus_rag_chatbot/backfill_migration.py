"""
One-time migration: Backfill derived entities and clean up test data.

This script:
1. Loads the CQE index to find all campuses/buildings/floors
2. Adds explicit JSON entries for any that are DERIVED-only (not in JSON)
3. Removes test data entities
4. Saves the updated JSON
"""
import sys, json, copy
from datetime import datetime
sys.path.insert(0, '.')

from campus_index import CampusQueryIndex

JSON_PATH = 'data/directory_entities.json'

# Load raw JSON
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

entities = data['entities']
existing_ids = {e['entity_id'] for e in entities}

print(f"Before: {len(entities)} entities")

# Load CQE index to discover derived entities
idx = CampusQueryIndex()
idx.load_from_flat_entities(JSON_PATH)

# --- TEST DATA TO REMOVE ---
test_entity_ids = {
    # Test rooms
    'AAAADWDWD', 'ATEST', 'CHEM',
    # Test buildings (0 rooms)
    'AAAAAAAAA', 'AAAAARGRR', 'ATESTBBBB',
    # Test floors (0 rooms)
    'IP_BUILDING_7F', 'ST_PATRICK_BUILDING_10F', 'ST_PATRICK_BUILDING_5F',
    # Test departments (all 0 rooms, all test names)
    'ADTEST', 'QWDWQD', 'ARCHITECTURE_DEPARTMENT',
    'COLLEGE_OF_NURSING', 'ENGINEERING_DEPARTMENT',
}

removed = []
entities_clean = []
for e in entities:
    if e['entity_id'] in test_entity_ids:
        removed.append(f"  removed: {e['entity_id']} ({e.get('entity_type', 'room')}: {e.get('canonical_name', '?')})")
    else:
        entities_clean.append(e)

for r in removed:
    print(r)

entities = entities_clean
existing_ids = {e['entity_id'] for e in entities}

# --- BACKFILL CAMPUSES ---
added = []
now = datetime.now().isoformat()

for campus_id, campus in sorted(idx.campuses.items()):
    if campus_id not in existing_ids:
        entity = {
            'entity_id': campus_id,
            'canonical_name': campus.name,
            'aliases': campus.aliases if campus.aliases else [campus.name.lower()],
            'building': '',
            'floor': '',
            'room': None,
            'campus': campus.name,
            'department': None,
            'landmarks': None,
            'description': None,
            'tags': [],
            'entity_type': 'campus',
            'status': 'active',
            'last_updated': now,
            'level_number': None,
            'child_ids': campus.building_ids,
            'office_room_ids': [],
        }
        entities.append(entity)
        existing_ids.add(campus_id)
        added.append(f"  added campus: {campus_id} ({campus.name})")

# --- BACKFILL BUILDINGS ---
for building_id, building in sorted(idx.buildings.items()):
    if building_id not in existing_ids:
        entity = {
            'entity_id': building_id,
            'canonical_name': building.name,
            'aliases': building.aliases if building.aliases else [building.name.lower()],
            'building': building.name,
            'floor': '',
            'room': None,
            'campus': next((c.name for c in idx.campuses.values() if building_id in c.building_ids), 'Main Campus'),
            'department': None,
            'landmarks': None,
            'description': None,
            'tags': [],
            'entity_type': 'building',
            'status': 'active',
            'last_updated': now,
            'level_number': None,
            'child_ids': building.floor_ids,
            'office_room_ids': [],
        }
        entities.append(entity)
        existing_ids.add(building_id)
        added.append(f"  added building: {building_id} ({building.name})")

# --- BACKFILL FLOORS ---
for floor_id, floor in sorted(idx.floors.items()):
    if floor_id not in existing_ids:
        building = idx.buildings.get(floor.building_id)
        building_name = building.name if building else ''
        campus_name = ''
        if building:
            campus = next((c for c in idx.campuses.values() if floor.building_id in c.building_ids), None)
            campus_name = campus.name if campus else 'Main Campus'
        
        entity = {
            'entity_id': floor_id,
            'canonical_name': floor.display_name,
            'aliases': floor.aliases if floor.aliases else [],
            'building': building_name,
            'floor': floor.display_name,
            'room': None,
            'campus': campus_name,
            'department': None,
            'landmarks': None,
            'description': None,
            'tags': [],
            'entity_type': 'floor',
            'status': 'active',
            'last_updated': now,
            'level_number': floor.level_number,
            'child_ids': [],
            'office_room_ids': [],
        }
        entities.append(entity)
        existing_ids.add(floor_id)
        added.append(f"  added floor: {floor_id} ({floor.display_name}, building={floor.building_id})")

for a in added:
    print(a)

# --- SAVE ---
data['entities'] = entities
data['last_updated'] = now

# Backup first
backup_path = JSON_PATH + '.backup'
with open(backup_path, 'w', encoding='utf-8') as f:
    json.dump(json.load(open(JSON_PATH, 'r', encoding='utf-8')), f, indent=2, ensure_ascii=False)

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nAfter: {len(entities)} entities")
print(f"Removed: {len(removed)}, Added: {len(added)}")
print(f"Backup saved to: {backup_path}")

# Verify
print("\n--- Verification ---")
idx2 = CampusQueryIndex()
idx2.load_from_flat_entities(JSON_PATH)
print(f"Campuses: {len(idx2.campuses)}")
print(f"Buildings: {len(idx2.buildings)}")
print(f"Floors: {len(idx2.floors)}")
print(f"Rooms: {len(idx2.rooms)}")
print(f"Outdoor: {len(idx2.outdoor_locations)}")
print(f"Departments: {len(idx2.departments)}")
