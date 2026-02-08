import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from campus_rag_chatbot.entity_extractors import extract_deans_from_text

import re

text = """
Deans
DEANS
DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director
Dr. ERIC A. MATRIANO (College of Business & Accountancy)
Engr. NOEL H. YAP (College of Computer Studies)
Arch. CORAZON Z. GONZALES (College of Architecture)
Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
"""

print("Testing line filtering...")
lines = text.split('\n')
for i, line in enumerate(lines):
    line_stripped = line.strip()
    if not line_stripped:
        print(f"{i}: [empty] - SKIP")
        continue
    
    if len(line_stripped) < 10:
        print(f"{i}: '{line_stripped}' - SKIP (too short)")
        continue
    
    # Check section header filter
    is_header = line_stripped.upper() == line_stripped and len(line_stripped) < 30 and line_stripped.replace(' ', '').isalpha()
    if is_header:
        print(f"{i}: '{line_stripped}' - SKIP (section header)")
        continue
    
    # Check title pattern
    has_title = re.search(r'\b(Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+', line_stripped)
    if not has_title:
        print(f"{i}: '{line_stripped}' - SKIP (no title)")
        continue
    
    print(f"{i}: '{line_stripped}' - PROCESS")

print("\n" + "="*70)
print("Actual extraction:")
deans = extract_deans_from_text(text)
print(f"Found {len(deans)} deans")
