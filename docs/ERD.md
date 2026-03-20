# CoCo System - Entity-Relationship Diagram

Entity-Relationship Diagram for the CoCo Campus RAG Chatbot system, covering both `WEB_APP` (runtime) and `INGESTION_MODULE` (document processing pipeline).

Only persistent, production-relevant entities are included. Runtime state, debug flags, and configuration-only data are excluded.

---

```mermaid
erDiagram

    %% ══════════════════════════════════════════════
    %% RAG / Knowledge Base
    %% ══════════════════════════════════════════════

    DOCUMENT {
        string document_id PK "MD5 hash of filename"
        string document_name
        string file_type "pdf | docx | txt"
        string file_hash "SHA256 content hash"
        string file_path
        string ingestion_timestamp "ISO 8601"
        int num_chunks
        int chunk_size "default 500"
        int chunk_overlap "default 50"
    }

    CHUNK {
        string docstore_id PK "UUID in FAISS docstore"
        int chunk_id "0-based per document, negative for synthetic"
        string document_id FK "links to DOCUMENT"
        string document_name
        string section
        string section_title
        string page_content "normalized text for embedding"
        string original_text "original text for display"
        bool is_synthetic "true for consolidated chunks"
        bool is_appendix
        string entity_type "deans | prayer | null"
        string element_types "Title, NarrativeText, etc"
        string page_numbers "list of page ints"
        int total_chunks
    }

    METADATA_INDEX_ENTRY {
        int chunk_id PK "matches CHUNK chunk_id"
        string docstore_id FK "UUID into FAISS docstore"
        int faiss_idx "positional index in FAISS"
        string section
        string section_title
        string pages "page number array"
        string document_id FK "links to DOCUMENT"
        string document_name
        bool is_synthetic
        bool is_appendix
        string entity_type "deans | prayer | null"
    }

    DOCUMENT ||--o{ CHUNK : "contains"
    CHUNK ||--|| METADATA_INDEX_ENTRY : "indexed as"

    %% ══════════════════════════════════════════════
    %% Conversation Logs
    %% ══════════════════════════════════════════════

    CONVERSATION_ENTRY {
        string query_id PK "YYYYMMDD_HHMMSS_microseconds"
        string timestamp "ISO 8601"
        string query "user question"
        string answer "system response"
        string feedback "true | false | null"
    }

    %% ══════════════════════════════════════════════
    %% FAQ
    %% ══════════════════════════════════════════════

    FAQ {
        string id PK "UUID v4"
        string question
        string answer "supports markdown"
        int display_order
        string created_at "ISO 8601"
        string updated_at "ISO 8601"
        string status "active | inactive"
    }

    %% ══════════════════════════════════════════════
    %% Advertisements
    %% ══════════════════════════════════════════════

    ADVERTISEMENT {
        string id PK "UUID v4"
        string ad_type "image | text"
        string uploaded_at "ISO 8601"
        string status "active | inactive"
        int display_order
        string filename "null for text ads"
        string original_name "null for text ads"
        string mime_type "image/jpeg | image/png | null"
        int file_size "bytes, null for text ads"
        string content "text ad body, null for image ads"
    }

    %% ══════════════════════════════════════════════
    %% Trivia, Study Tips, Quotes
    %% ══════════════════════════════════════════════

    TRIVIA_CONTENT {
        string month_year PK "YYYY-MM composite key"
        int month
        int year
        string seed "8-char MD5 prefix"
        string generated_at "ISO 8601"
        int days_in_month
        string trivia "day-number keyed map"
        string study_tips "day-number keyed map"
        string quotes "array of strings"
    }

    %% ══════════════════════════════════════════════
    %% Voice - STT Usage Tracking
    %% ══════════════════════════════════════════════

    STT_USAGE {
        string current_month PK "YYYY-MM"
        int used_seconds "rounded up per Google billing"
        int quota_seconds "default 3600"
        int transcription_count
        string last_updated "ISO 8601"
    }

    STT_USAGE_HISTORY {
        string month PK "YYYY-MM"
        int used_seconds
        int transcription_count
    }

    STT_USAGE ||--o{ STT_USAGE_HISTORY : "archives to"

    %% ══════════════════════════════════════════════
    %% Credentials & External Services
    %% ══════════════════════════════════════════════

    CREDENTIAL {
        string credential_id PK "e.g. openai_api_key"
        string value "AES-256-GCM encrypted"
        string credential_type "api_key | service_account_json"
        string updated_at "ISO 8601"
        string updated_by "admin"
    }

    OPENAI_API {
        string service_name PK "openai"
        string api_endpoint "api.openai.com"
        string model "gpt-4o-mini"
        string embedding_model "text-embedding-ada-002"
    }

    GOOGLE_CLOUD_STT {
        string service_name PK "google-cloud-stt"
        string api_endpoint "speech.googleapis.com"
        string model "default"
        string language_code "en-US"
        bool data_logging_disabled "true - privacy safe"
    }

    CREDENTIAL }o--|| OPENAI_API : "authenticates"
    CREDENTIAL }o--|| GOOGLE_CLOUD_STT : "authenticates"
    STT_USAGE }o--|| GOOGLE_CLOUD_STT : "tracks usage of"

    %% ══════════════════════════════════════════════
    %% Cross-Domain Relationships
    %% ══════════════════════════════════════════════

    CHUNK }o--|| OPENAI_API : "embedded via"
    CONVERSATION_ENTRY }o--|| OPENAI_API : "generated via"
```

---

## Storage Formats

| Entity | File | Format | Location |
|--------|------|--------|----------|
| DOCUMENT | `document_registry.json` | JSON (keyed by document_id) | `modules/` |
| CHUNK | `index.faiss` + `index.pkl` | FAISS binary + Pickle | `modules/vector_store/` |
| METADATA_INDEX_ENTRY | `metadata_index.json` | JSON (5 secondary indexes) | `modules/data/` |
| CONVERSATION_ENTRY | `conversations.jsonl` | JSONL (one record per line) | `modules/logs/` |
| FAQ | `faq_data.json` | JSON (array under `faqs` key) | `modules/data/` |
| ADVERTISEMENT | `advertisement_registry.json` | JSON (array under `advertisements` key) | `modules/data/` |
| ADVERTISEMENT images | `ad_*.jpg/png` | Binary image files | `modules/data/advertisements/` |
| TRIVIA_CONTENT | `trivia_content.json` | JSON (regenerated monthly) | `modules/data/` |
| STT_USAGE | `stt_usage.json` | JSON (single record + history array) | `modules/data/` |
| CREDENTIAL | `credentials.enc` | AES-256-GCM encrypted binary | `modules/data/` |

## Notes

### Identifiers

- **DOCUMENT**: `document_id` is an MD5 hash of the filename. Duplicate detection uses `file_hash` (SHA256 of content).
- **CHUNK**: Each chunk has two IDs — `docstore_id` (UUID, internal to FAISS) and `chunk_id` (integer, sequential per document). Synthetic chunks use negative IDs (`-1` for deans, `-2` for prayer).
- **CONVERSATION_ENTRY**: `query_id` is a timestamp-based composite (`YYYYMMDD_HHMMSS_microseconds`), not a UUID. Feedback is stored inline as a nullable boolean.
- **METADATA_INDEX_ENTRY**: Provides O(1) lookups into the FAISS docstore via 5 secondary indexes (`by_chunk_id`, `by_section`, `by_section_title`, `by_page`, `by_document`).

### External Services

- **OPENAI_API**: Used for both LLM inference (GPT-4o-mini) and embedding generation (text-embedding-ada-002). All chunks are embedded through this service during ingestion.
- **GOOGLE_CLOUD_STT**: Speech-to-text with data logging disabled at the project level in Google Cloud Console. Usage tracked against a 60-minute monthly quota.
- **CREDENTIAL**: Stores API keys and service account JSON encrypted with AES-256-GCM, derived from the admin password via PBKDF2.

### Data Retention

- **CONVERSATION_ENTRY**: Retains current + previous calendar month; older entries archived.
- **STT_USAGE_HISTORY**: Retains last 12 months of archived usage.
- **TRIVIA_CONTENT**: Regenerated on the 1st of each month using a deterministic seed for LLM variation.

---

## Suggested Improvements

These are observations only — the ERD above reflects the current implementation.

1. **CONVERSATION_ENTRY lacks a session_id field**: Conversations are logged individually with no link back to the session that produced them. Adding `session_id` would enable session-level analytics (e.g., average turns per session, drop-off analysis).

2. **FAQ has no category/tag field**: All FAQs are in a flat list. A `category` field would support grouped display and filtered retrieval as the FAQ count grows.

3. **ADVERTISEMENT image storage is file-based**: Image files are stored on disk alongside JSON metadata. A `file_checksum` field would enable integrity validation and deduplication.
