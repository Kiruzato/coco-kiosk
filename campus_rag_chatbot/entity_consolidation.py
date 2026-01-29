"""
Entity-Centric Chunk Consolidation for Enumeration Roles
=========================================================

This module provides post-chunking consolidation for scattered entity information.
Specifically designed for enumeration queries like "Who are the deans".
"""

import re
from typing import List, Dict, Set
from langchain_core.documents import Document
from text_normalizer import normalize_text

def consolidate_dean_chunks(documents: List[Document]) -> List[Document]:
    """
    Consolidate scattered dean information into ONE synthetic chunk.
    
    Phase 18 Entity Consolidation: Addresses PDF structures where dean information
    is scattered across multiple sections/pages. Creates a single authoritative
    "Deans" chunk containing all dean entities for deterministic enumeration.
    
    Design:
    - Semantic detection: role ("Dean") + person name patterns
    - Avoids false positives ("dean's office", etc.)
    - Deterministic ordering (document order)
    - Preserves provenance via source_chunk_ids metadata
    - Synthetic chunk injected at top, original chunks preserved for citation
    
    Args:
        documents: List of Document objects from chunk_document()
    
    Returns:
        List of Document objects with synthetic Deans chunk prepended
    """
    
    # Collect dean chunks - must have BOTH "dean" AND person title indicators
    dean_chunks = []
    dean_text_entries = []
    
    for i, doc in enumerate(documents):
        content = doc.metadata.get('original_text', doc.page_content)
        content_lower = content.lower()
        
        # Semantic detection: must have both "dean" and person name pattern
        if 'dean' in content_lower:
            # Check for person name indicators (titles like Dr., Engr., etc.)
            has_person_title = any(
                title in content_lower 
                for title in ['dr.', 'engr.', 'arch.', 'prof.', 'mr.', 'ms.', 'mrs.']
            )
            
            if has_person_title:
                # This chunk likely contains dean information
                # Avoid false positives like "dean's office" or dean role descriptions
                if "dean's" not in content_lower and "office" not in content_lower[:150]:
                    # Avoid role description chunks (like "13. DEAN\nIs tasked to assist...")
                    if not ("is tasked" in content_lower or "responsibilities" in content_lower[:200]):
                        dean_chunks.append({
                            'chunk_id': doc.metadata.get('chunk_id', i),
                            'content': content,
                            'pages': doc.metadata.get('page_numbers', []),
                            'document': doc
                        })
    
    # If we found dean chunks, consolidate them
    if dean_chunks:
        # Sort by page number (not chunk ID) to ensure structured lists come first
        # Earlier pages (e.g., page 12 with main DEANS list) should come before later pages
        dean_chunks.sort(key=lambda x: min(x['pages']) if x['pages'] else 999)
        
        combined_content = []
        for chunk in dean_chunks:
            # Clean up the content - remove excessive whitespace
            content = chunk['content'].strip()
            if content and content not in combined_content:
                combined_content.append(content)
        
        # Create synthetic chunk content
        # Format: Title + All dean chunk content (page-ordered, so structured lists appear first)
        synthetic_content = "Deans\n\n" + "\n\n---\n\n".join(combined_content)
        
        # Create synthetic chunk metadata
        source_chunk_ids = [chunk['chunk_id'] for chunk in dean_chunks]
        source_pages = sorted(list(set(
            page 
            for chunk in dean_chunks 
            for page in chunk['pages']
        )))
        
        # Use metadata from first dean chunk as template
        template_metadata = dean_chunks[0]['document'].metadata.copy()
        
        synthetic_metadata = {
            **template_metadata,
            'chunk_id': -1,  # Special ID for synthetic chunk
            'section': 'Deans',
            'section_title': 'Deans',
            'original_text': synthetic_content,
            'is_synthetic': True,
            'entity_type': 'deans',
            'source_chunk_ids': source_chunk_ids,
            'page_numbers': source_pages,
            'element_types': ['Synthetic'],
            'num_entities': len(combined_content)
        }
        
        # Create synthetic document
        synthetic_doc = Document(
            page_content=normalize_text(synthetic_content),
            metadata=synthetic_metadata
        )
        
        # Prepend synthetic chunk to documents list
        # Keep original chunks for citation/context
        return [synthetic_doc] + documents
    
    # No dean information found, return original documents
    return documents
