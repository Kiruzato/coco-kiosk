"""
Diagnostic Script for Phase 18 Retrieval Regression
====================================================

Investigates missing deans (Almazan, Capili) in query results.
"""

import sys
import json
import requests
from pathlib import Path

# Add campus_rag_chatbot to path
sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager
from retrieval_validator import extract_query_terms, compute_keyword_scores, combine_hybrid_scores
from text_normalizer import normalize_text

# Configuration
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"
APP_URL = "http://localhost:8000"

def test_query_via_api(query: str):
    """Test query via API endpoint"""
    print(f"\n{'='*70}")
    print(f"API Query: '{query}'")
    print(f"{'='*70}")
    
    try:
        response = requests.post(f"{APP_URL}/chat", json={"message": query}, timeout=30)
        data = response.json()
        
        print(f"\nAnswer: {data['answer']}")
        print(f"\nConfidence: {data['confidence_level']}")
        print(f"Rejected: {data['rejected']}")
        print(f"Sources: {len(data['sources'])}")
        
        print(f"\nSource details:")
        for s in data['sources']:
            print(f"  - {s['document_name']} section='{s['section']}' chunk={s['chunk_id']}")
        
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def search_chunks_containing(doc_manager, term: str, k: int = 20):
    """Search for chunks containing a specific term"""
    print(f"\n{'='*70}")
    print(f"Searching chunks containing: '{term}'")
    print(f"{'='*70}")
    
    normalized_term = normalize_text(term)
    results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        normalized_term,
        k=k,
        score_threshold=0.0  # No threshold to see all results
    )
    
    print(f"\nFound {len(results)} chunks")
    
    for i, (doc, score) in enumerate(results, 1):
        metadata = doc.metadata
        content = metadata.get('original_text', doc.page_content)
        
        # Check if term actually appears in content
        if term.lower() in content.lower():
            print(f"\n[{i}] Score: {score:.4f}")
            print(f"    Section: {metadata.get('section_title', metadata.get('section', 'N/A'))}")
            print(f"    Element types: {metadata.get('element_types', 'N/A')}")
            print(f"    Pages: {metadata.get('page_numbers', 'N/A')}")
            print(f"    Chunk ID: {metadata.get('chunk_id')}")
            print(f"    Content preview: {content[:200]}...")
    
    return results


def analyze_retrieval_for_query(doc_manager, query: str, k: int = 8):
    """Analyze retrieval pipeline for a specific query"""
    print(f"\n{'='*70}")
    print(f"Retrieval Analysis: '{query}'")
    print(f"{'='*70}")
    
    normalized_query = normalize_text(query)
    
    # Vector retrieval
    print(f"\n1. Vector Retrieval (k={k})")
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        normalized_query,
        k=k,
        score_threshold=0.5
    )
    
    print(f"   Retrieved {len(retrieval_results)} chunks")
    for i, (doc, score) in enumerate(retrieval_results, 1):
        metadata = doc.metadata
        print(f"   [{i}] Score: {score:.4f} | Section: {metadata.get('section_title', 'N/A')[:50]}")
    
    # Keyword scoring
    print(f"\n2. Keyword Extraction")
    query_terms = extract_query_terms(query)
    print(f"   Query terms: {query_terms}")
    
    # Hybrid scoring
    print(f"\n3. Hybrid Scoring")
    retrieved_docs = [doc for doc, score in retrieval_results]
    keyword_scores = compute_keyword_scores(query_terms, retrieved_docs)
    
    hybrid_results, hybrid_details = combine_hybrid_scores(
        retrieval_results,
        keyword_scores,
        vector_weight=0.7,
        keyword_weight=0.3
    )
    
    print(f"\n   Hybrid Results:")
    for i, (doc, hybrid_score) in enumerate(hybrid_results, 1):
        metadata = doc.metadata
        detail = hybrid_details[i-1]
        content = metadata.get('original_text', doc.page_content)
        
        print(f"\n   [{i}] Hybrid: {hybrid_score:.4f} (vector={detail['vector_score']:.4f}, keyword={detail['keyword_score']:.4f})")
        print(f"       Section: {metadata.get('section_title', 'N/A')}")
        print(f"       Pages: {metadata.get('page_numbers', 'N/A')}")
        print(f"       Preview: {content[:150]}...")
        
        # Check for dean names
        dean_names = ['Matriano', 'Yap', 'Gonzales', 'Gutierrez', 'Almazan', 'Capili']
        found_deans = [name for name in dean_names if name.lower() in content.lower()]
        if found_deans:
            print(f"       >>> Contains deans: {found_deans}")
    
    return hybrid_results


def check_all_dean_chunks(doc_manager):
    """Find all chunks mentioning any dean"""
    print(f"\n{'='*70}")
    print(f"Finding ALL chunks with dean names")
    print(f"{'='*70}")
    
    dean_names = {
        'Matriano': 'Dr. Eric A. Matriano',
        'Yap': 'Engr. Noel H. Yap',
        'Gonzales': 'Arch. Corazon Z. Gonzales',
        'Gutierrez': 'Dr. Engr. Vivian E. Gutierrez',
        'Almazan': 'Dr. Christine Gil O. Almazan',
        'Capili': 'Dr. Leilani E. Capili'
    }
    
    for short_name, full_name in dean_names.items():
        print(f"\n--- Searching for: {full_name} ---")
        
        # Search by last name
        results = doc_manager.vector_store.similarity_search_with_relevance_scores(
            short_name,
            k=10,
            score_threshold=0.0
        )
        
        found = False
        for doc, score in results:
            content = doc.metadata.get('original_text', doc.page_content)
            if short_name.lower() in content.lower():
                found = True
                metadata = doc.metadata
                print(f"  ✓ Found in chunk {metadata.get('chunk_id')}")
                print(f"    Section: {metadata.get('section_title', 'N/A')}")
                print(f"    Pages: {metadata.get('page_numbers', 'N/A')}")
                print(f"    Element types: {metadata.get('element_types', 'N/A')}")
                print(f"    Score: {score:.4f}")
                print(f"    Content: {content[:200]}...")
                break
        
        if not found:
            print(f"  ✗ NOT FOUND in vector store!")


def main():
    """Main diagnostic routine"""
    print("="*70)
    print("Phase 18 Retrieval Regression Diagnostic")
    print("="*70)
    
    # Initialize document manager
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    doc_manager.load_vector_store()
    
    if not doc_manager.vector_store:
        print("ERROR: Vector store not loaded")
        return
    
    print(f"\nVector store loaded successfully")
    
    # Step 1: Test via API
    print("\n" + "="*70)
    print("STEP 1: Test Query via API")
    print("="*70)
    api_result = test_query_via_api("Who are the deans")
    
    # Step 2: Check if all deans exist in vector store
    print("\n" + "="*70)
    print("STEP 2: Verify All Deans in Vector Store")
    print("="*70)
    check_all_dean_chunks(doc_manager)
    
    # Step 3: Analyze retrieval pipeline
    print("\n" + "="*70)
    print("STEP 3: Analyze Retrieval Pipeline")
    print("="*70)
    analyze_retrieval_for_query(doc_manager, "Who are the deans", k=8)
    
    # Step 4: Search for specific missing deans
    print("\n" + "="*70)
    print("STEP 4: Deep Search for Missing Deans")
    print("="*70)
    search_chunks_containing(doc_manager, "Almazan", k=15)
    search_chunks_containing(doc_manager, "Capili", k=15)
    
    # Step 5: Search for "dean" keyword
    print("\n" + "="*70)
    print("STEP 5: All Chunks Containing 'dean'")
    print("="*70)
    search_chunks_containing(doc_manager, "dean", k=20)
    
    print("\n" + "="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
