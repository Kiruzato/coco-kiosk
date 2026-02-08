"""
Phase 19 Initial Testing: Long-Form Content Reconstruction
===========================================================

Test if current _expand_with_adjacent_chunks (Phase 17C) already handles
long-form content correctly, or if enhancements are needed.
"""

import requests
import json

API_URL = "http://localhost:8000/chat"

def test_query(query, expected_keywords, session_id):
    """Test a query and check for expected keywords in response"""
    print(f"\nQuery: \"{query}\"")
    print("-" * 70)
    
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
        sources = len(data.get('sources', []))
        
        print(f"Confidence: {confidence}")
        print(f"Sources: {sources}")
        print(f"Answer length: {len(answer)} chars")
        print()
        print("Answer excerpt:")
        print(answer[:500] + ("..." if len(answer) > 500 else ""))
        print()
        
        # Check for expected keywords
        found = []
        missing = []
        for keyword in expected_keywords:
            if keyword.lower() in answer.lower():
                found.append(keyword)
            else:
                missing.append(keyword)
        
        print(f"Keywords found: {len(found)}/{len(expected_keywords)}")
        if missing:
            print(f"Missing: {missing}")
        
        return len(missing) == 0, answer
    
    except Exception as e:
        print(f"ERROR: {e}")
        return False, ""

def main():
    print("="*70)
    print("PHASE 19 INITIAL TESTING: Long-Form Content")
    print("="*70)
    
    tests = [
        {
            "name": "Columban Hymn Lyrics",
            "query": "Lyrics of Columban Hymn",
            "keywords": ["Columban", "hymn", "verse", "chorus", "alma mater"],
            "session_id": "test_phase19_hymn"
        },
        {
            "name": "Prayer to Saint Columban",
            "query": "Prayer to Saint Columban",
            "keywords": ["Saint Columban", "prayer", "patron", "intercession"],
            "session_id": "test_phase19_prayer"
        },
        {
            "name": "School Philosophy",
            "query": "What is the school philosophy?",
            "keywords": ["philosophy", "education", "values"],
            "session_id": "test_phase19_philosophy"
        }
    ]
    
    results = []
    
    for test in tests:
        print(f"\n{'='*70}")
        print(f"TEST: {test['name']}")
        print('='*70)
        
        passed, answer = test_query(test['query'], test['keywords'], test['session_id'])
        results.append({
            'name': test['name'],
            'passed': passed,
            'answer_length': len(answer)
        })
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for result in results:
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"{status} - {result['name']} ({result['answer_length']} chars)")
    
    total_passed = sum(1 for r in results if r['passed'])
    print(f"\nTotal: {total_passed}/{len(results)} passed")
    
    if total_passed == len(results):
        print("\n✅ Current implementation handles long-form content!")
        print("Phase 17C expansion may be sufficient.")
    else:
        print("\n❌ Current implementation incomplete for long-form content")
        print("Phase 19 enhancements needed.")

if __name__ == '__main__':
    main()
