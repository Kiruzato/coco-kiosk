# ==============================================================================
# WARNING: SYNCHRONIZED FILE
# ==============================================================================
# This file exists in TWO locations:
#   1. WEB_APP/modules/text_normalizer_pipeline.py       (runtime)
#   2. INGESTION_MODULE/modules/text_normalizer_pipeline.py  (ingestion)
#
# These copies are intentionally independent to maintain strict architectural
# isolation between WEB_APP and INGESTION_MODULE. Neither module may import
# from the other.
#
# ANY CHANGES to this file MUST be manually mirrored to the other copy.
# Failure to synchronize will cause behavioral divergence between runtime
# and ingestion environments.
# ==============================================================================
"""
PDF Text Normalization Pipeline - Phase 18.1
============================================

Deterministic preprocessing layer to clean PDF parsing artifacts before chunking.
Applied after layout extraction, before semantic sectioning.

Industry-standard approach following RAG best practices from:
- Pinecone documentation (document preprocessing)
- LlamaIndex text cleaning patterns
- Weaviate ingestion pipelines

No LLM usage - all transformations are rule-based and deterministic.
"""

import re
import unicodedata
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def normalize_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Master normalization pipeline applied to layout-parsed PDF elements.
    
    Pipeline stages:
    1. Whitespace normalization (element-level)
    2. Line reassembly (cross-element)
    3. OCR artifact removal (element-level)
    4. Person entry normalization (cross-element)
    5. Entity block cleanup (cross-element)
    
    Args:
        elements: List of element dicts from unstructured.partition.pdf
                  Each element has: {'text': str, 'type': str, 'metadata': {...}}
    
    Returns:
        Normalized elements with cleaned text
    """
    if not elements:
        return elements
    
    logger.info(f"Starting text normalization on {len(elements)} elements")
    
    # Stage 1: Whitespace normalization (per-element)
    elements = [_normalize_element_whitespace(elem) for elem in elements]
    
    # Stage 2: Line reassembly (cross-element)
    elements = _reassemble_fragmented_lines(elements)
    
    # Stage 3: OCR artifact removal (per-element)
    elements = [_remove_ocr_artifacts(elem) for elem in elements]
    
    # Stage 4: Person entry normalization (cross-element)
    elements = _normalize_person_entries(elements)
    
    # Stage 5: Entity block cleanup (cross-element)
    elements = _clean_entity_blocks(elements)
    
    logger.info(f"Normalization complete on {len(elements)} elements")
    
    return elements


# =============================================================================
# STAGE 1: WHITESPACE NORMALIZATION
# =============================================================================

def _normalize_element_whitespace(element: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize whitespace within a single element.
    
    Transformations:
    - Collapse 3+ spaces to single space
    - Remove trailing/leading whitespace
    - Normalize line breaks (CRLF → LF)
    - Remove excessive blank lines within element
    
    Args:
        element: Single element dict
    
    Returns:
        Element with normalized whitespace
    """
    text = element['text']
    
    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Collapse excessive spaces (3+ → 1)
    text = re.sub(r' {3,}', ' ', text)
    
    # Remove trailing whitespace from each line
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    
    # Remove excessive blank lines (2+ → 1)
    normalized_lines = []
    prev_blank = False
    for line in lines:
        is_blank = len(line.strip()) == 0
        if is_blank:
            if not prev_blank:
                normalized_lines.append(line)
            prev_blank = True
        else:
            normalized_lines.append(line)
            prev_blank = False
    
    text = '\n'.join(normalized_lines)
    
    # Final strip
    text = text.strip()
    
    element['text'] = text
    return element


# =============================================================================
# STAGE 2: LINE REASSEMBLY
# =============================================================================

def _reassemble_fragmented_lines(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reassemble fragmented person entries split across multiple elements.
    
    Pattern detection:
    - Person title (Dr., Engr., Arch.) without name on same line
    - Next element starts with capitalized name
    - Join into single element
    
    Args:
        elements: List of elements
    
    Returns:
        Elements with fragmented lines reassembled
    """
    if len(elements) < 2:
        return elements
    
    person_title_pattern = re.compile(r'^(Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s*$', re.IGNORECASE)
    
    reassembled = []
    i = 0
    
    while i < len(elements):
        current = elements[i]
        current_text = current['text'].strip()
        
        # Check if this element is a lone person title
        if person_title_pattern.match(current_text):
            # Look ahead for name on next element
            if i + 1 < len(elements):
                next_elem = elements[i + 1]
                next_text = next_elem['text'].strip()
                
                # If next element starts with capitalized word, it's likely the name
                if next_text and next_text[0].isupper():
                    # Merge
                    merged_text = f"{current_text} {next_text}"
                    merged_elem = {
                        'text': merged_text,
                        'type': current['type'],
                        'metadata': current['metadata'].copy()
                    }
                    reassembled.append(merged_elem)
                    i += 2  # Skip both elements
                    continue
        
        reassembled.append(current)
        i += 1
    
    return reassembled


# =============================================================================
# STAGE 3: OCR ARTIFACT REMOVAL
# =============================================================================

def _remove_ocr_artifacts(element: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove common OCR errors and artifacts.
    
    Transformations:
    - "CHARPERSON" → "CHAIRPERSON"
    - "Direcor" → "Director"
    - "OIrganization" → "Organization"
    - Unicode bullets (\\uf0b7) → removed
    - Unicode private use area chars → removed
    - Fix spacing around punctuation ("Asst .SAO" → "Asst. SAO")
    
    Args:
        element: Single element dict
    
    Returns:
        Element with OCR artifacts removed
    """
    text = element['text']
    
    # Specific OCR corrections
    text = re.sub(r'\bCHARPERSON(S)?\b', r'CHAIRPERSON\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bDirecor\b', 'Director', text)
    text = re.sub(r'\bOIrganization(s)?\b', r'Organization\1', text, flags=re.IGNORECASE)
    
    # Remove Unicode private use area characters (U+E000 to U+F8FF)
    # This includes bullets like \\uf0b7
    text = re.sub(r'[\ue000-\uf8ff]', '', text)
    
    # Fix spacing around periods in titles
    # "Asst ." → "Asst."
    text = re.sub(r'\b(\w+)\s+\.', r'\1.', text)
    
    # Fix spacing after periods in titles
    # "Asst." → "Asst. " (if followed by letter)
    text = re.sub(r'\.(\w)', r'. \1', text)
    
    # Normalize unicode characters (é → e, etc.)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    element['text'] = text
    return element


# =============================================================================
# STAGE 4: PERSON ENTRY NORMALIZATION
# =============================================================================

def _normalize_person_entries(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize person entry formatting for consistent structure.
    
    Transformations:
    - Standardize person title casing: "DR." → "Dr."
    - Remove role descriptor fragments ("& FACULTY")
    - Ensure clean format: "[Title] [Name], [Role], [College]"
    
    Args:
        elements: List of elements
    
    Returns:
        Elements with normalized person entries
    """
    person_title_map = {
        'DR.': 'Dr.',
        'ENGR.': 'Engr.',
        'ARCH.': 'Arch.',
        'PROF.': 'Prof.',
        'MR.': 'Mr.',
        'MS.': 'Ms.',
        'MRS.': 'Mrs.'
    }
    
    normalized = []
    
    for element in elements:
        text = element['text']
        
        # Standardize person titles
        for old_title, new_title in person_title_map.items():
            text = re.sub(rf'\b{old_title}\b', new_title, text, flags=re.IGNORECASE)
        
        # Remove "& FACULTY" descriptor
        text = re.sub(r'\s*&\s*FACULTY\b', '', text, flags=re.IGNORECASE)
        
        # Clean up College formatting
        # "( College" → "(College"
        text = re.sub(r'\(\s+', '(', text)
        
        element['text'] = text
        normalized.append(element)
    
    return normalized


# =============================================================================
# STAGE 5: ENTITY BLOCK CLEANUP
# =============================================================================

def _clean_entity_blocks(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean up enumeration blocks (Deans, Directors, etc.) by removing
    interspersed section headers and standalone role descriptors.
    
    Logic:
    - Detect dean/director enumeration blocks
    - Remove standalone section headers within blocks
    - Remove noise headers from WITHIN elements containing dean names
    - Keep only person entries
    
    Args:
        elements: List of elements
    
    Returns:
        Elements with cleaned enumeration blocks
    """
    if len(elements) < 3:
        return elements
    
    # Patterns for enumeration block detection
    enum_header_pattern = re.compile(r'^(DEANS|DIRECTORS|CHAIRPERSONS|CHAIRS|VPS|VICE PRESIDENTS)$', re.IGNORECASE)
    person_entry_pattern = re.compile(r'\b(Dr\.|Engr\.|Arch\.|Prof\.)\s+[A-Z]', re.IGNORECASE)
    
    # Section headers to remove when inside enum blocks (or within elements)
    noise_headers = [
        'Student Organizations',
        'Student OIrganizations',  # OCR variant
        'Special Provision',
        'SAS Directors',
        'Academic & Student Services Council',
        'CHAIRPERSONS'  # Remove "CHAIRPERSONS" prefix from dean entries
    ]
    
    # Stage 1: Remove standalone noise elements
    cleaned = []
    in_enum_block = False
    block_person_count = 0
    
    for i, element in enumerate(elements):
        text = element['text'].strip()
        
        # Check if starting enum block
        if enum_header_pattern.match(text):
            in_enum_block = True
            block_person_count = 0
            cleaned.append(element)
            continue
        
        # If in enum block
        if in_enum_block:
            # Check if this is a person entry
            if person_entry_pattern.search(text):
                cleaned.append(element)
                block_person_count += 1
                continue
            
            # Check if this is noise header to remove
            is_noise = any(noise.lower() in text.lower() for noise in noise_headers)
            
            # Also check for numbered provisions
            is_provision = re.match(r'^\d+\s+(Special\s+)?Provision', text, re.IGNORECASE)
            
            if is_noise or is_provision:
                # Skip this element (remove from enum block)
                continue
            
            # If we've seen person entries and now hit non-person, non-noise content,
            # exit enum block
            if block_person_count > 0 and len(text) > 3:
                in_enum_block = False
        
        cleaned.append(element)
    
    # Stage 2: Clean noise headers from WITHIN elements containing dean entries
    final_cleaned = []
    for element in cleaned:
        text = element['text']
        
        # If element contains dean entries, remove noise headers from it
        if person_entry_pattern.search(text):
            # Remove noise headers as separate lines
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                
                # Check if this line is a noise header
                is_noise_line = any(noise.lower() == line_stripped.lower() for noise in noise_headers)
                
                # Check if line is numbered provision
                is_provision_line = re.match(r'^\d+\s+(Special\s+)?Provision\s*$', line_stripped, re.IGNORECASE)
                
                # Check if line starts with "CHAIRPERSONS" prefix (mang led dean entry)
                has_chairperson_prefix = line_stripped.upper().startswith('CHAIRPERSONS ')
                
                if is_noise_line or is_provision_line:
                    # Skip this line
                    continue
                
                # If line has CHAIRPERSONS prefix, remove it
                if has_chairperson_prefix:
                    line = re.sub(r'^CHAIRPERSONS\s+', '', line, flags=re.IGNORECASE)
                
                cleaned_lines.append(line)
            
            text = '\n'.join(cleaned_lines)
            element['text'] = text.strip()
        
        final_cleaned.append(element)
    
    return final_cleaned


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_normalization_stats(original_elements: List[Dict[str, Any]], 
                           normalized_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get statistics about normalization transformations.
    
    Args:
        original_elements: Elements before normalization
        normalized_elements: Elements after normalization
    
    Returns:
        Dict with stats
    """
    original_count = len(original_elements)
    normalized_count = len(normalized_elements)
    
    original_chars = sum(len(e['text']) for e in original_elements)
    normalized_chars = sum(len(e['text']) for e in normalized_elements)
    
    return {
        'original_element_count': original_count,
        'normalized_element_count': normalized_count,
        'elements_removed': original_count - normalized_count,
        'original_char_count': original_chars,
        'normalized_char_count': normalized_chars,
        'chars_removed': original_chars - normalized_chars,
        'reduction_pct': ((original_chars - normalized_chars) / original_chars * 100) if original_chars > 0 else 0
    }
