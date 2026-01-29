"""
Entity Extractors Package
==========================

Deterministic entity extraction for RAG enumeration queries.

Following industry-standard RAG architecture:
    Retrieval → Deterministic extraction → LLM formatting (optional)

NOT:
    Retrieval → LLM guessing

Modules:
- deans: Dean entity extraction and enumeration
"""

from .deans import extract_deans_from_text, is_dean_enumeration_query, format_dean_list

__all__ = [
    'extract_deans_from_text',
    'is_dean_enumeration_query',
    'format_dean_list'
]
