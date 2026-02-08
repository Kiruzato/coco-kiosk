"""
Phase 19 Acceptance Test: Long-Form Content Reconstruction
===========================================================

Test Phase 19 enhanced expansion against acceptance criteria.
"""

import requests
import json

API_URL = "http://localhost:8000/chat"

def test_query(query, expected_min_length, expected_keywords, session_id):
    """Test query and validate response"""
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
        print(f"Answer length: {len(answer)} chars (expected ≥{expected_min_length})")
        print()
        
        # Check length
        length_ok = len(answer) >= expected_min_length
        print(f"Length check: {'✅ PASS' if length_ok else '❌ FAIL'}")
        
        # Check keywords
        found_keywords = []
        missing_keywords = []
        for keyword in expected_keywords:
            if keyword.lower() in answer.lower():
                found_keywords.append(keyword)
            else:
                missing_keywords.append(keyword)
        
        keywords_ok = len(missing_keywords) == 0
        print(f"Keywords: {len(found_keywords)}/{len(expected_keywords)} - " +
              f"{'✅ PASS' if keywords_ok else '❌ FAIL'}")
        if missing_keywords:
            print(f"  Missing: {missing_keywords}")
        
        # Show excerpt
        print()
        print("Answer excerpt (first 300 chars):")
        print(answer[:300] + ("..." if len(answer) > 300 else ""))
        
        return length_ok and keywords_ok, len(answer)
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, 0

def main():
    print("=" * 70)
    print("PHASE 19 ACCEPTANCE TEST")
    print("=" * 70)
    print()
    
    tests = [
        {
            "name": "Columban Hymn Lyrics",
            "query": "Lyrics of Columban Hymn",
            "min_length": 200,  # Full hymn should be substantial
            "keywords": ["Columban", "verse", "chorus"],
            "session_id": "phase19_hymn"
        },
        {
            "name": "Prayer to Saint Columban",
            "query": "Prayer to Saint Columban",
            "min_length": 300,  # Complete prayer
            "keywords": ["Saint Columban", "prayer", "intercession"],
            "session_id": "phase19_prayer"
        },
        {
            "name": "Dean Enumeration (Regression)",
            "query": "Who are the deans?",
            "min_length": 100,
            "keywords": ["Almazan", "Capili", "Matriano", "Yap", "Gonzales", "Gutierrez"],
            "session_id": "phase19_regression_dean"
        },
        {
            "name": "Directory Query (Regression)",
            "query": "Where is the library?",
            "min_length": 50,
            "keywords": ["library"],
            "session_id": "phase19_regression_dir"
        }
    ]
    
    results = []
    
    for test in tests:
        print("\n" + "=" * 70)
        print(f"TEST: {test['name']}")
        print("=" * 70)
        
        passed, length = test_query(
            test['query'],
            test['min_length'],
            test['keywords'],
            test['session_id']
        )
        
        results.append({
            'name': test['name'],
            'passed': passed,
            'length': length
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for result in results:
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"{status} - {result['name']} ({result['length']} chars)")
    
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    print()
    print(f"Total: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - Phase 19 complete!")
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed - review above")

if __name__ == '__main__':
    main()
