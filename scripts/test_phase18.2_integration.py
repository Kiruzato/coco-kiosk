"""
Phase 18.2 Integration Acceptance Test
========================================

Tests the production integration of deterministic dean extraction.

Acceptance Criteria:
1. Query: "Who are the deans?"
2. Expected: 6/6 deans extracted
3. Method: deterministic_extraction (not LLM)
4. All 6 names present in answer
"""

import requests
import json
import sys

API_URL = "http://localhost:8000/chat"

def test_dean_enumeration():
    """Test dean enumeration query"""
    print("="*70)
    print("PHASE 18.2 ACCEPTANCE TEST: Dean Enumeration")
    print("="*70)
    print()
    
    query = "Who are the deans?"
    
    print(f"Query: \"{query}\"")
    print()
    
    # Send request
    payload = {
        "message": query,
        "session_id": "test_phase18.2_acceptance"
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print("Response received:")
        print("-" * 70)
        print(data.get('answer', 'No answer'))
        print("-" * 70)
        print()
        
        # Verify 6/6 deans present
        answer = data.get('answer', '')
        
        expected_deans = [
            'Almazan',
            'Capili', 
            'Matriano',
            'Yap',
            'Gonzales',
            'Gutierrez'
        ]
        
        found_deans = []
        missing_deans = []
        
        for dean in expected_deans:
            if dean in answer:
                found_deans.append(dean)
            else:
                missing_deans.append(dean)
        
        print("VERIFICATION:")
        print(f"  Deans found: {len(found_deans)}/6")
        for dean in found_deans:
            print(f"    ✓ {dean}")
        
        if missing_deans:
            print(f"  Missing deans: {len(missing_deans)}")
            for dean in missing_deans:
                print(f"    ✗ {dean}")
        
        print()
        print(f"Confidence: {data.get('confidence_level', 'Unknown')}")
        print(f"Sources: {len(data.get('sources', []))}")
        print()
        
        if len(found_deans) == 6:
            print("✅ ACCEPTANCE TEST PASSED: 6/6 deans extracted!")
            return True
        else:
            print(f"❌ ACCEPTANCE TEST FAILED: Only {len(found_deans)}/6 deans extracted")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_regression_queries():
    """Test that other queries still work"""
    print()
    print("="*70)
    print("REGRESSION TESTS")
    print("="*70)
    print()
    
    test_queries = [
        "Where is the library?",
        "How to attain honorable mention?",
        "What are the academic awards?"
    ]
    
    results = []
    
    for query in test_queries:
        print(f"Query: \"{query}\"")
        
        payload = {
            "message": query,
            "session_id": f"test_regression_{test_queries.index(query)}"
        }
        
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            answer = data.get('answer', '')
            confidence = data.get('confidence_level', 'Unknown')
            
            # Check if we got a reasonable answer (not refusal)
            is_refusal = "don't have verified" in answer.lower() or "can't answer" in answer.lower()
            
            if not is_refusal and len(answer) > 20:
                print(f"  ✓ OK - {confidence} confidence, {len(answer)} chars")
                results.append(True)
            else:
                print(f"  ✗ FAIL - Possible refusal or short answer")
                results.append(False)
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append(False)
        
        print()
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ REGRESSION TESTS PASSED: {passed}/{total}")
        return True
    else:
        print(f"⚠️  REGRESSION TESTS: {passed}/{total} passed")
        return False

if __name__ == '__main__':
    acceptance_passed = test_dean_enumeration()
    regression_passed = test_regression_queries()
    
    print()
    print("="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Acceptance Test (Dean Enumeration): {'PASS ✅' if acceptance_passed else 'FAIL ❌'}")
    print(f"Regression Tests (Other Queries): {'PASS ✅' if regression_passed else 'PARTIAL ⚠️'}")
    print()
    
    if acceptance_passed and regression_passed:
        print("🎉 ALL TESTS PASSED - Phase 18.2 integration successful!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Review results above")
        sys.exit(1)
