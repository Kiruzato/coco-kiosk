"""
Test Dean Query with Context Inspection
=======================================
"""

import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"

print("="*70)
print("Testing Dean Query with Context Inspection")
print("="*70)

# Initialize
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

# Retrieve chunks for "Who are the deans" query
print("\n[1] Retrieving chunks for 'deans' query...")
results = doc_manager.vector_store.similarity_search_with_relevance_scores(
    "deans",
    k=8,
    score_threshold=0.5
)

print(f"\nRetrieved {len(results)} chunks:")
for i, (doc, score) in enumerate(results, 1):
    content = doc.metadata.get('original_text', doc.page_content)
    section = doc.metadata.get('section', 'N/A')
    is_synthetic = doc.metadata.get('is_synthetic', False)
    
    # Count dean names
    dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
    found = [name for name in dean_names if name in content]
    
    marker = " [SYNTHETIC]" if is_synthetic else ""
    deans_marker = f" >>> {len(found)}/6 deans: {found}" if found else ""
    
    print(f"\n[{i}] Score: {score:.4f}{marker}{deans_marker}")
    print(f"    Section: {section}")
    print(f"    Content: {content[:200]}...")

# Now make the actual API call
print(f"\n{'='*70}")
print("[2] Making /chat API call...")
print(f"{'='*70}")

try:
    response = requests.post(
        "http://localhost:8000/chat",
        json={"message": "Who are the deans"},
        timeout=30
    )
    data = response.json()
    
    answer = data['answer']
    
    print(f"\nAnswer:\n{answer}")
    
    # Count deans in answer
    dean_names_check = {
        'Matriano': 'Dr. Eric A. Matriano',
        'Yap': 'Engr. Noel H. Yap',
        'Gonzales': 'Arch. Corazon Z. Gonzales',
        'Gutierrez': 'Dr. Engr. Vivian E. Gutierrez',
        'Almazan': 'Dr. Christine Gil O. Almazan',
        'Capili': 'Dr. Leilani E. Capili'
    }
    
    found_in_answer = [name for short, name in dean_names_check.items() if short in answer]
    
    print(f"\nDeans in answer: {len(found_in_answer)}/6")
    for dean in sorted(dean_names_check.values()):
        short_name = [k for k, v in dean_names_check.items() if v == dean][0]
        if short_name in answer:
            print(f"  ✓ {dean}")
        else:
            print(f"  ✗ {dean}")
    
except Exception as e:
    print(f"ERROR: {e}")

print(f"\n{'='*70}")
