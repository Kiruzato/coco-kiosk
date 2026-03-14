# Architecture Overview — INGESTION_MODULE

This document describes the architecture of the CoCo INGESTION_MODULE — a standalone document processing pipeline that converts raw documents (PDF, DOCX, TXT) into embeddings and produces deployment-ready RAG packages for the CoCo campus chatbot. It reflects the current implementation as verified in the codebase.

---

## 1. Project Structure

This section provides a high-level overview of the INGESTION_MODULE directory and file structure, organized by functional area.

```
INGESTION_MODULE/
├── ingest.py                           # CLI entry point — standalone ingestion pipeline
├── gui.py                              # Desktop GUI application (tkinter)
├── requirements.txt                    # Ingestion-specific Python dependencies
├── README.md                           # Usage and deployment documentation
├── setup.ps1                           # Windows setup script
├── ingestion_config.json               # Persisted GUI configuration (API key, last folder)
├── .env                                # Environment variables (OPENAI_API_KEY)
├── .env.example                        # Template for .env configuration
├── documents_to_ingest/                # Default input folder for source documents
│
├── modules/
│   ├── __init__.py                     # Python package marker
│   ├── config.py                       # Configuration constants (chunk size, overlap, paths)
│   ├── document_manager.py             # Core pipeline: loading, chunking, embedding, storage
│   ├── consolidation_engine.py         # Config-driven entity consolidation (synthetic chunks)
│   ├── metadata_index.py              # O(1) chunk metadata lookups (secondary indexes)
│   ├── text_normalizer.py             # Text normalization for embedding consistency
│   ├── text_normalizer_pipeline.py    # Multi-stage PDF text cleaning pipeline
│   ├── admin.py                        # CLI admin interface (list, delete, rebuild)
│   │
│   ├── data/
│   │   ├── consolidation_rules.json    # Entity consolidation rule definitions
│   │   └── metadata_index.json         # Persisted chunk metadata index
│   │
│   └── vector_store/                   # Output: FAISS index (created during ingestion)
│       ├── index.faiss                 # FAISS vector database (IndexFlatL2)
│       └── index.pkl                   # FAISS docstore metadata (pickled)
│
└── document_registry.json              # Persistent document metadata registry
```

---

## 2. High-Level System Diagram

The INGESTION_MODULE operates as a preprocessing stage that runs independently from the runtime WEB_APP. Documents are processed on a development machine, and the resulting RAG package is deployed to the kiosk.

```
                        INGESTION_MODULE (Development Machine)
                        ======================================

┌─────────────────┐     ┌──────────────────────────────────────────────────────┐
│  Source Documents│     │                 Ingestion Pipeline                   │
│  (PDF/DOCX/TXT) │────▶│                                                      │
└─────────────────┘     │  1. Document Loading (pypdf / unstructured / docx)    │
                        │  2. Text Normalization Pipeline (5-stage cleaning)    │
                        │  3. Element Grouping & Section Merging               │
                        │  4. Chunking (layout-aware or linear fallback)       │
                        │  5. Consolidation Engine (synthetic chunk creation)  │
                        │  6. Metadata Validation & Logging                    │
                        │  7. Embedding Generation (OpenAI text-embedding)     │
                        │  8. FAISS Vector Store Creation                      │
                        │  9. Metadata Index Build (secondary indexes)         │
                        │ 10. RAG Package Assembly (ZIP archive)               │
                        └──────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────────────┐
                        │               RAG Package (.zip)                     │
                        │  ├── vector_store/                                   │
                        │  │   ├── index.faiss                                 │
                        │  │   └── index.pkl                                   │
                        │  └── document_registry.json                          │
                        └──────────────────────┬───────────────────────────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                   Admin UI Upload        SCP Transfer         Git Commit
                   (Recommended)          (Manual)             (Version Control)
                          │                    │                    │
                          └────────────────────┼────────────────────┘
                                               ▼
                        ┌──────────────────────────────────────────────────────┐
                        │           WEB_APP Runtime (Raspberry Pi 5)           │
                        │  Loads pre-built vector store — no re-embedding      │
                        └──────────────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1. CLI Entry Point

**Name:** `ingest.py` — Standalone Ingestion Runner

**Description:** The main command-line entry point for document ingestion. Accepts a documents folder path, orchestrates the full pipeline, and produces a timestamped RAG package containing the FAISS index, docstore metadata, and document registry.

**Technologies:** Python, argparse

**Key Behavior:**
- Validates the input folder and counts supported documents
- Excludes previous `rag_package_*` folders from processing
- Creates timestamped output: `rag_package_YYYY-MM-DD_HH-MM/`
- Validates output against required files (`index.faiss`, `index.pkl`)
- Produces a ZIP archive for deployment via the Admin UI

**Usage:**
```bash
python ingest.py <path_to_documents_folder>
python ingest.py                          # Uses default: documents_to_ingest/
```

**Output Structure:**
```
documents_folder/
└── rag_package_YYYY-MM-DD_HH-MM/
    ├── vector_store/
    │   ├── index.faiss
    │   └── index.pkl
    ├── document_registry.json
    └── rag_package_YYYY-MM-DD_HH-MM.zip
```

---

### 3.2. Desktop GUI

**Name:** `gui.py` — Ingestion Configuration GUI

**Description:** A tkinter-based desktop interface for configuring and running ingestion without the command line. Provides API key management, folder selection, progress tracking, and real-time status logging.

**Technologies:** Python tkinter, threading

**Sections:**
1. **API Key Configuration** — Input field with show/hide toggle and verify button (tests against OpenAI API)
2. **Document Folder Selection** — Browse dialog with document count display
3. **Ingestion Controls** — Start button with progress bar
4. **Status Display** — Scrollable log area with real-time updates

**Persistence:** Saves configuration (API key, last folder) to `ingestion_config.json`.

---

### 3.3. Document Manager

**Name:** `document_manager.py` — Core Ingestion Pipeline

**Description:** The central processing engine responsible for document loading, chunking, embedding generation, and vector store management. Contains both the `DocumentRegistry` class (persistent document metadata) and the `DocumentManager` class (full pipeline orchestration).

**Technologies:** LangChain, OpenAI Embeddings, FAISS, pypdf, python-docx, unstructured

#### 3.3.1. DocumentRegistry

Manages a JSON-based registry of all ingested documents. Tracks document identity (SHA256 hash for duplicate detection), ingestion metadata (timestamp, chunk count, chunk parameters), and file provenance.

**Registry Entry Schema:**
```json
{
  "document_name": "Campus_Info.pdf",
  "file_type": ".pdf",
  "file_hash": "sha256:a1b2c3...",
  "file_path": "/path/to/original/file",
  "ingestion_timestamp": "2026-03-14T10:30:00",
  "num_chunks": 120,
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `add_document(document_id, metadata)` | Register a newly ingested document |
| `remove_document(document_id)` | Unregister a document |
| `document_exists(file_hash)` | Duplicate detection by SHA256 hash |
| `list_documents()` | Return all registered document entries |

#### 3.3.2. DocumentManager

Orchestrates the full ingestion pipeline from raw files to vector store.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `ingest_document(file_path)` | Process a single file through the complete pipeline |
| `ingest_directory(dir_path)` | Process all supported files in a directory |
| `load_vector_store()` | Load existing FAISS index from disk |
| `save_vector_store()` | Persist FAISS index to disk |
| `delete_document(document_id)` | Remove a document from the vector store and registry |
| `rebuild_vector_store()` | Re-process all registered documents from source files |

---

### 3.4. Text Normalization Pipeline

**Name:** `text_normalizer_pipeline.py` — Multi-Stage PDF Text Cleaning

**Description:** A deterministic 5-stage preprocessing pipeline that cleans text extracted from PDF documents before chunking. Addresses common issues from PDF parsing: whitespace fragmentation, OCR artifacts, and inconsistent person entry formatting. Runs only on layout-aware PDF elements.

**Technologies:** Python regex

**Pipeline Stages:**

| Stage | Function | Purpose |
|-------|----------|---------|
| 1. Whitespace Normalization | `_normalize_element_whitespace()` | Collapse excessive spaces, normalize line breaks |
| 2. Line Reassembly | `_reassemble_fragmented_lines()` | Merge fragmented person titles across elements (e.g., "Dr." + "Smith") |
| 3. OCR Artifact Removal | `_remove_ocr_artifacts()` | Fix common OCR errors ("CHARPERSON" → "CHAIRPERSON"), remove Unicode private-use characters, normalize diacritics |
| 4. Person Entry Normalization | `_normalize_person_entries()` | Standardize professional titles ("DR." → "Dr."), clean college name formatting |
| 5. Entity Block Cleanup | `_clean_entity_blocks()` | Remove interspersed headers from enumeration blocks |

---

### 3.5. Text Normalizer

**Name:** `text_normalizer.py` — Embedding-Level Text Normalization

**Description:** Provides text normalization for consistent embedding generation and retrieval. All text is normalized before embedding to ensure queries and chunks occupy the same semantic space.

**Technologies:** Python `unicodedata`

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `normalize_text(text)` | NFKC Unicode normalization → lowercase → collapse whitespace → strip |
| `normalize_for_display(text)` | NFKC + collapse whitespace (preserves case) |
| `canonicalize_directory_query(text)` | Transform "where is X" → "X location" for semantic alignment |

---

### 3.6. Consolidation Engine

**Name:** `consolidation_engine.py` — Config-Driven Entity Consolidation

**Description:** Creates synthetic chunks by combining related content that is scattered across multiple chunks in the source document. Uses JSON-configured rules to identify and merge related content, ensuring enumeration queries (e.g., "Who are the deans?") retrieve complete answers.

**Technologies:** Python regex, JSON configuration

**Pattern Types:**

| Pattern | Description | Example |
|---------|-------------|---------|
| `semantic` | Matches chunks containing BOTH required patterns AND anchor patterns | Deans: required="dean" + anchors=["Dr.", "Engr.", "Prof."] |
| `anchor_continuation` | Finds an anchor chunk, then collects continuations by proximity | Prayer: anchor="prayer to st. columban" + max_distance=3 chunks |

**Built-In Rules (from `consolidation_rules.json`):**

| Rule | Entity Type | Chunk ID | Phase | Pattern |
|------|-------------|----------|-------|---------|
| Deans | `deans` | -1 | 18 | semantic |
| Prayer | `prayer` | -2 | 21.1 | anchor_continuation |

**Synthetic Chunk Metadata:**
```json
{
  "chunk_id": -1,
  "section": "deans",
  "is_synthetic": true,
  "entity_type": "deans",
  "source_chunk_ids": [12, 15, 18, 21],
  "consolidation_phase": "24",
  "element_types": ["Synthetic"]
}
```

Synthetic chunks use negative IDs (-1, -2) to distinguish them from natural chunks. They are prepended to the document list before embedding.

---

### 3.7. Metadata Index

**Name:** `metadata_index.py` — Fast Chunk Metadata Lookups

**Description:** Builds and maintains secondary indexes over the FAISS docstore to enable O(1) chunk metadata lookups without iterating the entire store. Supports filtering by section, page, document, and special chunk categories (synthetic, appendix).

**Technologies:** Python dict-based indexes, JSON persistence

**Index Structure:**

| Index | Key → Value | Purpose |
|-------|-------------|---------|
| `by_chunk_id` | chunk_id → {docstore_id, section, pages, ...} | Primary lookup |
| `by_section` | section_name → [chunk_ids] | Section filtering |
| `by_section_title` | title → [chunk_ids] | Title-based filtering |
| `by_page` | page_number → [chunk_ids] | Page-based filtering |
| `by_document` | document_id → [chunk_ids] | Document-scoped queries |
| `synthetic_chunks` | [chunk_ids] | All synthetic chunk IDs |
| `appendix_chunks` | [chunk_ids] | All appendix chunk IDs |

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `build_from_vector_store(vector_store)` | Build all indexes from FAISS docstore (single iteration) |
| `get_adjacent_chunk_ids(chunk_id, window)` | Get neighboring chunks for context expansion |
| `get_chunks_by_section(section)` | Filter chunks by section name |
| `get_stats()` | Return index statistics (total chunks, sections, pages) |

---

### 3.8. CLI Admin Interface

**Name:** `admin.py` — Command-Line Document Management

**Description:** Provides CLI-based document management for listing, inspecting, deleting, and rebuilding the vector store without the GUI.

**Commands:**

| Command | Purpose |
|---------|---------|
| `python admin.py list` | Display all registered documents in table format |
| `python admin.py info <doc_id>` | Show detailed metadata for one document |
| `python admin.py delete <doc_id>` | Remove document from registry and vector store |
| `python admin.py rebuild` | Rebuild the entire vector store from source files |
| `python admin.py ingest <path>` | Ingest new documents from a path |

---

## 4. Processing Pipeline

This section describes the complete ingestion pipeline — the sequence of transformations applied to raw documents to produce a deployable RAG package.

### 4.1. Pipeline Overview

```
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
│  1. Loading  │──▶│ 2. Normalize │──▶│  3. Grouping  │──▶│ 4. Chunking  │
│  (PDF/DOCX/  │   │  (5-stage    │   │  (sections,   │   │  (element or │
│   TXT)       │   │   pipeline)  │   │   appendices) │   │   linear)    │
└─────────────┘   └──────────────┘   └───────────────┘   └──────┬───────┘
                                                                 │
┌─────────────┐   ┌──────────────┐   ┌───────────────┐          │
│ 7. Package  │◀──│ 6. Embedding │◀──│ 5. Consolidat │◀─────────┘
│  (ZIP)      │   │  (OpenAI)    │   │    ion        │
└─────────────┘   └──────────────┘   └───────────────┘
```

### 4.2. Stage 1 — Document Loading

The pipeline supports three document formats, each with a dedicated loader:

| Format | Loader | Library | Strategy |
|--------|--------|---------|----------|
| **PDF** | `load_pdf_document_layout_aware()` | `unstructured` (`partition_pdf`, strategy="fast") | Structured element extraction with type preservation (Title, NarrativeText, ListItem, Table) |
| **PDF (fallback)** | `load_pdf_document()` | `pypdf` | Linear page-by-page text extraction |
| **DOCX** | `load_docx_document()` | `python-docx` | Paragraph-level text extraction |
| **TXT** | `load_txt_document()` | Built-in | UTF-8 file read |

**Duplicate Detection:** Before loading, the file's SHA256 hash is computed and checked against the document registry. Previously ingested files are skipped.

### 4.3. Stage 2 — Text Normalization

For layout-aware PDF elements, the 5-stage text normalization pipeline (`text_normalizer_pipeline.py`) cleans extracted text:

1. **Whitespace normalization** — Collapse excessive spaces, normalize line breaks
2. **Line reassembly** — Merge fragmented person titles (e.g., "Dr." on one line + "Smith" on next)
3. **OCR artifact removal** — Fix common errors ("CHARPERSON" → "CHAIRPERSON"), remove private-use Unicode characters
4. **Person entry normalization** — Standardize professional titles ("DR." → "Dr."), clean formatting
5. **Entity block cleanup** — Remove interspersed headers from enumeration blocks

For TXT and DOCX files, only embedding-level normalization (`normalize_text()`) is applied: NFKC Unicode normalization, lowercase conversion, and whitespace collapsing.

### 4.4. Stage 3 — Element Grouping and Section Merging

Layout-aware PDF elements are organized into logical sections:

1. **`group_elements_by_section()`** — Groups elements by Title boundaries. Each section receives metadata: section title, element types, page numbers, and appendix flags.

2. **`merge_related_admin_sections()`** — Merges related sections with hard boundary rules:
   - **Hard boundaries:** Enumeration groups (Deans, Directors, Vice Presidents, Chairs) are never mixed across sections
   - **Appendix isolation:** Appendix sections (detected by pattern matching: "Appendix A", "Prayer to St. Columban", "Columban Hymn") are isolated and appended at the end
   - **Page proximity clustering:** Sections within 3 pages are grouped as belonging to the same logical block
   - **Deterministic ordering:** Title elements → Person elements → Supporting text

### 4.5. Stage 4 — Chunking

Two chunking strategies are used depending on the document format and parsing result:

#### Layout-Aware Chunking (PDFs with structured elements)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Regular section max size | 800 characters | Element-boundary splitting |
| Appendix section max size | 2000 characters | Larger to keep appendix content intact |
| Overlap | None | Element boundaries prevent overlap |

**Logic:** If a section fits within the max size, it becomes a single chunk. If it exceeds the max size, it is split at element boundaries (preserving lists and tables as atomic units).

#### Linear Chunking (TXT, DOCX, and PDF fallback)

| Parameter | Value |
|-----------|-------|
| Chunk size | 500 characters (configurable via `config.py`) |
| Chunk overlap | 50 characters (configurable via `config.py`) |
| Separator hierarchy | `["\n\n", "\n", ". ", " ", ""]` |
| Splitter | LangChain `RecursiveCharacterTextSplitter` |

**Chunk Metadata:** Every chunk receives metadata including `document_id`, `document_name`, `file_type`, `chunk_id`, `section`, `section_title`, `element_types`, and `page_numbers`.

### 4.6. Stage 5 — Consolidation

The consolidation engine (`consolidation_engine.py`) creates synthetic chunks by combining related content scattered across multiple natural chunks. Rules are defined in `consolidation_rules.json`.

**Current Rules:**

1. **Deans** (semantic pattern) — Identifies all chunks containing dean information (pattern: "dean" + professional title anchors), combines them into a single synthetic chunk (chunk_id = -1)

2. **Prayer** (anchor_continuation pattern) — Finds the chunk containing "prayer to st. columban", then collects continuation chunks within a proximity window of 3 chunks (chunk_id = -2)

Synthetic chunks are prepended to the document list before embedding, ensuring they appear in retrieval results for relevant queries.

### 4.7. Stage 6 — Embedding Generation

| Parameter | Value |
|-----------|-------|
| Model | OpenAI `text-embedding-3-small` |
| Dimensions | 1536 |
| Input | Normalized chunk text (NFKC + lowercase) |
| Method | LangChain `OpenAIEmbeddings` |

Chunks are embedded and added to the FAISS vector store. If a store already exists, new documents are added incrementally. Otherwise, a new store is created with `FAISS.from_documents()`.

### 4.8. Stage 7 — Metadata Validation

After chunking and before embedding, all chunk metadata is validated:

- **Required field presence:** `document_id`, `document_name`, `file_type`, `chunk_id`, `section`, `original_text`
- **Type checking:** Page numbers must be integers, element types must be strings
- **Suspicious value detection:** Warns if section is "General Information" (indicates extraction failure)
- **Statistics logging:** Chunk size distribution (avg, min, max), synthetic/appendix counts, section inventory

### 4.9. Stage 8 — Vector Store and Index

| Component | Format | Purpose |
|-----------|--------|---------|
| `index.faiss` | FAISS IndexFlatL2 | Brute-force L2 distance vector index |
| `index.pkl` | Python pickle | LangChain docstore (chunk text + metadata) |
| `document_registry.json` | JSON | Document provenance and ingestion metadata |
| `metadata_index.json` | JSON | Secondary indexes for O(1) chunk lookups |

The metadata index is rebuilt after every ingestion by iterating the FAISS docstore once and constructing lookup tables by chunk_id, section, page, and document.

### 4.10. Stage 9 — RAG Package Assembly

The final output is a timestamped RAG package:

```
rag_package_YYYY-MM-DD_HH-MM/
├── vector_store/
│   ├── index.faiss          # FAISS vector database
│   └── index.pkl            # Docstore metadata
├── document_registry.json   # Document provenance
└── rag_package_YYYY-MM-DD_HH-MM.zip   # Deployment archive
```

The ZIP archive is designed for upload through the WEB_APP Admin UI at `/admin` → RAG Package section.

---

## 5. Data Stores

### 5.1. FAISS Vector Store

**Type:** FAISS IndexFlatL2 (brute-force exact nearest neighbor)

**Purpose:** Stores embedded document chunks for semantic similarity search at runtime.

**Files:**
- `index.faiss` — Binary FAISS index containing 1536-dimensional vectors
- `index.pkl` — Pickled LangChain docstore mapping docstore UUIDs to Document objects (text + metadata)

**Typical Size:** ~2-5 MB for 500-700 chunks across 4-8 documents.

### 5.2. Document Registry

**Type:** JSON file (`document_registry.json`)

**Purpose:** Persistent record of all ingested documents with provenance metadata. Enables duplicate detection (SHA256 hash) and document-level management (delete, list, info).

### 5.3. Metadata Index

**Type:** JSON file (`metadata_index.json`)

**Purpose:** Secondary indexes built from the FAISS docstore to support O(1) chunk lookups by section, page, document, and special categories. Eliminates the need to iterate the entire docstore for filtered queries.

### 5.4. Consolidation Rules

**Type:** JSON file (`consolidation_rules.json`)

**Purpose:** Defines entity consolidation rules for synthetic chunk creation. Each rule specifies a pattern type, matching criteria, content configuration, and output format.

---

## 6. External Integrations

### 6.1. OpenAI API

**Purpose:** Embedding generation for document chunks

**Integration Method:** LangChain `OpenAIEmbeddings` wrapper

**Model:** `text-embedding-3-small` (1536 dimensions)

**Configuration:** API key loaded from `.env` file (`OPENAI_API_KEY`)

**Usage:** Called during ingestion only — the runtime WEB_APP uses the pre-built FAISS index without re-embedding.

### 6.2. Unstructured Library

**Purpose:** Layout-aware PDF parsing with element type detection

**Integration Method:** Python library (`unstructured[pdf]`)

**Strategy:** `"fast"` — Rule-based parsing without OCR. Suitable for digitally-created campus documents (not scanned images).

**Element Types Extracted:** Title, NarrativeText, ListItem, Table, Header, Footer

---

## 7. Deployment and Infrastructure

### 7.1. Runtime Environment

| Aspect | Detail |
|--------|--------|
| **Platform** | Windows (development), Linux (RPi deployment of WEB_APP) |
| **Python Version** | 3.11 (required for Piper TTS compatibility in WEB_APP) |
| **Dependencies** | 12 packages (ingestion-specific, no web/voice dependencies) |
| **Setup** | `setup.ps1` (Windows) or manual `pip install -r requirements.txt` |

### 7.2. Deployment Workflow

The INGESTION_MODULE runs on the development machine. The resulting RAG package is deployed to the Raspberry Pi via one of three methods:

| Method | Steps | Recommended |
|--------|-------|-------------|
| **Admin UI Upload** | Upload ZIP at `/admin` → RAG Package | Yes |
| **SCP Transfer** | Copy `vector_store/` to RPi via SCP | Manual |
| **Git Commit** | Commit vector store files, pull on RPi | Version-controlled |

The RPi runs in **runtime-only mode** — it loads the pre-built FAISS index without performing document ingestion. Ingestion packages (`unstructured`, `pypdf`, `python-docx`) are excluded from RPi dependencies.

### 7.3. File Synchronization

Several files are intentionally duplicated between INGESTION_MODULE and WEB_APP to maintain strict architectural isolation (no cross-imports):

| File | Purpose |
|------|---------|
| `document_manager.py` | Document loading, chunking, registry management |
| `consolidation_engine.py` | Synthetic chunk creation |
| `metadata_index.py` | Metadata index building |
| `text_normalizer.py` | Text normalization functions |
| `text_normalizer_pipeline.py` | PDF text cleaning pipeline |

Changes to any of these files must be manually mirrored between both locations. Neither module imports from the other.

---

## 8. Security Considerations

### 8.1. API Key Management

- OpenAI API key stored in `.env` file (gitignored)
- GUI persists API key to `ingestion_config.json` (local only)
- Key verified via API call before ingestion begins

### 8.2. File Processing

- SHA256 hashing for duplicate detection (no file content stored in registry)
- Source file paths recorded in registry for provenance — file paths from the ingestion machine may not exist on the deployment target
- No user-supplied code execution — all processing is deterministic regex and library calls

### 8.3. Vector Store

- FAISS index contains embedded vectors and chunk text (no raw source files)
- Pickle files (`index.pkl`) loaded only from trusted local paths
- No authentication on vector store files — security relies on file system permissions

---

## 9. Development Notes

### 9.1. Adding New Document Formats

1. Implement a loader function in `document_manager.py` (e.g., `load_xlsx_document()`)
2. Add the extension to `SUPPORTED_FORMATS`
3. Register the loader in `load_document()` dispatcher
4. Mirror changes to WEB_APP's `document_manager.py`

### 9.2. Adding New Consolidation Rules

1. Add a rule definition to `consolidation_rules.json`
2. Choose pattern type: `semantic` (keyword matching) or `anchor_continuation` (proximity-based)
3. Assign a unique negative `chunk_id` (e.g., -3)
4. Re-run ingestion to generate updated synthetic chunks
5. No code changes required — the engine dispatches by `pattern_type`

### 9.3. Configuration

| Parameter | Default | File | Purpose |
|-----------|---------|------|---------|
| `DEFAULT_CHUNK_SIZE` | 500 | `config.py` | Character limit for linear chunking |
| `DEFAULT_CHUNK_OVERLAP` | 50 | `config.py` | Overlap between linear chunks |
| Layout-aware max size | 800 | `document_manager.py` | Max section size before element-boundary splitting |
| Appendix max size | 2000 | `document_manager.py` | Larger limit for appendix sections |
| Page proximity threshold | 3 pages | `document_manager.py` | Clustering distance for section merging |

---

## 10. Project Identification

| Field | Value |
|-------|-------|
| **Project Name** | CoCo — Columban College Information Kiosk |
| **Module** | INGESTION_MODULE |
| **Repository** | (Private repository) |
| **Primary Contact** | CoCo Development Team |
| **Date of Last Update** | 2026-03-14 |

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation — architecture that retrieves relevant documents before generating LLM responses |
| **FAISS** | Facebook AI Similarity Search — library for efficient similarity search on dense vectors |
| **FAISS IndexFlatL2** | Brute-force L2 (Euclidean) distance search index — exact nearest neighbor lookup |
| **Chunk** | A segment of document text with associated metadata, stored as a vector in the FAISS index |
| **Synthetic Chunk** | A consolidation-generated chunk combining related content from multiple natural chunks (negative chunk_id) |
| **Docstore** | LangChain's in-memory document store mapping UUIDs to Document objects (text + metadata) |
| **Layout-Aware Parsing** | PDF processing that preserves document structure (titles, lists, tables) rather than extracting flat text |
| **Element** | A structural unit extracted from a PDF by the `unstructured` library (e.g., Title, NarrativeText, ListItem) |
| **NFKC** | Unicode Normalization Form KC — canonical decomposition followed by compatibility composition |
| **Consolidation Rule** | A JSON-defined pattern specifying how to identify and merge related chunks into a synthetic chunk |
| **RAG Package** | A deployment-ready ZIP archive containing the FAISS index, docstore, and document registry |
| **Document Registry** | JSON file tracking all ingested documents with provenance metadata and SHA256 hashes |
| **Metadata Index** | Secondary lookup indexes (by section, page, document) built from the FAISS docstore for O(1) access |
| **Text Normalization Pipeline** | 5-stage deterministic preprocessing that cleans PDF-extracted text before chunking |
| **Hard Boundary** | A section merging constraint that prevents mixing content from different enumeration groups (e.g., Deans vs Directors) |
| **RPi** | Raspberry Pi — single-board ARM computer used as kiosk deployment target |
