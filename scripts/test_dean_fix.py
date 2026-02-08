"""
Test Dean Enumeration After Fix
================================

Re-ingest and test if all 6 deans appear.
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Paths
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"
PDF_PATH = Path(__file__).parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("="*70)
print("Testing Dean Enumeration After Fix")
print("="*70)

# Step 1: Clear vector store
print("\n1. Clearing vector store...")
if VECTOR_STORE_PATH.exists():
    shutil.rmtree(VECTOR_STORE_PATH)
if REGISTRY_PATH.exists():
    REGISTRY_PATH.unlink()

# Step 2: Re-ingest with fix
print("\n2. Re-ingesting PDF with merge_related_admin_sections fix...")
manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)

success, message = manager.ingest_document(
    file_path=PDF_PATH,
    chunk_size=500,
    chunk_overlap=50,
    skip_duplicates=False
)

print(f"   {message}")

if not success:
    print("FAILED: Re-ingestion failed")
    sys.exit(1)

# Step 3: Search for all deans
print("\n3. Searching for dean chunks...")
manager.load_vector_store()

dean_names = {
    'Matriano': 'Dr. Eric A. Matriano',
    'Yap': 'Engr. Noel H. Yap',
    'Gonzales': 'Arch. Corazon Z. Gonzales',
    'Gutierrez': 'Dr. Engr. Vivian E. Gutierrez',
    'Almazan': 'Dr. Christine Gil O. Almazan',
    'Capili': 'Dr. Leilani E. Capili'
}

found_deans = {}

for short_name, full_name in dean_names.items():
    results = manager.vector_store.similarity_search_with_relevance_scores(
        short_name,
        k=10,
        score_threshold=0.0
    )
    
    for doc, score in results:
        content = doc.metadata.get('original_text', doc.page_content)
        if short_name.lower() in content.lower():
            found_deans[short_name] = {
                'full_name': full_name,
                'chunk_id': doc.metadata.get('chunk_id'),
                'section': doc.metadata.get('section_title'),
                'score': score
            }
            break

print(f"\n   Found {len(found_deans)}/6 deans:")
for short_name, info in found_deans.items():
    print(f"   ✓ {info['full_name']}")
    print(f"     Chunk: {info['chunk_id']}, Section: {info['section'][:60]}")

missing = set(dean_names.keys()) - set(found_deans.keys())
if missing:
    print(f"\n   ✗ Missing: {[dean_names[m] for m in missing]}")

# Step 4: Test query
print(f"\n4. Testing 'Who are the deans' query...")
import requests

try:
    response = requests.post(
        "http://localhost:8000/chat",
        json={"message": "Who are the deans"},
        timeout=30
    )
    data = response.json()
    
    answer = data['answer']
    print(f"\n   Answer:\n   {answer}\n")
    
    # Count deans in answer
    deans_in_answer = sum(1 for name in dean_names.values() if name in answer)
    print(f"   Deans mentioned: {deans_in_answer}/6")
    
    if deans_in_answer == 6:
        print("\n   ✓ SUCCESS: All 6 deans appear in answer!")
    else:
        print(f"\n   ✗ PARTIAL: Only {deans_in_answer}/6 deans in answer")
        
except Exception as e:
    print(f"   Error querying app: {e}")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
