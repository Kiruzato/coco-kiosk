"""
Phase 18 Metadata Validation Script
====================================

Validates that Phase 18 layout-aware ingestion produced correct metadata enrichment.

Run after ingesting PDFs to verify:
- section_title field is present and non-empty
- element_types is a list of element types
- page_numbers is a list of integers
- Legacy metadata fields still present

Usage:
    python validate_phase18_metadata.py

This script loads the vector store and inspects chunk metadata.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_manager import DocumentManager


def validate_chunk_metadata(chunk_metadata: Dict, source: str) -> List[str]:
    """
    Validate a single chunk's metadata for Phase 18 compliance.
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check legacy metadata (should always be present)
    required_legacy = ['document_id', 'document_name', 'file_type', 'chunk_id', 'total_chunks', 'original_text']
    for field in required_legacy:
        if field not in chunk_metadata:
            errors.append(f"Missing required field: {field}")
    
    # Check Phase 18 metadata (should be present for PDF documents ingested with layout-aware parsing)
    if chunk_metadata.get('file_type') == '.pdf':
        # If section_title is present, it means layout-aware parsing was used
        if 'section_title' in chunk_metadata:
            # Validate section_title
            if not isinstance(chunk_metadata['section_title'], str):
                errors.append("section_title should be string")
            elif not chunk_metadata['section_title'].strip():
                errors.append("section_title is empty")
            
            # Validate element_types
            if 'element_types' not in chunk_metadata:
                errors.append("element_types missing (expected for layout-aware chunks)")
            else:
                if not isinstance(chunk_metadata['element_types'], list):
                    errors.append(f"element_types should be list, got {type(chunk_metadata['element_types'])}")
                elif len(chunk_metadata['element_types']) == 0:
                    errors.append("element_types is empty list")
            
            # Validate page_numbers (optional but should be list if present)
            if 'page_numbers' in chunk_metadata:
                if not isinstance(chunk_metadata['page_numbers'], list):
                    errors.append(f"page_numbers should be list, got {type(chunk_metadata['page_numbers'])}")
                elif chunk_metadata['page_numbers']:  # If not empty
                    # Check first element is int
                    if not isinstance(chunk_metadata['page_numbers'][0], int):
                        errors.append(f"page_numbers should contain integers, got {type(chunk_metadata['page_numbers'][0])}")
    
    return errors


def main():
    """Main validation routine"""
    print("=" * 70)
    print("Phase 18 Metadata Validation")
    print("=" * 70)
    print()
    
    # Initialize document manager
    registry_path = Path(__file__).parent / "document_registry.json"
    vector_store_path = Path(__file__).parent / "vector_store"
    
    if not vector_store_path.exists():
        print("[FAIL] Vector store not found. Ingest documents first.")
        return
    
    print(f"Loading vector store from: {vector_store_path}")
    
    try:
        manager = DocumentManager(registry_path, vector_store_path)
        vector_store = manager.load_vector_store()
        
        if not vector_store:
            print("[FAIL] Failed to load vector store")
            return
        
        print(f"[OK] Vector store loaded successfully")
        print()
        
        # Get sample chunks
        # Note: FAISS doesn't expose all chunks directly, so we use similarity search
        sample_query = "test"
        sample_chunks = vector_store.similarity_search(sample_query, k=20)
        
        print(f"Analyzing {len(sample_chunks)} sample chunks...")
        print()
        
        # Track statistics
        total_chunks = len(sample_chunks)
        pdf_chunks = 0
        layout_aware_chunks = 0
        linear_chunks = 0
        errors_by_chunk = []
        
        for idx, chunk in enumerate(sample_chunks):
            metadata = chunk.metadata
            errors = validate_chunk_metadata(metadata, f"chunk_{idx}")
            
            if metadata.get('file_type') == '.pdf':
                pdf_chunks += 1
                if 'section_title' in metadata:
                    layout_aware_chunks += 1
                else:
                    linear_chunks += 1
            
            if errors:
                errors_by_chunk.append({'chunk_id': idx, 'errors': errors, 'metadata': metadata})
        
        # Print statistics
        print("-" * 70)
        print("STATISTICS")
        print("-" * 70)
        print(f"Total chunks sampled: {total_chunks}")
        print(f"PDF chunks: {pdf_chunks}")
        print(f"  - Layout-aware (Phase 18): {layout_aware_chunks}")
        print(f"  - Linear chunking (legacy): {linear_chunks}")
        print()
        
        # Print validation results
        if errors_by_chunk:
            print("-" * 70)
            print("[WARN]  VALIDATION ERRORS FOUND")
            print("-" * 70)
            for item in errors_by_chunk:
                print(f"\nChunk {item['chunk_id']} ({item['metadata'].get('document_name', 'unknown')}):")
                for error in item['errors']:
                    print(f"  - {error}")
            print()
            print(f"[FAIL] {len(errors_by_chunk)} chunks have validation errors")
        else:
            print("[OK] All chunks have valid metadata")
        
        # Print sample metadata for inspection
        if layout_aware_chunks > 0:
            print()
            print("-" * 70)
            print("SAMPLE PHASE 18 METADATA")
            print("-" * 70)
            
            for chunk in sample_chunks:
                if chunk.metadata.get('section_title'):
                    print(f"\nDocument: {chunk.metadata.get('document_name')}")
                    print(f"Section: {chunk.metadata.get('section_title')}")
                    print(f"Element types: {chunk.metadata.get('element_types')}")
                    print(f"Page numbers: {chunk.metadata.get('page_numbers')}")
                    print(f"Chunk text preview: {chunk.page_content[:100]}...")
                    break
        
        print()
        print("=" * 70)
        if errors_by_chunk:
            print("RESULT: VALIDATION FAILED")
        else:
            print("RESULT: VALIDATION PASSED")
        print("=" * 70)
        
    except Exception as e:
        print(f"[FAIL] Error during validation: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
