# Campus RAG Chatbot - Phase 3

A complete RAG-based campus information chatbot with **document management system**, supporting PDF, DOCX, and TXT formats, conversation memory, and hallucination guardrails.

## Current Phase: Phase 3

### Phase 1 Features
- Python backend with LangChain
- Single document RAG
- Local FAISS vector store
- Basic source citation

### Phase 2 Features
- Multi-document retrieval
- Conversation memory (last 5 turns)
- Enhanced metadata tracking
- Hallucination guardrails
- Strict prompting

### Phase 3 Features (NEW)
- **Document Management System**: Admin functions for document lifecycle
- **Multi-Format Support**: PDF, DOCX, and TXT documents
- **Document Ingestion Pipeline**: Automated loading, chunking, embedding
- **Enhanced Metadata**: document_id, file_type, ingestion_timestamp
- **Duplicate Detection**: Prevents re-ingesting identical files
- **Incremental Indexing**: Add new documents without rebuilding from scratch
- **Admin CLI**: Command-line interface for document operations
- **Document Registry**: JSON-based tracking of all ingested documents

## Project Structure

```
campus_rag_chatbot/
├── main.py                      # Chat/RAG logic (Phase 3)
├── document_manager.py          # Document management system (NEW)
├── admin.py                     # Admin CLI interface (NEW)
├── demo_phase3.py               # Phase 3 demonstration script (NEW)
├── requirements.txt             # Updated with PDF/DOCX support
├── README.md                    # This file
├── .env.example                 # Environment variable template
├── .gitignore                   # Excludes generated files
├── data/
│   ├── campus_info.txt          # General campus information
│   ├── academic_programs.txt    # Academic programs and policies
│   └── events_activities.txt    # Campus events and activities
├── documents_to_ingest/         # Staging area for new documents (NEW)
│   ├── README.txt
│   ├── it_services.txt
│   └── student_employment.txt
├── document_registry.json       # Document metadata database (auto-generated)
└── vector_store/                # FAISS vector database (auto-generated)
```

## Prerequisites

- Python 3.8 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## Setup Instructions

### 1. Install Dependencies

```bash
cd campus_rag_chatbot
pip install -r requirements.txt
```

**New dependencies in Phase 3:**
- `pypdf` - PDF document loading
- `python-docx` - DOCX document loading
- `PyPDF2` - Fallback PDF loader
- `tabulate` - Pretty table formatting for admin CLI

### 2. Set Your OpenAI API Key

**Option A: Environment Variable**

```bash
# macOS/Linux
export OPENAI_API_KEY='your-api-key-here'

# Windows CMD
set OPENAI_API_KEY=your-api-key-here

# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Option B: .env File**

```bash
cp .env.example .env
# Edit .env and add your API key
```

### 3. Ingest Documents

Before running the chatbot, you need to ingest documents:

**Quick Start: Ingest sample documents**
```bash
python admin.py ingest documents_to_ingest/
```

**Or ingest the original Phase 1/2 documents:**
```bash
python admin.py ingest data/
```

### 4. Run the Chatbot

```bash
python main.py
```

**Or run the full Phase 3 demo:**
```bash
python demo_phase3.py
```

## Phase 3: Document Management

### Admin CLI Commands

The `admin.py` script provides administrative functions for managing documents.

#### List All Documents

```bash
python admin.py list
```

**Output:**
```
================================================================================
DOCUMENT REGISTRY
================================================================================

+----------------+-------------------------+-------+---------+---------------------+
| Document ID    | Filename                | Type  | Chunks  | Ingested            |
+================+=========================+=======+=========+=====================+
| abc123def...   | it_services.txt         | .txt  | 15      | 2025-01-04 10:30:22 |
| 456ghi789...   | student_employment.txt  | .txt  | 18      | 2025-01-04 10:30:23 |
| xyz890abc...   | campus_policy.pdf       | .pdf  | 25      | 2025-01-04 10:35:10 |
+----------------+-------------------------+-------+---------+---------------------+

Total documents: 3
```

#### Ingest Documents

**From default directory** (documents_to_ingest/):
```bash
python admin.py ingest
```

**From a specific file:**
```bash
python admin.py ingest path/to/document.pdf
```

**From a specific directory:**
```bash
python admin.py ingest path/to/documents/
```

**With custom chunk size:**
```bash
python admin.py ingest --chunk-size 1000 --chunk-overlap 100
```

**Allow duplicates** (re-ingest files):
```bash
python admin.py ingest --allow-duplicates
```

**Output:**
```
================================================================================
DOCUMENT INGESTION
================================================================================

Ingesting documents from directory: documents_to_ingest
--------------------------------------------------------------------------------

INGESTION SUMMARY
================================================================================
✓ Successfully ingested: 2 document(s)
⊘ Skipped (duplicates):  0 document(s)
✗ Failed:                0 document(s)

Successfully ingested:
  - it_services.txt
  - student_employment.txt
================================================================================
```

#### Show Document Details

```bash
python admin.py info abc123
```

**Output:**
```
================================================================================
DOCUMENT INFORMATION
================================================================================

Document Details:
  Document ID:         abc123def456ghi789
  Filename:            it_services.txt
  File Type:           .txt
  File Path:           /path/to/documents_to_ingest/it_services.txt
  Ingestion Time:      2025-01-04T10:30:22.123456
  Number of Chunks:    15
  Chunk Size:          500 characters
  Chunk Overlap:       50 characters
  File Hash:           a1b2c3d4e5f6g7h8...
================================================================================
```

#### Delete a Document

```bash
python admin.py delete abc123
```

**Output:**
```
================================================================================
DELETE DOCUMENT
================================================================================

Deleting document:
  ID:   abc123def456ghi789
  Name: it_services.txt
  Type: .txt

Are you sure you want to delete this document? (yes/no): yes

Deleting...
✓ Deleted it_services.txt and rebuilt vector store
================================================================================
```

**Note:** Deletion triggers a full vector store rebuild since FAISS doesn't support incremental deletion.

#### Rebuild Vector Store

```bash
python admin.py rebuild
```

Rebuilds the entire vector store from all documents in the registry. Useful if:
- The vector store becomes corrupted
- You want to re-index with different chunking parameters
- You manually edited the document registry

### Programmatic Usage

You can also use the admin functions programmatically:

```python
from admin import ingest_documents, list_documents, delete_document

# Ingest documents
results = ingest_documents(path="path/to/docs")

# List documents
docs = list_documents()

# Delete a document
success = delete_document("abc123")
```

## Document Ingestion Pipeline

### Supported Formats

- **TXT**: Plain text files
- **PDF**: PDF documents (via pypdf or PyPDF2)
- **DOCX**: Microsoft Word documents (via python-docx)

### How Ingestion Works

1. **File Validation**: Checks if file exists and format is supported
2. **Duplicate Detection**: Calculates SHA256 hash to prevent re-ingesting same content
3. **Document Loading**: Uses format-specific loader to extract text
4. **Chunking**: Splits text into ~500 character chunks with 50 character overlap
5. **Metadata Attachment**: Adds document_id, file_type, timestamp to each chunk
6. **Embedding**: Creates vector embeddings using OpenAI's embedding model
7. **Vector Store Update**: Adds embeddings to FAISS vector store incrementally
8. **Registry Update**: Saves document metadata to document_registry.json

### Document Metadata

Each chunk preserves the following metadata:

```python
{
    "document_id": "abc123...",           # Unique identifier
    "document_name": "it_services.txt",   # Original filename
    "file_type": ".txt",                  # File extension
    "ingestion_timestamp": "2025-01-04...", # ISO format timestamp
    "chunk_id": 5,                        # Chunk number (0-indexed)
    "total_chunks": 15,                   # Total chunks in document
    "section": "Network and Wi-Fi Access" # Extracted section header
}
```

This metadata is used for:
- **Source citations** in chatbot responses
- **Document management** (listing, deleting, tracking)
- **Debugging** (identifying which chunks were retrieved)

### Duplicate Detection

Documents are identified by their SHA256 hash. If you try to ingest a file with identical content:

```bash
python admin.py ingest document.pdf
# Output: ⊘ Duplicate: document.pdf already ingested on 2025-01-04 10:30:22
```

To force re-ingestion:
```bash
python admin.py ingest document.pdf --allow-duplicates
```

### Incremental vs. Full Rebuild

**Incremental Ingestion** (default):
- When you ingest new documents, they're added to the existing vector store
- Fast and efficient
- No need to rebuild from scratch

**Full Rebuild** (when needed):
- Use `python admin.py rebuild`
- Re-indexes all documents from the registry
- Required after deleting documents
- Useful if vector store becomes corrupted

## Running the Chatbot

### Basic Usage

```bash
python main.py
```

The chatbot will:
1. Load the vector store from disk
2. Display all ingested documents
3. Run a 5-turn example conversation
4. Show Phase 3 features and available commands

### Expected Output

```
================================================================================
Campus Information RAG Chatbot - Phase 3
Features: Document Management, Multi-format Support, Conversation Memory
================================================================================

Initializing document manager...
Loading vector store from: vector_store
Loaded vector store with 3 document(s)

Ingested documents:
  - it_services.txt (.txt, 15 chunks)
  - student_employment.txt (.txt, 18 chunks)
  - campus_info.txt (.txt, 20 chunks)

RAG system initialized with conversation memory (window size: 5 turns)

================================================================================
MULTI-TURN CONVERSATION EXAMPLE
Demonstrating conversation memory and follow-up questions
================================================================================

Turn 1
================================================================================
User: What IT services are available to students?
--------------------------------------------------------------------------------
Assistant: According to the Information Technology Services document...

Sources Used:

  From it_services.txt:
    - Section: Network and Wi-Fi Access (Chunk 0)
      Document ID: abc123def456... | Type: .txt
      Preview: All students receive network access credentials upon enrollment...
```

### Interactive Mode

Uncomment lines 304-324 in `main.py` to enable interactive mode:

```python
print("\nInteractive Mode")
print("Type 'quit' to exit, 'clear' to reset conversation memory")

turn = 1
while True:
    user_input = input("\nYou: ").strip()
    if user_input.lower() in ['quit', 'exit', 'q']:
        break
    elif user_input.lower() == 'clear':
        memory.clear()
        print("Conversation memory cleared.")
        turn = 1
        continue
    if user_input:
        ask_question(qa_chain, user_input, turn_number=turn)
        turn += 1
```

## Phase 3 Code Architecture

### Separation of Concerns

Phase 3 cleanly separates:

**Chat/RAG Logic** (`main.py`):
- Creates conversational QA chain
- Handles user questions
- Displays answers and sources

**Document Management** (`document_manager.py`):
- Document loading (PDF, DOCX, TXT)
- Chunking and metadata attachment
- Vector store operations
- Document registry management
- Duplicate detection

**Admin Interface** (`admin.py`):
- CLI commands for document operations
- Pretty table formatting
- User confirmations for destructive operations

### Key Classes

#### `DocumentRegistry`
- Manages document metadata in JSON format
- Tracks which documents have been ingested
- Prevents duplicates
- Provides listing and deletion

#### `DocumentManager`
- Main interface for document operations
- Handles vector store creation and loading
- Implements ingestion pipeline
- Provides rebuild functionality

### Ingestion Approaches

Phase 3 uses **incremental ingestion** by default:

```python
# First document creates vector store
self.vector_store = FAISS.from_documents(documents, self.embeddings)

# Subsequent documents are added incrementally
self.vector_store.add_documents(documents)
```

**Advantages:**
- Fast (no need to rebuild entire index)
- Preserves existing embeddings
- Allows continuous document addition

**Limitations:**
- FAISS doesn't support incremental deletion
- Deletion requires full rebuild

## Safety and Validation

### File Validation

```python
# Check file exists
if not file_path.exists():
    return False, f"File not found: {file_path}"

# Check format is supported
if file_path.suffix.lower() not in SUPPORTED_FORMATS:
    return False, f"Unsupported format: {file_path.suffix}"

# Check file is not empty
if not text_content.strip():
    return False, f"Document is empty: {document_name}"
```

### Error Handling

All document operations return `(success: bool, message: str)`:

```python
success, message = manager.ingest_document(file_path)
if success:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
```

### Logging

All operations are logged:

```python
logger.info(f"Ingesting document: {document_name}")
logger.info(f"Created {len(chunks)} chunks from {document_name}")
logger.error(f"Failed to load PDF {file_path.name}: {str(e)}")
```

Logs include:
- Document loading events
- Chunk creation
- Vector store operations
- Registry updates
- Errors and warnings

## Cost Estimate

**Initial Ingestion** (5 documents, ~100KB total):
- Embedding generation: ~$0.002
- Total: ~$0.002

**Chatbot Usage** (per conversation):
- 5-turn conversation: ~$0.02-$0.03
- Each additional question: ~$0.002

**Adding New Documents**:
- Per document (~20KB): ~$0.0004 (embedding only)

## Troubleshooting

### "No vector store found"

You need to ingest documents first:
```bash
python admin.py ingest data/
```

### "Unsupported file format"

Ensure your file is .txt, .pdf, or .docx. Check file extension.

### "PDF loader not available"

Install PDF dependencies:
```bash
pip install pypdf PyPDF2
```

### "DOCX loader not available"

Install DOCX dependency:
```bash
pip install python-docx
```

### "Duplicate document"

The file has already been ingested. To force re-ingestion:
```bash
python admin.py ingest path/to/file.pdf --allow-duplicates
```

### "File not found" during rebuild

A document in the registry was moved or deleted. Either:
1. Restore the file to its original location
2. Manually edit `document_registry.json` to remove the entry

### Vector store corrupted

Rebuild from scratch:
```bash
python admin.py rebuild
```

## What's NOT Included (Yet)

Phase 3 remains backend-only:

- ❌ Frontend web UI
- ❌ User authentication
- ❌ Database persistence (beyond JSON registry)
- ❌ Document upload via web interface
- ❌ Confidence scoring display
- ❌ OCR for scanned PDFs
- ❌ Session persistence across restarts

These features are planned for Phase 4.

## Key Differences from Phase 2

| Feature | Phase 2 | Phase 3 |
|---------|---------|---------|
| Document Formats | TXT only | TXT, PDF, DOCX |
| Document Loading | Direct file reading | Document manager |
| Metadata | Basic (source, section, chunk_id) | Enhanced (+ document_id, file_type, timestamp) |
| Ingestion | Manual, rebuild required | Automated pipeline, incremental |
| Duplicate Handling | None | SHA256 hash-based detection |
| Document Management | None | Full admin CLI |
| Document Tracking | None | JSON registry |
| Deletion | Not supported | Supported with rebuild |

## Example Workflows

### Adding a New PDF Document

```bash
# 1. Place PDF in documents_to_ingest/
cp ~/Documents/campus_policy.pdf documents_to_ingest/

# 2. Ingest the document
python admin.py ingest documents_to_ingest/campus_policy.pdf

# 3. Verify ingestion
python admin.py list

# 4. Test the chatbot
python main.py
```

### Removing Outdated Information

```bash
# 1. List documents to find the ID
python admin.py list

# 2. Delete the document
python admin.py delete abc123

# 3. Verify deletion
python admin.py list
```

### Bulk Ingestion

```bash
# Place all documents in a folder
mkdir new_docs
cp *.pdf *.docx *.txt new_docs/

# Ingest all at once
python admin.py ingest new_docs/

# Review results
python admin.py list
```

## Performance Considerations

### Chunk Size

Default: 500 characters with 50 character overlap

- **Smaller chunks** (300-400): Better precision, more granular citations
- **Larger chunks** (800-1000): Better context, fewer retrieval calls

### Retrieval Count

Default: Top 4 chunks with relevance threshold 0.5

- **More chunks** (k=6-8): Better recall, more context, higher cost
- **Fewer chunks** (k=2-3): Faster, cheaper, may miss relevant info

### Vector Store Size

- ~100 documents (~2MB text): Fast, instant retrieval
- ~1000 documents (~20MB text): Still fast, <1s retrieval
- ~10000+ documents: Consider specialized vector databases (Pinecone, Weaviate)

## Next Steps (Future Phases)

**Phase 4 (Planned):**
- Simple web frontend (Streamlit or Flask)
- Document upload interface
- Confidence scoring for answers
- OCR support for scanned PDFs
- Advanced search filters

**Phase 5 (Planned):**
- User authentication and sessions
- Database persistence (PostgreSQL)
- Analytics and usage tracking
- Role-based access control
- API endpoints for integration

## License

This is a prototype for educational purposes.

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the code comments in `document_manager.py` and `admin.py`
- Examine logs for error details

---

**Phase 3 Complete** - Document management system ready for production-like campus information kiosk deployment.
