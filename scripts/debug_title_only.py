"""
Debug Title-Only Merging
=========================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import load_pdf_document_layout_aware, group_elements_by_section

# PDF path
pdf_path = Path(__file__).parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("="*70)
print("Debugging Title-Only Merging")
print("="*70)

# Load and group (WITHOUT merging)
elements = load_pdf_document_layout_aware(pdf_path)

# Manually group without calling merge
sections = []
current_section = {
    'section_title': 'Document Content',
    'elements': [],
    'element_types': set(),
    'page_numbers': set()
}

for elem in elements:
    elem_type = elem['type']
    
    if elem_type == 'Title':
        if current_section['elements']:
            sections.append(current_section)
        
        current_section = {
            'section_title': elem['text'].strip(),
            'elements': [elem],
            'element_types': {elem_type},
            'page_numbers': {elem['metadata'].get('page_number')} if elem['metadata'].get('page_number') else set()
        }
    else:
        current_section['elements'].append(elem)
        current_section['element_types'].add(elem_type)
        if elem['metadata'].get('page_number'):
            current_section['page_numbers'].add(elem['metadata'].get('page_number'))

if current_section['elements']:
    sections.append(current_section)

# Find "Deans" section and next few sections
deans_idx = None
for i, section in enumerate(sections):
    if section['section_title'].lower().strip() == 'deans':
        deans_idx = i
        break

if deans_idx is not None:
    print(f"\nFound 'Deans' section at index {deans_idx}")
    print(f"\nShowing sections {deans_idx} to {deans_idx+5}:")
    
    for i in range(deans_idx, min(deans_idx+6, len(sections))):
        s = sections[i]
        section_text = ' '.join([elem['text'] for elem in s['elements']])
        has_person_names = any(title in section_text.lower() for title in ['dr.', 'engr.', 'arch.'])
        
        print(f"\n[{i}] Title: '{s['section_title']}'")
        print(f"    Pages: {sorted(s['page_numbers'])}")
        print(f"    Elements: {len(s['elements'])}")
        print(f"    Has person names: {has_person_names}")
        print(f"    Content: {section_text[:200]}...")
else:
    print("\n'Deans' section not found!")

print(f"\n{'='*70}")
