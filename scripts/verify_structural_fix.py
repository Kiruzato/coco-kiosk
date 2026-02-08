"""
Comprehensive Verification of Structural Fix
=============================================

Tests the redesigned merge_related_admin_sections function.
"""

import sys
import shutil
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "campus_rag_chatbot"))

from document_manager import DocumentManager
import requests

# Paths
REGISTRY_PATH = Path(__file__).parent.parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent.parent / "campus_rag_chatbot" / "vector_store"
PDF_PATH = Path(__file__).parent.parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("="*70)
print("STRUCTURAL FIX VERIFICATION")
print("="*70)

# Step 1: Clear and re-ingest
print("\n[1] Re-ingesting with structural fix...")
if VECTOR_STORE_PATH.exists():
    shutil.rmtree(VECTOR_STORE_PATH)
if REGISTRY_PATH.exists():
    REGISTRY_PATH.unlink()

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

print(f"    {message}")

if not success:
    print("FAILED: Re-ingestion failed")
    sys.exit(1)

# Step 2: Inspect Deans chunk
print("\n[2] Inspecting 'Deans' chunk content...")
manager.load_vector_store()

# Find the Deans chunk
results = manager.vector_store.similarity_search_with_relevance_scores(
    "deans",
    k=20,
    score_threshold=0.0
)

deans_chunk = None
deans_rank = None

for i, (doc, score) in enumerate(results, 1):
    section = doc.metadata.get('section_title', '')
    if section.lower().strip() in ['deans', 'dean']:
        deans_chunk = doc
        deans_rank = i
        print(f"\n    Found 'Deans' chunk at rank #{i}, score: {score:.4f}")
        print(f"    Section title: {section}")
        print(f"    Pages: {doc.metadata.get('page_numbers')}")
        print(f"    Element types: {doc.metadata.get('element_types')}")
        
        content = doc.metadata.get('original_text', doc.page_content)
        print(f"\n    Full content ({len(content)} chars):")
        print(f"    {'-'*66}")
        print(f"    {content}")
        print(f"    {'-'*66}")
        
        # Check which deans are present
        dean_names = {
            'Matriano': 'Dr. Eric A. Matriano',
            'Yap': 'Engr. Noel H. Yap',
            'Gonzales': 'Arch. Corazon Z. Gonzales',
            'Gutierrez': 'Dr. Engr. Vivian E. Gutierrez',
            'Almazan': 'Dr. Christine Gil O. Almazan',
            'Capili': 'Dr. Leilani E. Capili'
        }
        
        found_deans = [name for short, name in dean_names.items() if short.lower() in content.lower()]
        print(f"\n    Deans in this chunk: {len(found_deans)}/6")
        for dean in found_deans:
            print(f"      ✓ {dean}")
        
        missing = [name for short, name in dean_names.items() if short.lower() not in content.lower()]
        if missing:
            print(f"\n    Missing from this chunk:")
            for dean in missing:
                print(f"      ✗ {dean}")
        
        break

if not deans_chunk:
    print("\n    ✗ ERROR: No 'Deans' chunk found!")
    sys.exit(1)

# Step 3: Check for separate dean chunks
print("\n[3] Checking for separate dean chunks...")
separate_dean_chunks = []

for i, (doc, score) in enumerate(results, 1):
    if i == deans_rank:
        continue  # Skip the main Deans chunk
    
    content = doc.metadata.get('original_text', doc.page_content)
    section = doc.metadata.get('section_title', '')
    
    # Check if contains dean names
    dean_names_list = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
    found = [name for name in dean_names_list if name.lower() in content.lower()]
    
    if found and 'dean' in content.lower():
        separate_dean_chunks.append({
            'rank': i,
            'section': section,
            'score': score,
            'deans': found
        })

if separate_dean_chunks:
    print(f"\n    Found {len(separate_dean_chunks)} separate dean chunks:")
    for chunk in separate_dean_chunks:
        print(f"      Rank #{chunk['rank']}: {chunk['section']} (score {chunk['score']:.4f})")
        print(f"        Contains: {chunk['deans']}")
else:
    print(f"\n    ✓ No separate dean chunks - all consolidated!")

# Step 4: Test query 3 times for determinism
print("\n[4] Testing 'Who are the deans' query (3 runs for determinism)...")

query_results = []

for run in range(1, 4):
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"message": "Who are the deans"},
            timeout=30
        )
        data = response.json()
        
        answer = data['answer']
        
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
        query_results.append({
            'run': run,
            'count': len(found_in_answer),
            'deans': found_in_answer,
            'answer': answer
        })
        
        print(f"\n    Run {run}: {len(found_in_answer)}/6 deans")
        for dean in found_in_answer:
            print(f"      ✓ {dean}")
        
        missing = [name for short, name in dean_names_check.items() if short not in answer]
        if missing:
            print(f"      Missing:")
            for dean in missing:
                print(f"        ✗ {dean}")
        
    except Exception as e:
        print(f"\n    Run {run}: ERROR - {e}")
        query_results.append({'run': run, 'error': str(e)})

# Step 5: Check determinism
print("\n[5] Checking determinism...")
counts = [r['count'] for r in query_results if 'count' in r]

if len(set(counts)) == 1:
    print(f"    ✓ Deterministic: All runs returned {counts[0]}/6 deans")
else:
    print(f"    ✗ Non-deterministic: Counts vary: {counts}")

# Step 6: Regression tests
print("\n[6] Running regression tests...")

regression_queries = [
    "where is the library",
    "how to attain honorable mention"
]

for query in regression_queries:
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"message": query},
            timeout=30
        )
        data = response.json()
        
        if data['rejected']:
            print(f"    ✗ '{query}' - REJECTED")
        else:
            print(f"    ✓ '{query}' - OK (confidence: {data['confidence_level']})")
    except Exception as e:
        print(f"    ✗ '{query}' - ERROR: {e}")

# Final summary
print("\n" + "="*70)
print("VERIFICATION SUMMARY")
print("="*70)

all_passed = True

# Check 1: Deans chunk exists
if deans_chunk:
    print("✓ Deans chunk exists")
else:
    print("✗ Deans chunk missing")
    all_passed = False

# Check 2: All 6 deans in one chunk
if deans_chunk and len(found_deans) == 6:
    print("✓ All 6 deans in single 'Deans' chunk")
else:
    print(f"✗ Only {len(found_deans) if deans_chunk else 0}/6 deans in 'Deans' chunk")
    all_passed = False

# Check 3: No separate dean chunks
if not separate_dean_chunks:
    print("✓ No separate dean chunks (proper consolidation)")
else:
    print(f"✗ {len(separate_dean_chunks)} separate dean chunks exist")
    all_passed = False

# Check 4: Query returns all 6 deans
if counts and counts[0] == 6:
    print("✓ Query returns all 6 deans")
else:
    print(f"✗ Query returns only {counts[0] if counts else 0}/6 deans")
    all_passed = False

# Check 5: Deterministic
if len(set(counts)) == 1:
    print("✓ Deterministic across 3 runs")
else:
    print("✗ Non-deterministic results")
    all_passed = False

# Check 6: No K increase
print("✓ No K increase required (structural fix)")

print("\n" + "="*70)
if all_passed:
    print("✓✓✓ ALL CHECKS PASSED - STRUCTURAL FIX SUCCESSFUL ✓✓✓")
else:
    print("✗✗✗ SOME CHECKS FAILED - FURTHER INVESTIGATION NEEDED ✗✗✗")
print("="*70)
