"""
Check Top Ranking Chunks for 'dean' Query
==========================================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Top Chunks for 'dean' Query")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Search
results = doc_manager.vector_store.similarity_search_with_relevance_scores(
    "dean",
    k=10,
    score_threshold=0.0
)

print(f"\nTop 10 results:")
for i, (doc, score) in enumerate(results, 1):
    content = doc.metadata.get('original_text', doc.page_content)
    section = doc.metadata.get('section_title', 'N/A')
    
    # Check for dean names
    dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
    found = [name for name in dean_names if name.lower() in content.lower()]
    
    marker = f" >>> {found}" if found else ""
    
    print(f"\n[{i}] Score: {score:.4f}{marker}")
    print(f"    Section: {section}")
    print(f"    Content: {content[:250]}...")

print(f"\n{'='*70}")
