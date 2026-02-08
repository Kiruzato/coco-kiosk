"""
Find Sample Dean Chunk
=======================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Sample Dean Chunks")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Get all documents
all_docs = doc_manager.vector_store.docstore._dict

# Find chunks with specific dean names
target_deans = {
    'Matriano': None,
    'Yap': None,
    'Almazan': None,
    'Capili': None
}

for doc_id, doc in all_docs.items():
    content = doc.metadata.get('original_text', doc.page_content)
    is_synthetic = doc.metadata.get('is_synthetic', False)
    
    if is_synthetic:
        continue
    
    for dean_name in target_deans.keys():
        if dean_name in content and target_deans[dean_name] is None:
            target_deans[dean_name] = {
                'chunk_id': doc.metadata.get('chunk_id'),
                'section': doc.metadata.get('section'),
                'pages': doc.metadata.get('page_numbers', []),
                'content': content
            }

# Display
for dean_name, chunk_info in target_deans.items():
    if chunk_info:
        print(f"\n{'='*70}")
        print(f"DEAN: {dean_name}")
        print(f"{'='*70}")
        print(f"Chunk ID: {chunk_info['chunk_id']}")
        print(f"Section: {chunk_info['section']}")
        print(f"Pages: {chunk_info['pages']}")
        print(f"Content ({len(chunk_info['content'])} chars):")
        print(f"{'-'*70}")
        print(chunk_info['content'])
        print(f"{'-'*70}")

print(f"\n{'='*70}")
