"""
Verify Capili Chunks in Vector Store
=====================================

Check if Capili chunks exist and why they score poorly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager
from text_normalizer import normalize_text

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Verifying Capili Chunks in Vector Store")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Search for Capili with NO score threshold
print("\nSearching for 'Capili' (no threshold)...")
results = doc_manager.vector_store.similarity_search_with_relevance_scores(
    "Capili",
    k=50,
    score_threshold=0.0  # Get ALL results
)

print(f"\nTotal results: {len(results)}")

capili_chunks = []
for i, (doc, score) in enumerate(results):
    content = doc.metadata.get('original_text', doc.page_content)
    if 'capili' in content.lower():
        capili_chunks.append((doc, score))
        print(f"\n[{i+1}] FOUND Capili chunk!")
        print(f"    Score: {score:.4f}")
        print(f"    Chunk ID: {doc.metadata.get('chunk_id')}")
        print(f"    Section title: {doc.metadata.get('section_title', 'N/A')}")
        print(f"    Section (legacy): {doc.metadata.get('section', 'N/A')}")
        print(f"    Pages: {doc.metadata.get('page_numbers', 'N/A')}")
        print(f"    Element types: {doc.metadata.get('element_types', 'N/A')}")
        print(f"    Content: {content}")

if not capili_chunks:
    print("\n❌ NO chunks containing 'Capili' found in vector store!")
else:
    print(f"\n✓ Found {len(capili_chunks)} chunks containing 'Capili'")

# Now search for "dean" to see what scores those chunks get
print(f"\n{'='*70}")
print("Searching for 'dean' to see Capili chunk scores")
print(f"{'='*70}")

dean_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
    "dean",
    k=20,
    score_threshold=0.0
)

print(f"\nTop 20 results for 'dean' query:")
for i, (doc, score) in enumerate(dean_results, 1):
    content = doc.metadata.get('original_text', doc.page_content)
    has_capili = 'capili' in content.lower()
    marker = " >>> CAPILI <<<" if has_capili else ""
    print(f"[{i}] Score: {score:.4f} | Section: {doc.metadata.get('section_title', 'N/A')[:50]}{marker}")
    if has_capili:
        print(f"    Content: {content[:200]}...")

print(f"\n{'='*70}")
print("ANALYSIS COMPLETE")
print(f"{'='*70}")
