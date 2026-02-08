"""
Unit Tests for Dean Entity Extraction - Phase 18.2
===================================================

Tests deterministic dean extraction functionality:
- Intent detection
- Extraction accuracy (6/6 deans)
- Deduplication
- Ordering preservation
- Output formatting
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'campus_rag_chatbot'))

from entity_extractors import (
    extract_deans_from_text,
    is_dean_enumeration_query,
    format_dean_list
)


class TestIntentDetection:
    """Test dean enumeration query detection"""
    
    def test_who_are_deans(self):
        """Test 'who are the deans' query"""
        assert is_dean_enumeration_query("who are the deans") == True
        assert is_dean_enumeration_query("Who are the deans?") == True
        assert is_dean_enumeration_query("WHO ARE THE DEANS") == True
    
    def test_list_deans(self):
        """Test 'list deans' query"""
        assert is_dean_enumeration_query("list all deans") == True
        assert is_dean_enumeration_query("list the deans") == True
        assert is_dean_enumeration_query("list deans") == True
    
    def test_show_deans(self):
        """Test 'show deans' query"""
        assert is_dean_enumeration_query("show deans") == True
        assert is_dean_enumeration_query("show me the deans") == True
        assert is_dean_enumeration_query("show all deans") == True
    
    def test_non_enumeration_queries(self):
        """Test queries that should NOT trigger enumeration"""
        assert is_dean_enumeration_query("who is the dean of CASEd") == False
        assert is_dean_enumeration_query("what does the dean do") == False
        assert is_dean_enumeration_query("where is the dean's office") == False
        assert is_dean_enumeration_query("dean responsibilities") == False
        assert is_dean_enumeration_query("contact the dean") == False


class TestDeanExtraction:
    """Test extraction of dean entities from text"""
    
    def test_extract_all_6_deans(self):
        """Test extraction of all 6 deans from synthetic chunk"""
        synthetic_chunk = """
        Deans
        DEANS
        DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
        DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        Engr. NOEL H. YAP (College of Computer Studies)
        Arch. CORAZON Z. GONZALES (College of Architecture)
        Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
        """
        
        deans = extract_deans_from_text(synthetic_chunk)
        
        # Assert count
        assert len(deans) == 6, f"Expected 6 deans, got {len(deans)}"
        
        # Extract names for easier assertion
        names = [d['full_name'] for d in deans]
        
        # Assert all 6 expected names present
        assert any('Almazan' in name for name in names), "Almazan not found"
        assert any('Capili' in name for name in names), "Capili not found"
        assert any('Matriano' in name for name in names), "Matriano not found"
        assert any('Yap' in name for name in names), "Yap not found"
        assert any('Gonzales' in name for name in names), "Gonzales not found"
        assert any('Gutierrez' in name for name in names), "Gutierrez not found"
    
    def test_name_normalization(self):
        """Test that names are normalized to title case"""
        text = """
        DR. ERIC A. MATRIANO (College of Business & Accountancy)
        ENGR. NOEL H. YAP (College of Computer Studies)
        """
        
        deans = extract_deans_from_text(text)
        
        assert len(deans) == 2
        
        # Names should be title case
        assert deans[0]['full_name'] == 'Dr. Eric A. Matriano'
        assert deans[1]['full_name'] == 'Engr. Noel H. Yap'
        
        # Titles should be normalized
        assert deans[0]['title'] == 'Dr.'
        assert deans[1]['title'] == 'Engr.'
    
    def test_college_extraction(self):
        """Test college information extraction"""
        text = """
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
        DR. LEILANI E. CAPILI Dean, College of Nursing & Asst. SAO Director
        """
        
        deans = extract_deans_from_text(text)
        
        assert len(deans) == 3
        
        # Check college extraction
        assert deans[0]['college'] == 'College of Business & Accountancy'
        assert deans[1]['college'] == 'CASEd'
        assert deans[2]['college'] == 'College of Nursing'  # Should remove "& Asst. SAO Director"
    
    def test_deduplication(self):
        """Test that duplicate dean entries are removed"""
        text = """
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        DR. ERIC A. MATRIANO Dean, College of Business
        Dr. Eric A. Matriano (Business)
        """
        
        deans = extract_deans_from_text(text)
        
        # Should deduplicate to 1 dean
        assert len(deans) == 1
        assert 'Matriano' in deans[0]['full_name']
    
    def test_document_order_preserved(self):
        """Test that extraction preserves document order"""
        text = """
        Engr. NOEL H. YAP (College of Computer Studies)
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        Arch. CORAZON Z. GONZALES (College of Architecture)
        """
        
        deans = extract_deans_from_text(text)
        
        assert len(deans) == 3
        
        # Check order
        assert 'Yap' in deans[0]['full_name']
        assert 'Matriano' in deans[1]['full_name']
        assert 'Gonzales' in deans[2]['full_name']
    
    def test_handles_dr_engr_title(self):
        """Test extraction of 'Dr. Engr.' double title"""
        text = """
        Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
        """
        
        deans = extract_deans_from_text(text)
        
        assert len(deans) == 1
        assert deans[0]['full_name'] == 'Dr. Engr. Vivian E. Gutierrez'
        assert deans[0]['title'] == 'Dr. Engr.'
        assert deans[0]['college'] == 'College of Engineering'
    
    def test_empty_text(self):
        """Test extraction from empty text"""
        deans = extract_deans_from_text("")
        assert len(deans) == 0
    
    def test_no_deans_in_text(self):
        """Test extraction when no deans present"""
        text = """
        This is some text about the university.
        There are no dean entries here.
        Just regular content.
        """
        
        deans = extract_deans_from_text(text)
        assert len(deans) == 0
    
    def test_filters_noise_headers(self):
        """Test that section headers are filtered out"""
        text = """
        DEANS
        DIRECTORS
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        SPECIAL PROVISION
        Engr. NOEL H. YAP (College of Computer Studies)
        """
        
        deans = extract_deans_from_text(text)
        
        # Should extract only the 2 deans, not headers
        assert len(deans) == 2


class TestOutputFormatting:
    """Test dean list output formatting"""
    
    def test_format_single_dean(self):
        """Test formatting of single dean"""
        deans = [{
            'full_name': 'Dr. Eric A. Matriano',
            'title': 'Dr.',
            'college': 'College of Business & Accountancy'
        }]
        
        output = format_dean_list(deans)
        
        assert "The deans are:" in output
        assert "1. Dr. Eric A. Matriano — Dean, College of Business & Accountancy" in output
    
    def test_format_multiple_deans(self):
        """Test formatting of multiple deans"""
        deans = [
            {
                'full_name': 'Dr. Eric A. Matriano',
                'title': 'Dr.',
                'college': 'College of Business & Accountancy'
            },
            {
                'full_name': 'Engr. Noel H. Yap',
                'title': 'Engr.',
                'college': 'College of Computer Studies'
            }
        ]
        
        output = format_dean_list(deans)
        
        assert "The deans are:" in output
        assert "1. Dr. Eric A. Matriano" in output
        assert "2. Engr. Noel H. Yap" in output
    
    def test_format_dean_without_college(self):
        """Test formatting of dean without college info"""
        deans = [{
            'full_name': 'Dr. Eric A. Matriano',
            'title': 'Dr.',
            'college': ''
        }]
        
        output = format_dean_list(deans)
        
        assert "1. Dr. Eric A. Matriano — Dean" in output
        assert "College" not in output  # No college mention
    
    def test_format_empty_list(self):
        """Test formatting of empty dean list"""
        output = format_dean_list([])
        
        assert "No deans found" in output


class TestEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_pipeline(self):
        """Test complete pipeline: detection → extraction → formatting"""
        query = "Who are the deans?"
        
        # Step 1: Intent detection
        is_enumeration = is_dean_enumeration_query(query)
        assert is_enumeration == True
        
        # Step 2: Extraction from synthetic chunk
        synthetic_chunk = """
        Deans
        DEANS
        DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
        DR. LEILANI E. CAPILI Dean, College of Nursing
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        Engr. NOEL H. YAP (College of Computer Studies)
        Arch. CORAZON Z. GONZALES (College of Architecture)
        Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
        """
        
        deans = extract_deans_from_text(synthetic_chunk)
        assert len(deans) == 6
        
        # Step 3: Formatting
        output = format_dean_list(deans)
        
        # Verify output structure
        assert "The deans are:" in output
        assert "1." in output
        assert "6." in output
        
        # Verify all names present
        assert "Almazan" in output
        assert "Capili" in output
        assert "Matriano" in output
        assert "Yap" in output
        assert "Gonzales" in output
        assert "Gutierrez" in output
    
    def test_determinism(self):
        """Test that extraction is deterministic (same result every time)"""
        text = """
        DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
        DR. LEILANI E. CAPILI Dean, College of Nursing
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        Engr. NOEL H. YAP (College of Computer Studies)
        Arch. CORAZON Z. GONZALES (College of Architecture)
        Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
        """
        
        # Run extraction 5 times
        results = []
        for _ in range(5):
            deans = extract_deans_from_text(text)
            names = [d['full_name'] for d in deans]
            results.append(names)
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result, "Extraction is not deterministic"


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
