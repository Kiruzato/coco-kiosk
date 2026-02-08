import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from campus_rag_chatbot.entity_extractors import extract_deans_from_text


text = """
DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director
Dr. ERIC A. MATRIANO (College of Business & Accountancy)
Engr. NOEL H. YAP (College of Computer Studies)
Arch. CORAZON Z. GONZALES (College of Architecture)
Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
"""

print("Testing dean extraction...\n")
deans = extract_deans_from_text(text)

print(f"Found {len(deans)} deans:\n")
for i, dean in enumerate(deans, 1):
    print(f"{i}. {dean['full_name']}")
    print(f"   Title: {dean['title']}")
    print(f"   College: {dean['college']}")
    print(f"   Raw: {dean['raw_line']}\n")
