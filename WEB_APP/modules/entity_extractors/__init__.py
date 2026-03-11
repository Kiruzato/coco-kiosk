"""
Entity Extractors Package
==========================

Deterministic entity extraction for RAG enumeration queries.

Following industry-standard RAG architecture:
    Retrieval → Deterministic extraction → LLM formatting (optional)

NOT:
    Retrieval → LLM guessing

Modules:
- deans: Dean entity extraction and enumeration (Phase 18.2)
- awards: Awards and honors extraction and enumeration (Phase 27)
- dates: Event dates and times extraction (Phase 31)
- contacts: Office/location contact information extraction (Phase 31)
"""

from .deans import extract_deans_from_text, is_dean_enumeration_query, format_dean_list
from .awards import extract_awards_from_text, is_awards_enumeration_query, format_awards_list
from .dates import extract_events_from_text, is_event_date_query, format_event_list
from .contacts import extract_contacts_from_text, is_contact_query, format_contact_list

__all__ = [
    # Deans (Phase 18.2)
    'extract_deans_from_text',
    'is_dean_enumeration_query',
    'format_dean_list',
    # Awards (Phase 27)
    'extract_awards_from_text',
    'is_awards_enumeration_query',
    'format_awards_list',
    # Dates (Phase 31)
    'extract_events_from_text',
    'is_event_date_query',
    'format_event_list',
    # Contacts (Phase 31)
    'extract_contacts_from_text',
    'is_contact_query',
    'format_contact_list',
]
