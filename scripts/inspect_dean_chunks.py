"""
Inspect Dean Chunk Content
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
print("Inspecting All Dean-Related Chunks")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Get all documents from vector store
all_docs = doc_manager.vector_store.docstore._dict

print(f"\nTotal chunks in vector store: {len(all_docs)}")

# Find chunks with dean information
dean_chunks = []

for doc_id, doc in all_docs.items():
    content = doc.metadata.get('original_text', doc.page_content)
    
    if 'dean' in content.lower():
        # Check if it's synthetic
        is_synthetic = doc.metadata.get('is_synthetic', False)
        chunk_id = doc.metadata.get('chunk_id', 'N/A')
        
        dean_chunks.append({
            'doc_id': doc_id,
            'chunk_id': chunk_id,
            'is_synthetic': is_synthetic,
            'section': doc.metadata.get('section', 'N/A'),
            'pages': doc.metadata.get('page_numbers', []),
            'content': content
        })

print(f"\nFound {len(dean_chunks)} chunks with 'dean':")

# Separate synthetic and regular chunks
synthetic_chunks = [c for c in dean_chunks if c['is_synthetic']]
regular_chunks = [c for c in dean_chunks if not c['is_synthetic']]

print(f"\n  Synthetic chunks: {len(synthetic_chunks)}")
print(f"  Regular chunks: {len(regular_chunks)}")

# Show synthetic chunks
if synthetic_chunks:
    print(f"\n{'='*70}")
    print("SYNTHETIC CHUNKS:")
    print(f"{'='*70}")
    
    for i, chunk in enumerate(synthetic_chunks, 1):
        print(f"\n[{i}] Chunk ID: {chunk['chunk_id']}")
        print(f"    Section: {chunk['section']}")
        print(f"    Pages: {chunk['pages']}")
        print(f"    Content length: {len(chunk['content'])} chars")
        print(f"    Full content:")
        print(f"    {'-'*66}")
        print(f"    {chunk['content']}")
        print(f"    {'-'*66}")
        
        # Count dean names
        dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
        found = [name for name in dean_names if name in chunk['content']]
        print(f"    Contains {len(found)}/6 deans: {found}")
        
        # Show source chunk IDs if available
        source_ids = chunk.get('source_chunk_ids', [])
        if 'source_chunk_ids' in chunk:
            print(f"    Source chunk IDs: N/A in this dict")

# Show a few regular chunks
if regular_chunks:
    print(f"\n{'='*70}")
    print("SAMPLE REGULAR CHUNKS (first 3):")
    print(f"{'='*70}")
    
    for i, chunk in enumerate(regular_chunks[:3], 1):
        print(f"\n[{i}] Chunk ID: {chunk['chunk_id']}")
        print(f"    Section: {chunk['section']}")
        print(f"    Pages: {chunk['pages']}")
        print(f"    Content preview: {chunk['content'][:200]}...")

print(f"\n{'='*70}")
