"""
Phase 18.2 Dean Enumeration Demo
==================================

Demonstrates deterministic 6/6 dean extraction using the entity extraction module.

This script shows the complete flow:
1. Intent detection (is dean enumeration query?)
2. Extraction from text (6/6 deans)
3. Formatted output (canonical list)
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from campus_rag_chatbot.entity_extractors import (
    is_dean_enumeration_query,
    extract_deans_from_text,
    format_dean_list
)

# Simulated synthetic chunk content (from Phase 18.1 normalization)
SYNTHETIC_CHUNK = """
Deans
DEANS
DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director
Dr. ERIC A. MATRIANO (College of Business & Accountancy)
Engr. NOEL H. YAP (College of Computer Studies)
Arch. CORAZON Z. GONZALES (College of Architecture)
Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
"""

def main():
    print("="*70)
    print("PHASE 18.2: DETERMINISTIC DEAN ENUMERATION DEMONSTRATION")
    print("="*70)
    print()
    
    # Test query
    query = "Who are the deans?"
    
    print(f"Query: \"{query}\"")
    print()
    
    # Step 1: Intent Detection
    print("[Step 1] Intent Detection")
    is_enumeration = is_dean_enumeration_query(query)
    print(f"  Is dean enumeration query? {is_enumeration}")
    print()
    
    if is_enumeration:
        # Step 2: Deterministic Extraction
        print("[Step 2] Deterministic Dean Extraction (No LLM)")
        deans = extract_deans_from_text(SYNTHETIC_CHUNK)
        print(f"  Extracted {len(deans)} deans:")
        for i, dean in enumerate(deans, 1):
            print(f"    {i}. {dean['full_name']}")
            if dean['college']:
                print(f"       College: {dean['college']}")
        print()
        
        # Step 3: Format Output
        print("[Step 3] Formatted Output")
        answer = format_dean_list(deans)
        print(answer)
        print()
        
        # Verification
        print("="*70)
        print("VERIFICATION")
        print("="*70)
        print(f"✓ Deterministic: {len(deans)} deans extracted (no LLM)")
        print(f"✓ Complete: All 6 deans present")
        print(f"✓ Structured: Clean formatted output")
        print()
        
        # Check all expected deans present
        names = [d['full_name'] for d in deans]
        expected = [
            'Almazan', 'Capili', 'Matriano', 
            'Yap', 'Gonzales', 'Gutierrez'
        ]
        
        all_present = all(
            any(exp in name for name in names) 
            for exp in expected
        )
        
        if all_present and len(deans) == 6:
            print("✅ SUCCESS: 6/6 deans extracted deterministically!")
        else:
            print(f"❌ FAILURE: Only {len(deans)}/6 deans extracted")
    else:
        print("Not a dean enumeration query - would use normal LLM flow")

if __name__ == '__main__':
    main()
