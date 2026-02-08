import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from campus_rag_chatbot.entity_extractors.deans import _parse_dean_line


# Test the two missing deans
lines = [
    "DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd",
    "DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director"
]

print("Testing problematic lines:\n")
for line in lines:
    print(f"Line: {line}")
    result = _parse_dean_line(line)
    if result:
        print(f"  ✓ Extracted: {result['full_name']}")
        print(f"    College: {result['college']}")
    else:
        print(f"  ✗ Failed to extract")
    print()
