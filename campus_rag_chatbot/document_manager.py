"""
Document Management System - Phase 3 + Text Normalization
==========================================================
This module handles document ingestion, metadata management, and indexing for the
campus RAG chatbot. Supports PDF, DOCX, and TXT formats.

Key Features:
- Multi-format document loading (PDF, DOCX, TXT)
- Enhanced metadata tracking (document_id, timestamp, file type)
- Duplicate detection
- Incremental ingestion
- Document registry management
- Text normalization for consistent retrieval (case-insensitive matching)
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Document loaders
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# PDF loaders
try:
    from pypdf import PdfReader
    PDF_LOADER = "pypdf"
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_LOADER = "PyPDF2"
    except ImportError:
        PDF_LOADER = None

# DOCX loader
try:
    from docx import Document as DocxDocument
    DOCX_LOADER = True
except ImportError:
    DOCX_LOADER = False

# Text normalization for consistent retrieval
from text_normalizer import normalize_text


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPPORTED_FORMATS = ['.txt', '.pdf', '.docx']


# ==============================================================================
# DOCUMENT REGISTRY MANAGEMENT
# ==============================================================================

class DocumentRegistry:
    """
    Manages a registry of ingested documents to track metadata and prevent duplicates.
    Registry is stored as a JSON file.
    """

    def __init__(self, registry_path: Path):
        """
        Initialize the document registry.

        Args:
            registry_path: Path to the JSON registry file
        """
        self.registry_path = registry_path
        self.documents = self._load_registry()

    def _load_registry(self) -> Dict:
        """Load the registry from disk or create a new one."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_registry(self):
        """Save the registry to disk."""
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2, default=str)
        logger.info(f"Registry saved to {self.registry_path}")

    def add_document(self, document_id: str, metadata: Dict):
        """
        Add a document to the registry.

        Args:
            document_id: Unique identifier for the document
            metadata: Document metadata dictionary
        """
        self.documents[document_id] = metadata
        self._save_registry()
        logger.info(f"Added document to registry: {metadata['document_name']} (ID: {document_id})")

    def remove_document(self, document_id: str) -> bool:
        """
        Remove a document from the registry.

        Args:
            document_id: Document identifier to remove

        Returns:
            True if removed, False if not found
        """
        if document_id in self.documents:
            doc_name = self.documents[document_id].get('document_name', 'Unknown')
            del self.documents[document_id]
            self._save_registry()
            logger.info(f"Removed document from registry: {doc_name} (ID: {document_id})")
            return True
        return False

    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata by ID."""
        return self.documents.get(document_id)

    def list_documents(self) -> List[Dict]:
        """
        List all documents in the registry.

        Returns:
            List of document metadata dictionaries
        """
        return [
            {"document_id": doc_id, **metadata}
            for doc_id, metadata in self.documents.items()
        ]

    def document_exists(self, file_hash: str) -> bool:
        """
        Check if a document with the given file hash already exists.

        Args:
            file_hash: SHA256 hash of the file

        Returns:
            True if document exists, False otherwise
        """
        for doc_metadata in self.documents.values():
            if doc_metadata.get('file_hash') == file_hash:
                return True
        return False

    def get_by_hash(self, file_hash: str) -> Optional[Tuple[str, Dict]]:
        """
        Get document ID and metadata by file hash.

        Returns:
            Tuple of (document_id, metadata) or None
        """
        for doc_id, metadata in self.documents.items():
            if metadata.get('file_hash') == file_hash:
                return (doc_id, metadata)
        return None


# ==============================================================================
# DOCUMENT LOADING UTILITIES
# ==============================================================================

def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of a file for duplicate detection.

    Args:
        file_path: Path to the file

    Returns:
        SHA256 hash as hexadecimal string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def extract_section_name(text_chunk: str) -> str:
    """
    Extract section name from a text chunk.

    Args:
        text_chunk: The text chunk to analyze

    Returns:
        Section name or "General Information"
    """
    lines = text_chunk.split('\n')
    for line in lines[:3]:
        line = line.strip()
        if line and (line.isupper() or (line[0].isupper() and len(line.split()) <= 5)):
            return line
    return "General Information"


def load_txt_document(file_path: Path) -> str:
    """
    Load a text document.

    Args:
        file_path: Path to the TXT file

    Returns:
        Document text content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_pdf_document(file_path: Path) -> str:
    """
    Load a PDF document.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text content

    Raises:
        ImportError: If PDF loader is not available
        Exception: If PDF cannot be read
    """
    if PDF_LOADER is None:
        raise ImportError("PDF loader not available. Install pypdf or PyPDF2.")

    try:
        reader = PdfReader(str(file_path))
        text_content = []

        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                text_content.append(text)

        logger.info(f"Extracted text from {len(reader.pages)} pages in {file_path.name}")
        return "\n\n".join(text_content)

    except Exception as e:
        logger.error(f"Failed to load PDF {file_path.name}: {str(e)}")
        raise


def load_pdf_structured(file_path: Path) -> Optional[List[dict]]:
    """
    Phase 18: Layout-aware PDF extraction using unstructured.
    Returns list of elements with type, text, and metadata,
    or None if unstructured is not available.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of element dicts with 'type', 'text', 'metadata' keys, or None
    """
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        logger.warning("[PHASE18] unstructured not installed, falling back to pypdf")
        return None

    try:
        elements = partition_pdf(
            filename=str(file_path),
            strategy="fast",
            include_page_breaks=True,
        )

        structured = []
        for el in elements:
            structured.append({
                "type": type(el).__name__,
                "text": str(el),
                "metadata": {
                    "page_number": el.metadata.page_number if hasattr(el.metadata, 'page_number') else None,
                }
            })

        logger.info(f"[PHASE18] Extracted {len(structured)} elements from {file_path.name}")
        return structured

    except Exception as e:
        logger.warning(f"[PHASE18] Structured extraction failed for {file_path.name}: {e}")
        return None


def chunk_by_sections(
    elements: List[dict],
    document_id: str,
    document_name: str,
    file_type: str,
    ingestion_timestamp: str,
    max_chunk_size: int = 1500
) -> List[Document]:
    """
    Phase 18: Group elements by section headings into semantic chunks.
    Long sections are sub-split to stay under max_chunk_size.

    Args:
        elements: List of element dicts from load_pdf_structured()
        document_id: Unique document identifier
        document_name: Original filename
        file_type: File extension
        ingestion_timestamp: ISO format timestamp
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of Document objects with metadata including section_title and page_number
    """
    # Group elements into sections by Title/Header boundaries
    sections = []
    current_title = "Untitled Section"
    current_texts = []
    current_pages = set()

    for el in elements:
        el_type = el["type"]
        el_text = el["text"].strip()
        if not el_text:
            continue

        if el_type in ("Title", "Header"):
            # Only treat as section boundary if the title is descriptive enough.
            # Short titles (< 5 words) that look like sub-headings within lists
            # (e.g., "DEANS", "Students") are kept as body text to avoid
            # fragmenting related content like meeting attendee lists.
            MIN_TITLE_WORDS = 3
            is_section_heading = len(el_text.split()) >= MIN_TITLE_WORDS

            if is_section_heading:
                # Save previous section
                if current_texts:
                    sections.append({
                        "title": current_title,
                        "text": "\n".join(current_texts),
                        "pages": sorted(current_pages) if current_pages else [],
                    })
                current_title = el_text
                current_texts = []
                current_pages = set()
            else:
                # Short title: treat as body text (preserves context flow)
                current_texts.append(el_text)
                page = el["metadata"].get("page_number")
                if page is not None:
                    current_pages.add(page)
        else:
            # Tables: preserve as-is with a marker
            if el_type == "Table":
                current_texts.append(f"[Table]\n{el_text}")
            else:
                current_texts.append(el_text)
            page = el["metadata"].get("page_number")
            if page is not None:
                current_pages.add(page)

    # Don't forget last section
    if current_texts:
        sections.append({
            "title": current_title,
            "text": "\n".join(current_texts),
            "pages": sorted(current_pages) if current_pages else [],
        })

    logger.info(f"[PHASE18] Detected {len(sections)} raw sections in {document_name}")

    # Merge small sections into their next neighbor to prevent fragmentation.
    # Sub-headings in meeting minutes, lists, etc. create tiny sections that
    # break related content apart. Merge sections under MIN_SECTION_SIZE chars.
    MIN_SECTION_SIZE = 200
    merged_sections = []
    carry_title = None
    carry_texts = []
    carry_pages = []

    for section in sections:
        combined_text = "\n".join(carry_texts + [section["text"]]) if carry_texts else section["text"]
        combined_title = carry_title or section["title"]
        combined_pages = sorted(set(carry_pages + section["pages"]))

        if len(combined_text) < MIN_SECTION_SIZE:
            # Too small, carry forward and merge with next section
            carry_title = combined_title
            carry_texts = [combined_text]
            carry_pages = combined_pages
        else:
            merged_sections.append({
                "title": combined_title,
                "text": combined_text,
                "pages": combined_pages,
            })
            carry_title = None
            carry_texts = []
            carry_pages = []

    # Flush any remaining carried content
    if carry_texts:
        if merged_sections:
            # Append to last section
            last = merged_sections[-1]
            last["text"] += "\n" + "\n".join(carry_texts)
            last["pages"] = sorted(set(last["pages"] + carry_pages))
        else:
            merged_sections.append({
                "title": carry_title or "Untitled Section",
                "text": "\n".join(carry_texts),
                "pages": carry_pages,
            })

    sections = merged_sections
    logger.info(f"[PHASE18] After merging small sections: {len(sections)} sections")

    # Convert sections to Document chunks, sub-splitting long sections
    documents = []
    chunk_id = 0

    for section in sections:
        # Prepend section title to body for grounding and LLM context
        title = section["title"]
        body = section["text"]
        text = f"{title}\n{body}" if title and title != "Untitled Section" else body
        base_metadata = {
            "document_id": document_id,
            "document_name": document_name,
            "file_type": file_type,
            "ingestion_timestamp": ingestion_timestamp,
            "section_title": section["title"],
            "page_number": section["pages"],
        }

        if len(text) <= max_chunk_size:
            normalized = normalize_text(text)
            doc = Document(
                page_content=normalized,
                metadata={
                    **base_metadata,
                    "chunk_id": chunk_id,
                    "section": section["title"],
                    "original_text": text,
                }
            )
            documents.append(doc)
            chunk_id += 1
        else:
            # Sub-split long sections
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_chunk_size,
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            sub_chunks = splitter.split_text(text)
            for sub in sub_chunks:
                normalized = normalize_text(sub)
                doc = Document(
                    page_content=normalized,
                    metadata={
                        **base_metadata,
                        "chunk_id": chunk_id,
                        "section": section["title"],
                        "original_text": sub,
                    }
                )
                documents.append(doc)
                chunk_id += 1

    # Update total_chunks in all documents
    total = len(documents)
    for doc in documents:
        doc.metadata["total_chunks"] = total

    # Log stats
    sizes = [len(d.page_content) for d in documents]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    logger.info(f"[PHASE18] Created {total} section-based chunks, avg size: {avg_size:.0f} chars")

    return documents


def load_docx_document(file_path: Path) -> str:
    """
    Load a DOCX document.

    Args:
        file_path: Path to the DOCX file

    Returns:
        Extracted text content

    Raises:
        ImportError: If DOCX loader is not available
        Exception: If DOCX cannot be read
    """
    if not DOCX_LOADER:
        raise ImportError("DOCX loader not available. Install python-docx.")

    try:
        doc = DocxDocument(str(file_path))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        logger.info(f"Extracted {len(paragraphs)} paragraphs from {file_path.name}")
        return "\n\n".join(paragraphs)

    except Exception as e:
        logger.error(f"Failed to load DOCX {file_path.name}: {str(e)}")
        raise


def load_document(file_path: Path) -> str:
    """
    Load a document based on its file extension.

    Args:
        file_path: Path to the document

    Returns:
        Extracted text content

    Raises:
        ValueError: If file format is not supported
        Exception: If document cannot be loaded
    """
    extension = file_path.suffix.lower()

    if extension == '.txt':
        return load_txt_document(file_path)
    elif extension == '.pdf':
        return load_pdf_document(file_path)
    elif extension == '.docx':
        return load_docx_document(file_path)
    else:
        raise ValueError(f"Unsupported file format: {extension}")


# ==============================================================================
# DOCUMENT CHUNKING AND METADATA
# ==============================================================================

def chunk_document(
    text: str,
    document_id: str,
    document_name: str,
    file_type: str,
    ingestion_timestamp: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Document]:
    """
    Chunk a document and attach metadata to each chunk.

    Args:
        text: Document text content
        document_id: Unique document identifier
        document_name: Original filename
        file_type: File extension (.txt, .pdf, .docx)
        ingestion_timestamp: ISO format timestamp
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between chunks

    Returns:
        List of Document objects with metadata
    """
    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    # Split text into chunks
    chunks = text_splitter.split_text(text)

    # Create Document objects with rich metadata
    # Text normalization: Store original text in metadata, use normalized for embedding
    documents = []
    for i, chunk in enumerate(chunks):
        section_name = extract_section_name(chunk)

        # Normalize text for consistent embedding (case-insensitive matching)
        normalized_chunk = normalize_text(chunk)

        metadata = {
            "document_id": document_id,
            "document_name": document_name,
            "file_type": file_type,
            "ingestion_timestamp": ingestion_timestamp,
            "chunk_id": i,
            "total_chunks": len(chunks),
            "section": section_name,
            "original_text": chunk  # Preserve original text for display/citation
        }

        # Use normalized text for page_content (embedding), original stored in metadata
        doc = Document(page_content=normalized_chunk, metadata=metadata)
        documents.append(doc)

    logger.info(f"Created {len(chunks)} chunks from {document_name}")
    return documents


# ==============================================================================
# DOCUMENT INGESTION
# ==============================================================================

class DocumentManager:
    """
    Main document management class that handles ingestion, indexing, and retrieval.
    """

    def __init__(
        self,
        registry_path: Path,
        vector_store_path: Path,
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize the document manager.

        Args:
            registry_path: Path to the document registry JSON file
            vector_store_path: Path to the vector store directory
            openai_api_key: OpenAI API key (uses env var if not provided)
        """
        self.registry = DocumentRegistry(registry_path)
        self.vector_store_path = vector_store_path
        self.api_key = openai_api_key or OPENAI_API_KEY

        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.embeddings = OpenAIEmbeddings(openai_api_key=self.api_key)
        self.vector_store = None

    def load_vector_store(self) -> Optional[FAISS]:
        """
        Load existing vector store from disk.

        Returns:
            FAISS vector store or None if not found
        """
        if self.vector_store_path.exists():
            logger.info(f"Loading vector store from {self.vector_store_path}")
            self.vector_store = FAISS.load_local(
                str(self.vector_store_path),
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            return self.vector_store
        logger.warning("No existing vector store found.")
        return None

    def save_vector_store(self):
        """Save the vector store to disk."""
        if self.vector_store:
            self.vector_store_path.mkdir(parents=True, exist_ok=True)
            self.vector_store.save_local(str(self.vector_store_path))
            logger.info(f"Vector store saved to {self.vector_store_path}")

    def ingest_document(
        self,
        file_path: Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        skip_duplicates: bool = True
    ) -> Tuple[bool, str]:
        """
        Ingest a single document into the vector store.

        Args:
            file_path: Path to the document file
            chunk_size: Chunk size for text splitting
            chunk_overlap: Overlap between chunks
            skip_duplicates: If True, skip documents that already exist

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate file exists
            if not file_path.exists():
                return False, f"File not found: {file_path}"

            # Validate file format
            if file_path.suffix.lower() not in SUPPORTED_FORMATS:
                return False, f"Unsupported format: {file_path.suffix}"

            # Calculate file hash for duplicate detection
            file_hash = calculate_file_hash(file_path)

            # Check for duplicates
            if skip_duplicates and self.registry.document_exists(file_hash):
                existing = self.registry.get_by_hash(file_hash)
                if existing:
                    doc_id, metadata = existing
                    return False, f"Duplicate: {metadata['document_name']} already ingested on {metadata['ingestion_timestamp']}"

            # Generate document ID and metadata
            document_id = hashlib.md5(f"{file_path.name}{datetime.now().isoformat()}".encode()).hexdigest()
            document_name = file_path.name
            file_type = file_path.suffix.lower()
            ingestion_timestamp = datetime.now().isoformat()

            logger.info(f"Ingesting document: {document_name}")

            documents = None

            # Phase 18: Try layout-aware structured extraction for PDFs
            if file_type == '.pdf':
                structured_elements = load_pdf_structured(file_path)
                if structured_elements:
                    documents = chunk_by_sections(
                        elements=structured_elements,
                        document_id=document_id,
                        document_name=document_name,
                        file_type=file_type,
                        ingestion_timestamp=ingestion_timestamp,
                    )
                    if documents:
                        logger.info(f"[PHASE18] Using section-based chunks for {document_name}")

            # Fallback: original text-based chunking (all formats, or PDF if structured failed)
            if not documents:
                text_content = load_document(file_path)

                if not text_content.strip():
                    return False, f"Document is empty: {document_name}"

                documents = chunk_document(
                    text=text_content,
                    document_id=document_id,
                    document_name=document_name,
                    file_type=file_type,
                    ingestion_timestamp=ingestion_timestamp,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )

            # Add to vector store (incremental)
            if self.vector_store is None:
                # Create new vector store
                logger.info("Creating new vector store")
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            else:
                # Add to existing vector store incrementally
                logger.info("Adding documents to existing vector store")
                self.vector_store.add_documents(documents)

            # Save vector store
            self.save_vector_store()

            # Add to registry
            registry_metadata = {
                "document_name": document_name,
                "file_type": file_type,
                "file_hash": file_hash,
                "file_path": str(file_path.absolute()),
                "ingestion_timestamp": ingestion_timestamp,
                "num_chunks": len(documents),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
            self.registry.add_document(document_id, registry_metadata)

            return True, f"Successfully ingested {document_name} ({len(documents)} chunks)"

        except Exception as e:
            logger.error(f"Error ingesting {file_path.name}: {str(e)}")
            return False, f"Error: {str(e)}"

    def ingest_directory(
        self,
        directory_path: Path,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        skip_duplicates: bool = True
    ) -> Dict[str, List[str]]:
        """
        Ingest all supported documents from a directory.

        Args:
            directory_path: Path to directory containing documents
            chunk_size: Chunk size for text splitting
            chunk_overlap: Overlap between chunks
            skip_duplicates: If True, skip documents that already exist

        Returns:
            Dictionary with 'success' and 'failed' lists of filenames
        """
        results = {"success": [], "failed": [], "skipped": []}

        if not directory_path.exists():
            logger.error(f"Directory not found: {directory_path}")
            return results

        # Find all supported files
        files = []
        for ext in SUPPORTED_FORMATS:
            files.extend(directory_path.glob(f"*{ext}"))

        if not files:
            logger.warning(f"No supported documents found in {directory_path}")
            return results

        logger.info(f"Found {len(files)} document(s) to ingest")

        # Ingest each file
        for file_path in files:
            success, message = self.ingest_document(
                file_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                skip_duplicates=skip_duplicates
            )

            if success:
                results["success"].append(file_path.name)
            elif "Duplicate" in message:
                results["skipped"].append(file_path.name)
            else:
                results["failed"].append(file_path.name)

            logger.info(f"{file_path.name}: {message}")

        return results

    def delete_document(self, document_id: str) -> Tuple[bool, str]:
        """
        Delete a document from the registry and rebuild the vector store.

        Note: FAISS does not support incremental deletion, so we rebuild the entire
        vector store from remaining documents.

        Args:
            document_id: Document ID to delete

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check if document exists
        doc_metadata = self.registry.get_document(document_id)
        if not doc_metadata:
            return False, f"Document not found: {document_id}"

        document_name = doc_metadata.get('document_name', 'Unknown')

        # Remove from registry
        self.registry.remove_document(document_id)

        # Rebuild vector store from remaining documents
        logger.info("Rebuilding vector store after deletion...")
        success, message = self.rebuild_vector_store()

        if success:
            return True, f"Deleted {document_name} and rebuilt vector store"
        else:
            return False, f"Deleted {document_name} from registry, but rebuild failed: {message}"

    def rebuild_vector_store(self) -> Tuple[bool, str]:
        """
        Rebuild the vector store from all documents in the registry.

        This method re-ingests all documents from their original file paths.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            documents_list = self.registry.list_documents()

            if not documents_list:
                # No documents, clear vector store
                if self.vector_store_path.exists():
                    import shutil
                    shutil.rmtree(self.vector_store_path)
                self.vector_store = None
                return True, "Vector store cleared (no documents)"

            all_documents = []

            # Re-load and chunk each document
            for doc_info in documents_list:
                file_path = Path(doc_info['file_path'])

                if not file_path.exists():
                    logger.warning(f"File not found, skipping: {file_path}")
                    continue

                documents = None

                # Phase 18: Try structured extraction for PDFs
                if doc_info['file_type'] == '.pdf':
                    structured_elements = load_pdf_structured(file_path)
                    if structured_elements:
                        documents = chunk_by_sections(
                            elements=structured_elements,
                            document_id=doc_info['document_id'],
                            document_name=doc_info['document_name'],
                            file_type=doc_info['file_type'],
                            ingestion_timestamp=doc_info['ingestion_timestamp'],
                        )
                        if documents:
                            logger.info(f"[PHASE18] Rebuilt {doc_info['document_name']} with section-based chunks")

                # Fallback: original text-based chunking
                if not documents:
                    text_content = load_document(file_path)
                    documents = chunk_document(
                        text=text_content,
                        document_id=doc_info['document_id'],
                        document_name=doc_info['document_name'],
                        file_type=doc_info['file_type'],
                        ingestion_timestamp=doc_info['ingestion_timestamp'],
                        chunk_size=doc_info.get('chunk_size', 500),
                        chunk_overlap=doc_info.get('chunk_overlap', 50)
                    )

                all_documents.extend(documents)

            # Rebuild vector store
            logger.info(f"Rebuilding vector store with {len(all_documents)} chunks from {len(documents_list)} documents")
            self.vector_store = FAISS.from_documents(all_documents, self.embeddings)
            self.save_vector_store()

            return True, f"Rebuilt vector store with {len(documents_list)} documents"

        except Exception as e:
            logger.error(f"Error rebuilding vector store: {str(e)}")
            return False, str(e)

    def list_documents(self) -> List[Dict]:
        """
        List all ingested documents.

        Returns:
            List of document metadata dictionaries
        """
        return self.registry.list_documents()

    def get_document_info(self, document_id: str) -> Optional[Dict]:
        """
        Get information about a specific document.

        Args:
            document_id: Document identifier

        Returns:
            Document metadata or None
        """
        return self.registry.get_document(document_id)
