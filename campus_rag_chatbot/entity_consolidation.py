"""
Entity-Centric Chunk Consolidation for Enumeration Roles
=========================================================

DEPRECATED: This module is superseded by consolidation_engine.py (Phase 24).
The functions are kept for backward compatibility but now delegate to the engine.

Original Purpose:
This module provides post-chunking consolidation for scattered entity information.
Specifically designed for enumeration queries like "Who are the deans".
"""

import warnings

import re
import logging
from typing import List, Dict, Set
from langchain_core.documents import Document
from text_normalizer import normalize_text

logger = logging.getLogger(__name__)

def consolidate_dean_chunks(documents: List[Document]) -> List[Document]:
    """
    DEPRECATED: Use ConsolidationEngine from consolidation_engine.py instead.

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
    warnings.warn(
        "consolidate_dean_chunks is deprecated. Use ConsolidationEngine instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
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
        
        # Phase 18.1: Additional cleanup for synthetic chunk
        # Remove noise headers that may have made it through sectioning
        noise_headers = [
            'Student Organizations',
            'Student OIrganizations',
            '9 Special Provision',
            'SAS Directors',
            'DIRECTORS & RESEARCH PROPONENTS'
        ]
        
        lines = synthetic_content.split('\n')
        cleaned_lines = []
        for line in lines:
            line_stripped = line.strip()
            
            # Skip noise header lines
            is_noise = any(noise.lower() == line_stripped.lower() for noise in noise_headers)
            
            # Skip numbered provision lines
            is_provision = re.match(r'^\d+\s+(Special\s+)?Provision\s*$', line_stripped, re.IGNORECASE)
            
            # Skip SAS Directors list line (starts with "SAS Directors")
            is_sas_directors = line_stripped.startswith('SAS Directors')
            
            if not is_noise and not is_provision and not is_sas_directors:
                cleaned_lines.append(line)
        
        synthetic_content = '\n'.join(cleaned_lines)
        
        # Collapse excessive whitespace (2+ spaces → 1 space, to handle 200+ space runs)
        synthetic_content = re.sub(r' {2,}', ' ', synthetic_content)
        
        # Remove lines that are just whitespace or fragments like "o"
        lines = synthetic_content.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Keep line if it's not empty or single char fragment
            if stripped and not (len(stripped) == 1 and not stripped.isalnum()):
                cleaned_lines.append(line)
        
        synthetic_content = '\n'.join(cleaned_lines)
        
        #Final strip
        synthetic_content = synthetic_content.strip()
        
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


def consolidate_prayer_chunks(documents: List[Document]) -> List[Document]:
    """
    DEPRECATED: Use ConsolidationEngine from consolidation_engine.py instead.

    Phase 21.1: Consolidate scattered prayer content into ONE synthetic chunk.

    Fixes fragmented "Prayer to St. Columban" which was split across chunks 647-650
    during PDF ingestion.

    Args:
        documents: List of Document objects from chunk_document()

    Returns:
        List of Document objects with synthetic Prayer chunk prepended
    """
    warnings.warn(
        "consolidate_prayer_chunks is deprecated. Use ConsolidationEngine instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # Detect prayer chunks using two-pass approach
    prayer_chunks = []
    anchor_chunk_id = None

    # First pass: Find the anchor chunk (main prayer chunk)
    for i, doc in enumerate(documents):
        content = doc.metadata.get('original_text', doc.page_content)
        content_lower = content.lower()
        section = doc.metadata.get('section', '').lower()

        # Primary detection: section title or explicit prayer header
        is_anchor = (
            'prayer to st. columban' in section or
            'prayer to st columban' in section or
            'prayer to st. columban' in content_lower or
            'prayer to st columban' in content_lower
        )

        if is_anchor:
            chunk_id = doc.metadata.get('chunk_id', i)
            anchor_chunk_id = chunk_id
            prayer_chunks.append({
                'chunk_id': chunk_id,
                'content': content,
                'pages': doc.metadata.get('page_numbers', []),
                'document': doc
            })

    # If no anchor found, return unchanged
    if anchor_chunk_id is None:
        return documents

    # Second pass: Find continuation chunks (adjacent to anchor, with prayer content)
    for i, doc in enumerate(documents):
        content = doc.metadata.get('original_text', doc.page_content)
        content_lower = content.lower()
        chunk_id = doc.metadata.get('chunk_id', i)

        # Skip if already added or not adjacent to anchor
        if chunk_id == anchor_chunk_id:
            continue

        # Check if this is a likely continuation (within +3 chunks of anchor)
        if isinstance(chunk_id, int) and isinstance(anchor_chunk_id, int):
            if anchor_chunk_id < chunk_id <= anchor_chunk_id + 3:
                # Check for prayer continuation content
                is_continuation = (
                    'o beloved columban' in content_lower or
                    'o blessed columban' in content_lower or
                    'through christ our lord' in content_lower or
                    ('amen' in content_lower and len(content) < 100) or
                    ('because of your love for christ' in content_lower) or
                    ('fullness of life' in content_lower)
                )

                if is_continuation:
                    prayer_chunks.append({
                        'chunk_id': chunk_id,
                        'content': content,
                        'pages': doc.metadata.get('page_numbers', []),
                        'document': doc
                    })

    # If only anchor found (no continuations), still create synthetic chunk
    if len(prayer_chunks) < 1:
        return documents

    logger.info(f"[PHASE21.1] Consolidating {len(prayer_chunks)} prayer chunks")

    # Sort by chunk_id to maintain document order
    prayer_chunks.sort(key=lambda x: x['chunk_id'])

    # Combine content (deduplicated)
    combined_content = []
    source_chunk_ids = []
    source_pages = []

    for chunk in prayer_chunks:
        content = chunk['content'].strip()
        if content and content not in combined_content:
            combined_content.append(content)
            source_chunk_ids.append(chunk['chunk_id'])
            source_pages.extend(chunk['pages'])

    # Create synthetic content - join with space to form continuous text
    synthetic_content = "Prayer to St. Columban\n\n" + " ".join(combined_content)

    # Clean up whitespace artifacts
    synthetic_content = re.sub(r'\s+', ' ', synthetic_content)
    synthetic_content = synthetic_content.replace(' .', '.').replace(' ,', ',')
    synthetic_content = synthetic_content.strip()

    # Get template metadata from first chunk
    template_metadata = prayer_chunks[0]['document'].metadata.copy()

    # Create synthetic metadata
    synthetic_metadata = {
        **template_metadata,
        'chunk_id': -2,  # Different from deans (-1)
        'section': 'Prayer to St. Columban',
        'section_title': 'Prayer to St. Columban',
        'original_text': synthetic_content,
        'is_synthetic': True,
        'entity_type': 'prayer',
        'source_chunk_ids': source_chunk_ids,
        'page_numbers': sorted(list(set(source_pages))),
        'element_types': ['Synthetic'],
        'consolidation_phase': '21.1'
    }

    # Create synthetic document with normalized text
    synthetic_doc = Document(
        page_content=normalize_text(synthetic_content),
        metadata=synthetic_metadata
    )

    logger.info(f"[PHASE21.1] Created synthetic prayer chunk: {len(synthetic_content)} chars from {len(source_chunk_ids)} chunks")

    # Prepend synthetic chunk to documents list
    return [synthetic_doc] + documents
