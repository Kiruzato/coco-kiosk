# CoCo - Campus RAG Chatbot

## Project Overview

CoCo (Columban College Information Kiosk) is a RAG-based campus information chatbot built for deployment on a Raspberry Pi 5. It provides students with accurate information about campus locations, services, academic programs, and events.

## Current State

**Completed through Phase 17A.2** - Retrieval-First Routing

### Phase History
1. **Phase 1-3**: Core RAG pipeline, document management, multi-format support
2. **Phase 4**: Web frontend (FastAPI + static HTML/JS/CSS)
3. **Phase 5**: Confidence scoring system
4. **Phase 6**: Dual-mode answering (intent classification)
5. **Phase 7**: Remote admin document management system (web-based)
6. **Phase 8**: Directory answering with text normalization, query canonicalization, entity-aware confidence promotion, soft max-similarity gating
7. **Phase 9**: Entity-anchored directory retrieval (structured directory entities)
8. **Phase 10**: Admin-managed Directory Entity Editor (CRUD operations for directory entities)
9. **Phase 11**: Admin CSV import/export for directory entities
10. **Phase 12**: Campus/department field support for entities
11. **Phase 13**: Session-scoped conversation memory for follow-up queries
12. **Phase 14**: Memory-aware clarification & disambiguation flow
13. **Phase 15**: Document-aware clarification & scoped RAG
14. **Phase 16**: Observability, analytics & failure monitoring
15. **Phase 17A**: Hybrid retrieval (BM25 + vector) & grounding validation
16. **Phase 17A.1**: Developer RAG-only mode toggle for debugging
17. **Phase 17A.2**: Retrieval-first routing (campus-default behavior)

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
├── event_tracker.py          # Phase 16: Observability & analytics
├── retrieval_validator.py    # Phase 17A: Hybrid retrieval & grounding
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

### Entity Resolution (Phase 9-14)
- Directory locations are first-class entities with:
  - `entity_id`, `canonical_name`, `aliases`
  - `building`, `floor`, `room`
  - `status` (active/inactive), `last_updated`
  - `campus`, `department` (Phase 12)
- Entity resolution replaces pure similarity-based confidence
- Safety guardrails prevent LLM from inventing location details
- Admin can create, update, and deactivate entities via web UI
- CSV import/export for bulk entity management (Phase 11)

### Conversation Memory (Phase 13)
- Session-scoped memory tracks last entity discussed
- Follow-up queries ("What floor is it on?") use context
- Context switches when user asks about different entity

### Disambiguation (Phase 14)
- Detects when multiple entities match a query (e.g., "court")
- Presents numbered options for user to select
- Supports selection by number (1-4), word (first, second), or partial name
- Only updates context after user confirms selection

### Confidence Scoring
- HIGH/MEDIUM/LOW confidence levels
- Entity-resolved answers get HIGH confidence automatically
- Similarity-based scoring as fallback

### Observability (Phase 16)
- EventTracker logs structured events (privacy-safe, metadata only)
- Tracks: query types, clarifications, answers, refusals
- Admin analytics dashboard at `/admin/analytics`
- Rolling log limit prevents unbounded growth

### Hybrid Retrieval & Grounding (Phase 17A)
- Combines vector similarity (0.7 weight) with BM25 keyword matching (0.3 weight)
- Prevents semantic neighbor confusion (e.g., "Dean's Lister" returning "Team Leadership Award")
- Query term extraction filters stopwords, identifies key concepts
- Grounding validation requires query terms in retrieved chunks
- Refuses gracefully if grounding fails: "I couldn't confidently find information about [topic]"

### Developer Tools (Phase 17A.1)
- Developer page at `/dev` for debugging RAG behavior
- RAG-only mode toggle disables general AI fallback
- When enabled, only document-based answers are returned
- Toggle events logged via EventTracker
- In-memory flag (not persisted to disk)

## Running the Application

```bash
cd campus_rag_chatbot

# Start the server (runs on 0.0.0.0:8000)
python app.py

# Access points:
# - User interface: http://localhost:8000/
# - Admin interface: http://localhost:8000/admin
# - Developer tools: http://localhost:8000/dev
```

## Environment Variables (.env)

```
OPENAI_API_KEY=sk-...
ADMIN_API_KEY=<uuid for admin authentication>
```

## Current Work / Next Steps

The project has implemented Phase 17A (hybrid retrieval & grounding validation). Potential future work:
- Phase 17B: Multi-word phrase detection for improved term extraction
- Background job queue for long document operations
- HTTPS support
- Enhanced security features
- Document preview in admin interface

## Session Notes

_Use this section to track work in progress between sessions:_

---
