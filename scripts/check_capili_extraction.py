"""
Check Raw PDF Content for Missing Dean
=======================================

Directly inspect what the layout parser extracted for Capili.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import load_pdf_document_layout_aware, group_elements_by_section

# PDF path
pdf_path = Path(__file__).parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("="*70)
print("Inspecting Layout-Aware PDF Parsing for 'Capili'")
print("="*70)

# Load with layout-aware parsing
print(f"\nParsing: {pdf_path.name}")
elements = load_pdf_document_layout_aware(pdf_path)

print(f"\nTotal elements extracted: {len(elements)}")

# Search for Capili
print(f"\n{'='*70}")
print("Searching for 'Capili' in extracted elements")
print(f"{'='*70}")

capili_elements = []
for i, elem in enumerate(elements):
    if 'capili' in elem['text'].lower():
        capili_elements.append((i, elem))
        print(f"\n[Element {i}]")
        print(f"  Type: {elem['type']}")
        print(f"  Page: {elem['metadata'].get('page_number', 'N/A')}")
        print(f"  Text: {elem['text']}")

if not capili_elements:
    print("\n❌ 'Capili' NOT FOUND in any extracted elements!")
    print("\nThis means the layout parser failed to extract this text from the PDF.")
else:
    print(f"\n✓ Found {len(capili_elements)} elements containing 'Capili'")

# Also search for Almazan for comparison
print(f"\n{'='*70}")
print("Searching for 'Almazan' in extracted elements (for comparison)")
print(f"{'='*70}")

almazan_count = 0
for i, elem in enumerate(elements):
    if 'almazan' in elem['text'].lower():
        almazan_count += 1
        if almazan_count <= 3:  # Show first 3
            print(f"\n[Element {i}]")
            print(f"  Type: {elem['type']}")
            print(f"  Page: {elem['metadata'].get('page_number', 'N/A')}")
            print(f"  Text: {elem['text'][:200]}")

print(f"\n✓ Found {almazan_count} elements containing 'Almazan'")

# Group into sections and check
print(f"\n{'='*70}")
print("Checking Section Grouping")
print(f"{'='*70}")

sections = group_elements_by_section(elements)
print(f"\nTotal sections: {len(sections)}")

# Find sections with Capili
capili_sections = []
for i, section in enumerate(sections):
    section_text = '\n'.join([e['text'] for e in section['elements']])
    if 'capili' in section_text.lower():
        capili_sections.append((i, section))

if capili_sections:
    print(f"\n✓ Found {len(capili_sections)} sections containing 'Capili'")
    for i, section in capili_sections:
        print(f"\n[Section {i}]")
        print(f"  Title: {section['section_title']}")
        print(f"  Pages: {sorted(section['page_numbers'])}")
        print(f"  Element count: {len(section['elements'])}")
        print(f"  Element types: {section['element_types']}")
else:
    print("\n❌ 'Capili' NOT FOUND in any section!")

print(f"\n{'='*70}")
print("DIAGNOSIS COMPLETE")
print(f"{'='*70}")
