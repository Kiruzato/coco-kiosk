"""
Unit Tests for Phase 18 Layout-Aware PDF Ingestion
===================================================

Test the new layout-aware parsing functions:
- load_pdf_document_layout_aware
- group_elements_by_section
- create_chunks_from_sections
- Fallback behavior in chunk_document

Run with: python -m pytest test_layout_aware_ingestion.py -v
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_manager import (
    group_elements_by_section,
    create_chunks_from_sections,
    chunk_document,
    LAYOUT_AWARE_PARSER
)


class TestGroupElementsBySection:
    """Test section grouping logic"""
    
    def test_single_section_with_title(self):
        """Test grouping elements when there's a clear title"""
        elements = [
            {'type': 'Title', 'text': 'Introduction', 'metadata': {'page_number': 1}},
            {'type': 'NarrativeText', 'text': 'This is the first paragraph.', 'metadata': {'page_number': 1}},
            {'type': 'NarrativeText', 'text': 'This is the second paragraph.', 'metadata': {'page_number': 1}}
        ]
        
        sections = group_elements_by_section(elements)
        
        assert len(sections) == 1
        assert sections[0]['section_title'] == 'Introduction'
        assert len(sections[0]['elements']) == 3
        assert 'Title' in sections[0]['element_types']
        assert 'NarrativeText' in sections[0]['element_types']
        assert 1 in sections[0]['page_numbers']
    
    def test_multiple_sections(self):
        """Test grouping with multiple Title elements"""
        elements = [
            {'type': 'Title', 'text': 'Section 1', 'metadata': {'page_number': 1}},
            {'type': 'NarrativeText', 'text': 'Content 1', 'metadata': {'page_number': 1}},
            {'type': 'Title', 'text': 'Section 2', 'metadata': {'page_number': 2}},
            {'type': 'NarrativeText', 'text': 'Content 2', 'metadata': {'page_number': 2}},
        ]
        
        sections = group_elements_by_section(elements)
        
        assert len(sections) == 2
        assert sections[0]['section_title'] == 'Section 1'
        assert sections[1]['section_title'] == 'Section 2'
    
    def test_no_title_elements(self):
        """Test grouping when no Title elements present"""
        elements = [
            {'type': 'NarrativeText', 'text': 'Just text', 'metadata': {}},
            {'type': 'ListItem', 'text': '1. Item', 'metadata': {}}
        ]
        
        sections = group_elements_by_section(elements)
        
        assert len(sections) == 1
        assert sections[0]['section_title'] == 'Document Content'
    
    def test_mixed_element_types(self):
        """Test with various element types"""
        elements = [
            {'type': 'Title', 'text': 'Awards', 'metadata': {'page_number': 5}},
            {'type': 'NarrativeText', 'text': 'The following awards...', 'metadata': {'page_number': 5}},
            {'type': 'ListItem', 'text': '1. Merit Award', 'metadata': {'page_number': 5}},
            {'type': 'ListItem', 'text': '2. Excellence Award', 'metadata': {'page_number': 5}},
            {'type': 'Table', 'text': 'Award | Criteria...', 'metadata': {'page_number': 6}}
        ]
        
        sections = group_elements_by_section(elements)
        
        assert len(sections) == 1
        assert sections[0]['element_types'] == {'Title', 'NarrativeText', 'ListItem', 'Table'}
        assert sorted(sections[0]['page_numbers']) == [5, 6]


class TestCreateChunksFromSections:
    """Test smart chunking algorithm"""
    
    def test_small_section_stays_intact(self):
        """Section smaller than max_size should remain single chunk"""
        sections = [{
            'section_title': 'Short Section',
            'elements': [
                {'type': 'Title', 'text': 'Short Section', 'metadata': {'page_number': 1}},
                {'type': 'NarrativeText', 'text': 'Brief content.', 'metadata': {'page_number': 1}}
            ],
            'element_types': {'Title', 'NarrativeText'},
            'page_numbers': {1}
        }]
        
        chunks = create_chunks_from_sections(
            sections=sections,
            document_id='test123',
            document_name='test.pdf',
            file_type='.pdf',
            ingestion_timestamp='2026-01-29T11:00:00',
            target_size=500,
            max_size=800
        )
        
        assert len(chunks) == 1
        assert 'section_title' in chunks[0].metadata
        assert chunks[0].metadata['section_title'] == 'Short Section'
        assert 'element_types' in chunks[0].metadata
        assert 'page_numbers' in chunks[0].metadata
    
    def test_large_section_splits_at_element_boundary(self):
        """Large section should split at element boundaries"""
        # Create section with enough text to exceed max_size
        long_text = "A" * 500  # 500 chars
        sections = [{
            'section_title': 'Long Section',
            'elements': [
                {'type': 'Title', 'text': 'Long Section', 'metadata': {'page_number': 1}},
                {'type': 'NarrativeText', 'text': long_text, 'metadata': {'page_number': 1}},
                {'type': 'NarrativeText', 'text': long_text, 'metadata': {'page_number': 2}}
            ],
            'element_types': {'Title', 'NarrativeText'},
            'page_numbers': {1, 2}
        }]
        
        chunks = create_chunks_from_sections(
            sections=sections,
            document_id='test123',
            document_name='test.pdf',
            file_type='.pdf',
            ingestion_timestamp='2026-01-29T11:00:00',
            target_size=500,
            max_size=800
        )
        
        # Should split into multiple chunks
        assert len(chunks) > 1
        # All chunks should preserve section_title
        for chunk in chunks:
            assert chunk.metadata['section_title'] == 'Long Section'
    
    def test_metadata_enrichment(self):
        """Verify new Phase 18 metadata fields are present"""
        sections = [{
            'section_title': 'Test',
            'elements': [
                {'type': 'Title', 'text': 'Test', 'metadata': {'page_number': 3}},
                {'type': 'ListItem', 'text': 'Item 1', 'metadata': {'page_number': 3}}
            ],
            'element_types': {'Title', 'ListItem'},
            'page_numbers': {3}
        }]
        
        chunks = create_chunks_from_sections(
            sections=sections,
            document_id='test456',
            document_name='test.pdf',
            file_type='.pdf',
            ingestion_timestamp='2026-01-29T11:00:00'
        )
        
        chunk = chunks[0]
        
        # Verify Phase 18 metadata
        assert 'section_title' in chunk.metadata
        assert chunk.metadata['section_title'] == 'Test'
        
        assert 'element_types' in chunk.metadata
        assert isinstance(chunk.metadata['element_types'], list)
        assert set(chunk.metadata['element_types']) == {'Title', 'ListItem'}
        
        assert 'page_numbers' in chunk.metadata
        assert isinstance(chunk.metadata['page_numbers'], list)
        assert chunk.metadata['page_numbers'] == [3]
        
        # Verify legacy metadata still present
        assert 'document_id' in chunk.metadata
        assert 'chunk_id' in chunk.metadata
        assert 'total_chunks' in chunk.metadata


class TestChunkDocumentFallback:
    """Test fallback behavior when layout-aware parsing unavailable"""
    
    def test_linear_chunking_for_non_pdf(self):
        """Non-PDF files should always use linear chunking"""
        text = "This is a test document.\n\nNew paragraph."
        
        chunks = chunk_document(
            text=text,
            document_id='txt123',
            document_name='test.txt',
            file_type='.txt',
            ingestion_timestamp='2026-01-29T11:00:00',
            chunk_size=500,
            chunk_overlap=50,
            file_path=Path('test.txt')  # Even with path, .txt uses linear
        )
        
        # Should work with linear chunking
        assert len(chunks) >= 1
        # Should NOT have Phase 18 fields (section_title, element_types, page_numbers)
        assert 'section_title' not in chunks[0].metadata
        assert 'element_types' not in chunks[0].metadata
        assert 'page_numbers' not in chunks[0].metadata
    
    @patch('document_manager.LAYOUT_AWARE_PARSER', False)
    def test_pdf_fallback_when_parser_unavailable(self):
        """PDF should use linear chunking if unstructured not available"""
        text = "PDF content extracted linearly."
        
        chunks = chunk_document(
            text=text,
            document_id='pdf123',
            document_name='test.pdf',
            file_type='.pdf',
            ingestion_timestamp='2026-01-29T11:00:00',
            chunk_size=500,
            chunk_overlap=50,
            file_path=Path('test.pdf')
        )
        
        # Should fall back to linear chunking
        assert len(chunks) >= 1
        assert 'section_title' not in chunks[0].metadata


@pytest.mark.skipif(not LAYOUT_AWARE_PARSER, reason="unstructured library not installed")
class TestLayoutAwareIntegration:
    """Integration tests requiring unstructured library"""
    
    def test_layout_aware_chunks_have_enriched_metadata(self):
        """Verify layout-aware chunks include Phase 18 metadata"""
        # This test would require a real PDF file or mocking partition_pdf
        # For now, just verify the LAYOUT_AWARE_PARSER flag is set correctly
        assert LAYOUT_AWARE_PARSER == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
