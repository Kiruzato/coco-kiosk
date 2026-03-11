# ==============================================================================
# WARNING: SYNCHRONIZED FILE
# ==============================================================================
# This file exists in TWO locations:
#   1. WEB_APP/modules/metadata_index.py       (runtime)
#   2. INGESTION_MODULE/modules/metadata_index.py  (ingestion)
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
Phase 25: Metadata Index for Fast Filtering
============================================

Provides O(1) lookups by metadata fields (chunk_id, section, page, document)
without iterating the entire FAISS docstore.

Key Benefits:
- Fast adjacent chunk lookup for Phase 19 expansion
- Section-filtered queries (e.g., "all chunks in Deans section")
- Page-based queries (e.g., "all chunks from page 12")
- Synthetic/appendix chunk identification
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)

# Default path for metadata index
DEFAULT_INDEX_PATH = Path(__file__).parent / "data" / "metadata_index.json"


class MetadataIndex:
    """
    Persistent metadata index for fast chunk lookups.

    Provides O(1) access to chunks by:
    - chunk_id (primary key)
    - section/section_title
    - page number
    - document_id

    Usage:
        index = MetadataIndex()
        if not index.load():
            index.build_from_vector_store(vector_store)
            index.save()

        # Fast lookups
        info = index.get_chunk_info(chunk_id=62)
        docstore_id = index.get_docstore_id(chunk_id=62)
        chunks = index.get_chunks_by_section("Deans")
        chunks = index.get_chunks_by_page(12)
    """

    VERSION = "1.0"

    def __init__(self, index_path: Optional[str] = None):
        """
        Initialize metadata index.

        Args:
            index_path: Path to JSON index file. Defaults to data/metadata_index.json
        """
        self.index_path = Path(index_path) if index_path else DEFAULT_INDEX_PATH

        # Primary index: chunk_id -> {docstore_id, section, section_title, pages, document_id, ...}
        self.by_chunk_id: Dict[int, Dict[str, Any]] = {}

        # Secondary indexes: field_value -> [chunk_ids]
        self.by_section: Dict[str, List[int]] = {}
        self.by_section_title: Dict[str, List[int]] = {}
        self.by_page: Dict[int, List[int]] = {}
        self.by_document: Dict[str, List[int]] = {}

        # Special chunk lists
        self.synthetic_chunks: List[int] = []
        self.appendix_chunks: List[int] = []

        # Metadata
        self.last_updated: Optional[str] = None
        self.total_chunks: int = 0
        self.document_id: Optional[str] = None

    def build_from_vector_store(self, vector_store) -> None:
        """
        Build index from FAISS vector store docstore.

        Iterates docstore ONCE to build all indexes.

        Args:
            vector_store: FAISS vector store with docstore
        """
        logger.info("[PHASE25] Building metadata index from vector store...")

        # Clear existing data
        self._clear()

        if vector_store is None:
            logger.warning("[PHASE25] Vector store is None, cannot build index")
            return

        # Get docstore mapping
        try:
            docstore = vector_store.docstore
            index_to_docstore = vector_store.index_to_docstore_id
        except AttributeError as e:
            logger.error(f"[PHASE25] Invalid vector store structure: {e}")
            return

        # Iterate docstore once
        chunks_processed = 0
        documents_seen: Set[str] = set()

        for faiss_idx, docstore_id in index_to_docstore.items():
            try:
                doc = docstore.search(docstore_id)
                if doc is None:
                    continue

                metadata = doc.metadata
                chunk_id = metadata.get('chunk_id')

                if chunk_id is None:
                    continue

                # Ensure chunk_id is int (handles string keys from JSON)
                chunk_id = int(chunk_id)

                # Extract metadata fields
                section = metadata.get('section', '')
                section_title = metadata.get('section_title', section)
                pages = metadata.get('page_numbers', [])
                document_id = metadata.get('document_id', '')
                document_name = metadata.get('document_name', '')
                is_synthetic = metadata.get('is_synthetic', False)
                is_appendix = metadata.get('is_appendix', False)
                entity_type = metadata.get('entity_type')

                # Build primary index
                self.by_chunk_id[chunk_id] = {
                    'docstore_id': docstore_id,
                    'faiss_idx': faiss_idx,
                    'section': section,
                    'section_title': section_title,
                    'pages': pages,
                    'document_id': document_id,
                    'document_name': document_name,
                    'is_synthetic': is_synthetic,
                    'is_appendix': is_appendix,
                    'entity_type': entity_type,
                }

                # Build secondary indexes
                # By section
                if section:
                    if section not in self.by_section:
                        self.by_section[section] = []
                    self.by_section[section].append(chunk_id)

                # By section_title
                if section_title:
                    if section_title not in self.by_section_title:
                        self.by_section_title[section_title] = []
                    self.by_section_title[section_title].append(chunk_id)

                # By page
                for page in pages:
                    page = int(page)
                    if page not in self.by_page:
                        self.by_page[page] = []
                    self.by_page[page].append(chunk_id)

                # By document
                if document_id:
                    if document_id not in self.by_document:
                        self.by_document[document_id] = []
                    self.by_document[document_id].append(chunk_id)
                    documents_seen.add(document_id)

                # Special lists
                if is_synthetic:
                    self.synthetic_chunks.append(chunk_id)

                if is_appendix:
                    self.appendix_chunks.append(chunk_id)

                chunks_processed += 1

            except Exception as e:
                logger.warning(f"[PHASE25] Error processing docstore entry {docstore_id}: {e}")

        # Sort all lists for consistent ordering
        self._sort_all_indexes()

        # Set metadata
        self.total_chunks = chunks_processed
        self.last_updated = datetime.now().isoformat()
        self.document_id = list(documents_seen)[0] if len(documents_seen) == 1 else None

        logger.info(f"[PHASE25] Built metadata index: {chunks_processed} chunks, "
                   f"{len(self.by_section)} sections, {len(self.by_page)} pages, "
                   f"{len(self.synthetic_chunks)} synthetic, {len(self.appendix_chunks)} appendix")

    def _clear(self) -> None:
        """Clear all index data."""
        self.by_chunk_id.clear()
        self.by_section.clear()
        self.by_section_title.clear()
        self.by_page.clear()
        self.by_document.clear()
        self.synthetic_chunks.clear()
        self.appendix_chunks.clear()
        self.last_updated = None
        self.total_chunks = 0
        self.document_id = None

    def _sort_all_indexes(self) -> None:
        """Sort all chunk_id lists for consistent ordering."""
        for section in self.by_section:
            self.by_section[section].sort()
        for section_title in self.by_section_title:
            self.by_section_title[section_title].sort()
        for page in self.by_page:
            self.by_page[page].sort()
        for doc_id in self.by_document:
            self.by_document[doc_id].sort()
        self.synthetic_chunks.sort()
        self.appendix_chunks.sort()

    def save(self) -> bool:
        """
        Persist index to JSON file.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Ensure directory exists
            self.index_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert chunk_id keys to strings for JSON compatibility
            by_chunk_id_json = {str(k): v for k, v in self.by_chunk_id.items()}
            by_page_json = {str(k): v for k, v in self.by_page.items()}

            data = {
                "version": self.VERSION,
                "last_updated": self.last_updated or datetime.now().isoformat(),
                "document_id": self.document_id,
                "total_chunks": self.total_chunks,
                "indexes": {
                    "by_chunk_id": by_chunk_id_json,
                    "by_section": self.by_section,
                    "by_section_title": self.by_section_title,
                    "by_page": by_page_json,
                    "by_document": self.by_document,
                    "synthetic_chunks": self.synthetic_chunks,
                    "appendix_chunks": self.appendix_chunks,
                },
                "stats": {
                    "sections": len(self.by_section),
                    "section_titles": len(self.by_section_title),
                    "pages": len(self.by_page),
                    "documents": len(self.by_document),
                    "synthetic": len(self.synthetic_chunks),
                    "appendix": len(self.appendix_chunks),
                }
            }

            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info(f"[PHASE25] Saved metadata index to {self.index_path}")
            return True

        except Exception as e:
            logger.error(f"[PHASE25] Failed to save metadata index: {e}")
            return False

    def load(self) -> bool:
        """
        Load index from JSON file.

        Returns:
            True if loaded successfully, False if file not found or error
        """
        if not self.index_path.exists():
            logger.info(f"[PHASE25] Metadata index not found at {self.index_path}")
            return False

        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Version check
            version = data.get("version", "0.0")
            if version != self.VERSION:
                logger.warning(f"[PHASE25] Index version mismatch: {version} != {self.VERSION}")

            # Load metadata
            self.last_updated = data.get("last_updated")
            self.document_id = data.get("document_id")
            self.total_chunks = data.get("total_chunks", 0)

            # Load indexes
            indexes = data.get("indexes", {})

            # Convert string keys back to int for by_chunk_id
            by_chunk_id_json = indexes.get("by_chunk_id", {})
            self.by_chunk_id = {int(k): v for k, v in by_chunk_id_json.items()}

            self.by_section = indexes.get("by_section", {})
            self.by_section_title = indexes.get("by_section_title", {})

            # Convert string keys back to int for by_page
            by_page_json = indexes.get("by_page", {})
            self.by_page = {int(k): v for k, v in by_page_json.items()}

            self.by_document = indexes.get("by_document", {})
            self.synthetic_chunks = indexes.get("synthetic_chunks", [])
            self.appendix_chunks = indexes.get("appendix_chunks", [])

            logger.info(f"[PHASE25] Loaded metadata index: {self.total_chunks} chunks, "
                       f"{len(self.by_section)} sections")
            return True

        except Exception as e:
            logger.error(f"[PHASE25] Failed to load metadata index: {e}")
            self._clear()
            return False

    # =========================================================================
    # Fast Lookup Methods
    # =========================================================================

    def get_chunk_info(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full metadata for a chunk.

        Args:
            chunk_id: Chunk ID (can be negative for synthetic chunks)

        Returns:
            Dict with docstore_id, section, pages, etc. or None if not found
        """
        return self.by_chunk_id.get(chunk_id)

    def get_docstore_id(self, chunk_id: int) -> Optional[str]:
        """
        Get FAISS docstore ID for a chunk.

        This is the key needed to retrieve the actual Document from docstore.

        Args:
            chunk_id: Chunk ID

        Returns:
            Docstore ID string or None if not found
        """
        info = self.by_chunk_id.get(chunk_id)
        return info.get('docstore_id') if info else None

    def get_chunks_by_section(self, section: str) -> List[int]:
        """
        Get all chunk IDs in a section.

        Args:
            section: Section name (e.g., "Deans", "Library")

        Returns:
            List of chunk IDs in that section (sorted)
        """
        return self.by_section.get(section, [])

    def get_chunks_by_section_title(self, section_title: str) -> List[int]:
        """
        Get all chunk IDs with a specific section title.

        Args:
            section_title: Section title

        Returns:
            List of chunk IDs (sorted)
        """
        return self.by_section_title.get(section_title, [])

    def get_chunks_by_page(self, page: int) -> List[int]:
        """
        Get all chunk IDs on a specific page.

        Args:
            page: Page number

        Returns:
            List of chunk IDs on that page (sorted)
        """
        return self.by_page.get(page, [])

    def get_chunks_by_page_range(self, start_page: int, end_page: int) -> List[int]:
        """
        Get all chunk IDs in a page range (inclusive).

        Args:
            start_page: Start page number
            end_page: End page number (inclusive)

        Returns:
            List of unique chunk IDs in range (sorted)
        """
        chunk_ids: Set[int] = set()
        for page in range(start_page, end_page + 1):
            chunk_ids.update(self.by_page.get(page, []))
        return sorted(chunk_ids)

    def get_chunks_by_document(self, document_id: str) -> List[int]:
        """
        Get all chunk IDs for a document.

        Args:
            document_id: Document ID

        Returns:
            List of chunk IDs for that document (sorted)
        """
        return self.by_document.get(document_id, [])

    def get_adjacent_chunk_ids(self, chunk_id: int, window: int = 1) -> List[int]:
        """
        Get adjacent chunk IDs without docstore iteration.

        Args:
            chunk_id: Center chunk ID
            window: Number of chunks on each side (default 1 = prev + next)

        Returns:
            List of adjacent chunk IDs that exist in the index
        """
        adjacent = []
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            adj_id = chunk_id + offset
            if adj_id in self.by_chunk_id:
                adjacent.append(adj_id)
        return sorted(adjacent)

    def get_synthetic_chunks(self) -> List[int]:
        """Get all synthetic chunk IDs."""
        return self.synthetic_chunks.copy()

    def get_appendix_chunks(self) -> List[int]:
        """Get all appendix chunk IDs."""
        return self.appendix_chunks.copy()

    def has_chunk(self, chunk_id: int) -> bool:
        """Check if chunk exists in index."""
        return chunk_id in self.by_chunk_id

    def get_all_sections(self) -> List[str]:
        """Get list of all section names."""
        return list(self.by_section.keys())

    def get_all_section_titles(self) -> List[str]:
        """Get list of all section titles."""
        return list(self.by_section_title.keys())

    def get_page_range(self) -> tuple:
        """Get min and max page numbers."""
        if not self.by_page:
            return (0, 0)
        pages = list(self.by_page.keys())
        return (min(pages), max(pages))

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_chunks": self.total_chunks,
            "sections": len(self.by_section),
            "section_titles": len(self.by_section_title),
            "pages": len(self.by_page),
            "documents": len(self.by_document),
            "synthetic": len(self.synthetic_chunks),
            "appendix": len(self.appendix_chunks),
            "last_updated": self.last_updated,
        }
