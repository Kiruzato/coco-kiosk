"""
Debug Section Classification
=============================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import load_pdf_document_layout_aware, group_elements_by_section

# PDF path
pdf_path = Path(__file__).parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("="*70)
print("Debugging Section Classification")
print("="*70)

# Load and group
elements = load_pdf_document_layout_aware(pdf_path)
sections = group_elements_by_section(elements)

# Find all sections with "dean" in title or content
dean_sections = []

for i, section in enumerate(sections):
    title = section['section_title']
    section_text = ' '.join([elem['text'] for elem in section['elements']])
    
    if 'dean' in title.lower() or 'dean' in section_text.lower():
        dean_sections.append({
            'index': i,
            'title': title,
            'pages': sorted(section['page_numbers']),
            'element_count': len(section['elements']),
            'element_types': section['element_types'],
            'content_preview': section_text[:300]
        })

print(f"\nFound {len(dean_sections)} sections with 'dean':")

for s in dean_sections:
    print(f"\n[{s['index']}] Title: '{s['title']}'")
    print(f"    Pages: {s['pages']}")
    print(f"    Elements: {s['element_count']}")
    print(f"    Types: {s['element_types']}")
    print(f"    Content: {s['content_preview']}...")

print(f"\n{'='*70}")
