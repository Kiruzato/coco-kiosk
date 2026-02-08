"""
Find Chunks With All Deans
===========================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration 
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Finding Chunks With Multiple Deans")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Get all documents from vector store
all_docs = doc_manager.vector_store.docstore._dict

dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']

# Find chunks with multiple deans
multi_dean_chunks = []

for doc_id, doc in all_docs.items():
    content = doc.metadata.get('original_text', doc.page_content)
    
    # Count how many deans are in this chunk
    found_deans = [name for name in dean_names if name in content]
    
    if len(found_deans) >= 2:
        multi_dean_chunks.append({
            'chunk_id': doc.metadata.get('chunk_id', 'N/A'),
            'is_synthetic': doc.metadata.get('is_synthetic', False),
            'section': doc.metadata.get('section', 'N/A'),
            'pages': doc.metadata.get('page_numbers', []),
            'content': content,
            'found_deans': found_deans,
            'count': len(found_deans)
        })

# Sort by count descending
multi_dean_chunks.sort(key=lambda x: x['count'], reverse=True)

print(f"\nFound {len(multi_dean_chunks)} chunks with 2+ deans:")

for i, chunk in enumerate(multi_dean_chunks[:5], 1):
    print(f"\n[{i}] Chunk ID: {chunk['chunk_id']} (Synthetic: {chunk['is_synthetic']})")
    print(f"    Section: {chunk['section']}")
    print(f"    Pages: {chunk['pages']}")
    print(f"    Deans: {chunk['count']}/6 - {chunk['found_deans']}")
    print(f"    Content ({len(chunk['content'])} chars):")
    print(f"    {'-'*66}")
    print(f"    {chunk['content'][:500]}...")
    print(f"    {'-'*66}")

print(f"\n{'='*70}")
