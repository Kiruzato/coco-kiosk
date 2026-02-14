"""Clean up re-added test entities from the backfill"""
import json
from datetime import datetime

JSON_PATH = 'data/directory_entities.json'

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

entities = data['entities']
print(f"Before cleanup: {len(entities)} entities")

# These test entities got re-added by the backfill because they were in the CQE index
# (derived from the pre-cleanup data)
test_ids = {
    'AAAAAAAAA', 'AAAAARGRR', 'ATESTBBBB',  # test buildings
    'IP_BUILDING_7F', 'ST_PATRICK_BUILDING_10F', 'ST_PATRICK_BUILDING_5F',  # test floors
}

cleaned = []
removed = []
for e in entities:
    if e['entity_id'] in test_ids:
        removed.append(f"  removed: {e['entity_id']} ({e.get('entity_type', '?')}: {e.get('canonical_name', '?')})")
    else:
        cleaned.append(e)

for r in removed:
    print(r)

data['entities'] = cleaned
data['last_updated'] = datetime.now().isoformat()

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"After cleanup: {len(cleaned)} entities")

# Count by type
types = {}
for e in cleaned:
    t = e.get('entity_type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items()):
    print(f"  {t}: {c}")
