# CoCo - Campus RAG Chatbot

## Project Overview

CoCo (Columban College Information Kiosk) is a RAG-based campus information chatbot built for deployment on a Raspberry Pi 5. It provides students with accurate information about campus locations, services, academic programs, and events.

## Current State

**Completed through Phase 9** - Entity-anchored directory retrieval

### Phase History
1. **Phase 1-3**: Core RAG pipeline, document management, multi-format support
2. **Phase 4**: Web frontend (FastAPI + static HTML/JS/CSS)
3. **Phase 5**: Confidence scoring system
4. **Phase 6**: Dual-mode answering (intent classification)
5. **Phase 7**: Remote admin document management system (web-based)
6. **Phase 8**: Directory answering with text normalization, query canonicalization, entity-aware confidence promotion, soft max-similarity gating
7. **Phase 9**: Entity-anchored directory retrieval (structured directory entities)

## Architecture

```
campus_rag_chatbot/
├── app.py                    # FastAPI server (main entry point)
├── main.py                   # Core RAG/chat logic
├── document_manager.py       # Document ingestion pipeline
├── intent_classifier.py      # Query intent classification
├── confidence_scorer.py      # Confidence scoring system
├── text_normalizer.py        # Text normalization for directory queries
├── entity_registry.py        # Directory entity definitions
├── entity_resolver.py        # Entity resolution pipeline
├── entity_analyzer.py        # Entity analysis utilities
├── query_logger.py           # Query logging
├── admin.py                  # CLI admin interface
├── static/                   # Web frontend (index.html, admin.html, etc.)
├── data/                     # Source documents
│   ├── campus_directory.txt  # Directory/location information
│   ├── campus_info.txt       # General campus info
│   ├── academic_programs.txt # Academic programs
│   └── events_activities.txt # Events and activities
└── vector_store/             # FAISS vector database
```

## Key Components

### Intent Classification
- Classifies queries as: `directory`, `academic`, `event`, `general`, `greeting`, `out_of_scope`
- Directory queries get special handling with entity resolution

### Entity Resolution (Phase 9)
- Directory locations are first-class entities with:
  - `entity_id`, `canonical_name`, `aliases`
  - `building`, `floor`, `room`
- Entity resolution replaces pure similarity-based confidence
- Safety guardrails prevent LLM from inventing location details

### Confidence Scoring
- HIGH/MEDIUM/LOW confidence levels
- Entity-resolved answers get HIGH confidence automatically
- Similarity-based scoring as fallback

## Running the Application

```bash
cd campus_rag_chatbot

# Start the server (runs on 0.0.0.0:8000)
python app.py

# Access points:
# - User interface: http://localhost:8000/
# - Admin interface: http://localhost:8000/admin
```

## Environment Variables (.env)

```
OPENAI_API_KEY=sk-...
ADMIN_API_KEY=<uuid for admin authentication>
```

## Current Work / Next Steps

The project has implemented Phase 9 (entity-anchored directory retrieval). Potential future work:
- Background job queue for long document operations
- HTTPS support
- Enhanced security features
- Document preview in admin interface

## Session Notes

_Use this section to track work in progress between sessions:_

---
