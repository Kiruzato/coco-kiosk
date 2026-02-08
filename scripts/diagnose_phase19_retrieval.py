"""
Phase 19 Diagnosis: Retrieval Testing via API
==============================================

Test hymn and prayer queries with detailed output to diagnose retrieval.
"""

import requests
import json

API_URL = "http://localhost:8000/chat"

def test_with_details(query, session_id):
    """Test query and show detailed response"""
    print(f"\nQuery: \"{query}\"")
    print("=" * 70)
    
    payload = {
        "message": query,
        "session_id": session_id
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        answer = data.get('answer', '')
        confidence = data.get('confidence_level', 'Unknown')
        sources = data.get('sources', [])
        
        print(f"Confidence: {confidence}")
        print(f"Sources: {len(sources)}")
        print(f"Answer length: {len(answer)} chars")
        print()
        
        # Show sources detail
        if sources:
            print("Source chunks:")
            for i, source in enumerate(sources, 1):
                doc = source.get('document_name', 'Unknown')
                section = source.get('section', 'Unknown')
                chunk_id = source.get('chunk_id', '?')
                print(f"  {i}. Chunk {chunk_id} - {doc} / {section}")
        else:
            print("No sources returned")
        
        print()
        print("Answer:")
        print("-" * 70)
        print(answer)
        print("-" * 70)
        
        return data
        
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def main():
    print("=" * 70)
    print("PHASE 19 DIAGNOSIS: API Retrieval Testing")
    print("=" * 70)
    print()
    print("Testing long-form content queries to diagnose retrieval behavior")
    print()
    
    # Test 1: Hymn
    print("\n" + "=" * 70)
    print("TEST 1: Columban Hymn")
    print("=" * 70)
    test_with_details("Lyrics of Columban Hymn", "diag_hymn")
    
    # Test 2: Different phrasing
    print("\n" + "=" * 70)
    print("TEST 2: Hymn (alternate query)")
    print("=" * 70)
    test_with_details("What is the Columban College hymn?", "diag_hymn2")
    
    # Test 3: Prayer
    print("\n" + "=" * 70)
    print("TEST 3: Prayer to Saint Columban")
    print("=" * 70)
    test_with_details("Prayer to Saint Columban", "diag_prayer")
    
    # Test 4: Partial prayer query
    print("\n" + "=" * 70)
    print("TEST 4: Prayer (partial query)")
    print("=" * 70)
    test_with_details("Show me the prayer for Saint Columban", "diag_prayer2")
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS INSTRUCTIONS")
    print("=" * 70)
    print("""
Check the server logs for:
1. [PHASE17A] query terms extracted
2. [PHASE17C] chunks retrieved and hybrid scores
3. [PHASE17C] Expanded N chunks with ±1 neighbors
4. Grounding validation results

This will show:
- If content is being retrieved
- At what rank
- If expansion is occurring
- If grounding is failing
""")

if __name__ == '__main__':
    main()
