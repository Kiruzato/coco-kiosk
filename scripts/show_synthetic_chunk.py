"""
Inspect Full Synthetic Chunk Content
====================================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Full Synthetic Chunk Content")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Get all documents
all_docs = doc_manager.vector_store.docstore._dict

# Find synthetic chunk
for doc_id, doc in all_docs.items():
    is_synthetic = doc.metadata.get('is_synthetic', False)
    
    if is_synthetic:
        content = doc.metadata.get('original_text', doc.page_content)
        
        print(f"\nSynthetic Chunk Found:")
        print(f"  Chunk ID: {doc.metadata.get('chunk_id')}")
        print(f"  Section: {doc.metadata.get('section')}")
        print(f"  Pages: {doc.metadata.get('page_numbers')}")
        print(f"  Source chunks: {doc.metadata.get('source_chunk_ids')}")
        print(f"  Num entities: {doc.metadata.get('num_entities')}")
        print(f"  Content length: {len(content)} chars")
        print(f"\n{'='*70}")
        print("FULL CONTENT:")
        print(f"{'='*70}")
        print(content)
        print(f"{'='*70}")
        
        # Count dean names
        dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
        found = []
        for name in dean_names:
            if name in content:
                # Find position
                pos = content.find(name)
                found.append((name, pos))
        
        found.sort(key=lambda x: x[1])
        
        print(f"\nDean names in order of appearance:")
        for name, pos in found:
            print(f"  {pos:5d}: {name}")
        
        break

print(f"\n{'='*70}")
