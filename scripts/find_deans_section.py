"""
Find the Main Deans Section
============================

Check what happened to the primary "Deans" section.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Finding Main Deans Section")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Search for chunks with "Deans" as section title
print("\nSearching for all chunks...")
results = doc_manager.vector_store.similarity_search_with_relevance_scores(
    "deans",
    k=50,
    score_threshold=0.0
)

print(f"\nTotal results: {len(results)}")

# Find chunks with "Deans" in section title
deans_sections = []
for i, (doc, score) in enumerate(results):
    section_title = doc.metadata.get('section_title', '')
    if 'dean' in section_title.lower():
        deans_sections.append((i+1, doc, score))

print(f"\nChunks with 'dean' in section title: {len(deans_sections)}")

for rank, doc, score in deans_sections[:10]:
    print(f"\n[Rank {rank}] Score: {score:.4f}")
    print(f"    Section: {doc.metadata.get('section_title')}")
    print(f"    Chunk ID: {doc.metadata.get('chunk_id')}")
    print(f"    Pages: {doc.metadata.get('page_numbers')}")
    content = doc.metadata.get('original_text', doc.page_content)
    print(f"    Content preview: {content[:300]}...")
    
    # Check which deans are in this chunk
    dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
    found = [name for name in dean_names if name.lower() in content.lower()]
    if found:
        print(f"    >>> Contains: {found}")

print(f"\n{'='*70}")
print("DONE")
print(f"{'='*70}")
