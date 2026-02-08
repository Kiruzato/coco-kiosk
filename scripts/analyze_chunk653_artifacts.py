"""
Analyze Current PDF Parsing Artifacts
======================================
Show the exact artifacts in chunk 653 to inform normalization design
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*80)
print("ANALYZING PDF PARSING ARTIFACTS IN CHUNK 653")
print("="*80)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Find chunk 653 (the DEANS chunk)
all_docs = doc_manager.vector_store.docstore._dict

chunk_653 = None
for doc_id, doc in all_docs.items():
    if doc.metadata.get('chunk_id') == 653:
        chunk_653 = doc
        break

if not chunk_653:
    print("ERROR: Chunk 653 not found")
    sys.exit(1)

content = chunk_653.metadata.get('original_text', chunk_653.page_content)

print(f"\nChunk 653 Found:")
print(f"  Section: {chunk_653.metadata.get('section')}")
print(f"  Pages: {chunk_653.metadata.get('page_numbers')}")
print(f"  Length: {len(content)} chars")
print(f"\n{'='*80}")
print("RAW CONTENT (with visible whitespace):")
print(f"{'='*80}\n")

# Show raw content with visible whitespace
repr_content = repr(content)
print(repr_content)

print(f"\n{'='*80}")
print("LINE-BY-LINE ANALYSIS:")
print(f"{'='*80}\n")

lines = content.split('\n')
for i, line in enumerate(lines, 1):
    # Show line with length and leading/trailing spaces
    leading = len(line) - len(line.lstrip())
    trailing = len(line) - len(line.rstrip())
    
    dean_names = ['MATRIANO', 'YAP', 'GONZALES', 'GUTIERREZ', 'ALMAZAN', 'CAPILI']
    has_dean = any(name in line.upper() for name in dean_names)
    
    marker = " ← DEAN" if has_dean else ""
    
    print(f"Line {i:3d} (len={len(line):3d}, lead={leading:3d}, trail={trailing:3d}){marker}:")
    print(f"  |{line}|")
    print()

print(f"\n{'='*80}")
print("IDENTIFIED ARTIFACTS:")
print(f"{'='*80}\n")

# Identify specific artifact patterns
artifacts = []

for i, line in enumerate(lines, 1):
    # Long whitespace runs
    if '  ' * 10 in line:  # 20+ consecutive spaces
        artifacts.append(f"Line {i}: Excessive whitespace (20+ spaces)")
    
    # Fragmented names (person title without name on same line)
    titles = ['DR.', 'ENGR.', 'ARCH.', 'PROF.']
    for title in titles:
        if title in line.upper() and len(line.strip()) < 50:
            # Check if next line might be continuation
            if i < len(lines):
                artifacts.append(f"Line {i}: Possible fragmented entry ('{line.strip()[:50]}...')")
                break
    
    # "CHARPERSONS" artifact
    if 'CHARPERSON' in line.upper():
        artifacts.append(f"Line {i}: Mangled prefix 'CHARPERSONS' instead of 'CHAIRPERSONS'")
    
    # Incomplete fragments at start
    if i > 1 and line.strip() and line.strip()[0].islower():
        artifacts.append(f"Line {i}: Starts with lowercase (likely fragment): '{line.strip()[:30]}'")

for artifact in artifacts:
    print(f"  • {artifact}")

print(f"\n{'='*80}")
