"""
Search All Dean Text
=====================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Searching for Dean Text Patterns")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Get all documents
all_docs = doc_manager.vector_store.docstore._dict

# Search patterns
patterns = [
    'matriano',
    'dr. eric',
    'eric a.',
    'college of business',
    'yap',
    'noel',
    'computer studies',
    'almazan',
    'christine',
    'capili',
    'leilani',
    'nursing'
]

print(f"\nSearching {len(all_docs)} chunks...")

matches_by_pattern = {p: [] for p in patterns}

for doc_id, doc in all_docs.items():
    content = doc.metadata.get('original_text', doc.page_content)
    content_lower = content.lower()
    chunk_id = doc.metadata.get('chunk_id')
    is_synthetic = doc.metadata.get('is_synthetic', False)
    
    if is_synthetic:
        continue
    
    for pattern in patterns:
        if pattern in content_lower:
            matches_by_pattern[pattern].append({
                'chunk_id': chunk_id,
                'content_preview': content[:150]
            })

print(f"\nResults:")
for pattern, matches in sorted(matches_by_pattern.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"\n'{pattern}': {len(matches)} matches")
    if matches:
        # Show first match
        print(f"  First match (chunk {matches[0]['chunk_id']}): {matches[0]['content_preview']}...")

print(f"\n{'='*70}")
