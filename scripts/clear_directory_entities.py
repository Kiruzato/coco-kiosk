"""
Clear all directory entities from directory_entities.json.
Creates a backup before clearing.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

# Paths
ENTITIES_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\data\directory_entities.json")

print("=" * 60)
print("Directory Entities Cleaner")
print("=" * 60)

# Check if file exists
if not ENTITIES_PATH.exists():
    print(f"ERROR: File not found: {ENTITIES_PATH}")
    exit(1)

# Load current data
with open(ENTITIES_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

current_count = len(data.get('entities', []))
print(f"Current entities: {current_count}")

# Create backup
backup_path = ENTITIES_PATH.with_suffix('.json.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
shutil.copy(ENTITIES_PATH, backup_path)
print(f"Backup created: {backup_path}")

# Clear entities
data['entities'] = []
data['last_updated'] = datetime.now().isoformat()

# Save cleared file
with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nCleared all {current_count} directory entities.")
print(f"File saved: {ENTITIES_PATH}")
print("\nYou can now upload your real directory entities via the Admin UI.")
print("=" * 60)
