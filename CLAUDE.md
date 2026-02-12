# CoCo - Campus RAG Chatbot

## Project Overview

CoCo (Columban College Information Kiosk) is a RAG-based campus information chatbot built for deployment on a Raspberry Pi 5. It provides students with accurate information about campus locations, services, academic programs, and events.

## Current State

**Completed through Phase 48** - Unified Query Parser

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
18. **Phase 17C**: Single retrieval pipeline, enumeration stability, k=8
19. **Phase 18**: Layout-aware PDF parsing & entity consolidation
20. **Phase 18.1**: Multi-stage text normalization pipeline
21. **Phase 18.2**: Deterministic enumeration extraction (deans)
22. **Phase 19**: Contiguous context reconstruction (neighbor chunk expansion)
23. **Phase 20**: Semantic grounding override for long-form content
24. **Phase 21**: Semantic trust injection for verified content
25. **Phase 21.1**: Synthetic prayer consolidation
26. **Phase 22**: Appendix-aware chunking (larger max_size for appendices)
27. **Phase 23**: Metadata validation & observability
28. **Phase 24**: Generic consolidation framework (config-driven engine)
29. **Phase 25**: Metadata index for fast filtering (O(1) chunk lookups)
30. **Phase 26**: RRF hybrid retrieval scoring
31. **Phase 27**: Awards deterministic extractor & deans extractor fixes
32. **Phase 28**: Query synonym expansion for improved retrieval
33. **Phase 29**: Chunk diversity in results (max 3 per section)
34. **Phase 30**: Negative examples to grounding (entity confusion detection)
35. **Phase 31**: Event dates & office contact extractors
36. **Phase 32**: Voice infrastructure foundation (STT/TTS services)
37. **Phase 33**: Voice API layer (rate limiting, error codes, health monitoring)
38. **Phase 34**: Frontend voice UI (mic button, state machine, audio recording/playback)
39. **Phase 35**: Configurable voice provider selection (runtime engine switching)
40. **Phase 36**: Admin voice configuration UI (provider cards, settings persistence)
41. **Phase 37**: Voice provider fallback configuration (primary/fallback selection)
42. **Phase 38**: Google Cloud STT with usage monitoring (60-min quota tracking)
43. **Phase 39**: Admin-configurable cloud credentials & real-time debugging panel
44. **Phase 40**: Silent TTS with implicit interruption (background audio, auto-stop on input)
45. **Phase 41**: Voice bug fixes & Python 3.11 migration
46. **Phase 42**: Windows setup & UI enhancements (fullscreen toggle, auto-focus disabled, TTS full response)
47. **Phase 44**: LLM-as-Final-Synthesizer architecture (4-layer orchestration, semantic relevance scoring)
48. **Phase 45**: Response Style Policy for kiosk/voice UX (query analyzer, style hints, LaTeX stripping)
49. **Phase 46**: Arithmetic Query Processing (input preprocessor, deterministic math engine, STT artifact cleanup)
50. **Phase 47**: Campus Query Engine Data Model (hierarchical schema, CampusQueryIndex, structural proximity)
51. **Phase 48**: Unified Query Parser (StructuredQuery, QueryIntent, filter extraction, is_campus_query)

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
├── entity_consolidation.py   # DEPRECATED: Use consolidation_engine.py
├── consolidation_engine.py   # Phase 24: Config-driven consolidation
├── metadata_index.py         # Phase 25: Fast chunk lookups by metadata
├── campus_schema.py          # Phase 47: Hierarchical entity schema (Campus/Building/Floor/Room)
├── campus_index.py           # Phase 47: CampusQueryIndex with O(1) lookups
├── migrate_entities.py       # Phase 47: Entity migration validation script
├── structured_query.py       # Phase 48: StructuredQuery, QueryIntent, QueryFilter
├── campus_query_parser.py    # Phase 48: Unified query parser with filter extraction
├── response_orchestrator.py  # Phase 44: LLM-as-Final-Synthesizer architecture
├── query_analyzer.py         # Phase 45: Query type detection for response formatting
├── input_preprocessor.py     # Phase 46: STT artifact cleanup, number normalization
├── math_engine.py            # Phase 46: Deterministic arithmetic evaluation
├── entity_extractors/        # Phase 18.2/27/31: Deterministic extractors
│   ├── deans.py              # Dean enumeration extraction
│   ├── awards.py             # Awards enumeration extraction
│   ├── dates.py              # Event dates extraction (Phase 31)
│   └── contacts.py           # Office contacts extraction (Phase 31)
├── voice/                    # Phase 32-38: Voice integration
│   ├── config.py             # Voice configuration
│   ├── stt_service.py        # Speech-to-Text service
│   ├── tts_service.py        # Text-to-Speech service
│   ├── voice_orchestrator.py # STT -> Chat -> TTS coordination
│   ├── provider_registry.py  # Phase 35: Available STT/TTS providers
│   ├── usage_tracker.py      # Phase 38: Google STT usage monitoring
│   └── engines/              # Engine implementations
│       ├── whisper_cpp.py    # Offline STT (Whisper.cpp)
│       ├── whisper_openai.py # Cloud STT fallback (OpenAI)
│       ├── google_cloud_stt.py  # Cloud STT (Google, Phase 38)
│       ├── piper_tts.py      # Offline TTS (Piper)
│       └── edge_tts.py       # Cloud TTS (Microsoft Edge, free)
├── voice_routes.py           # Phase 32: Voice API endpoints
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

### Hybrid Retrieval & Grounding (Phase 17A/26/28)
- Combines vector similarity with BM25 keyword matching via RRF (Phase 26)
- Prevents semantic neighbor confusion (e.g., "Dean's Lister" returning "Team Leadership Award")
- Query term extraction filters stopwords, identifies key concepts
- Query synonym expansion (Phase 28): "lib"→"library", "tuition"→"payment,fees"
- Grounding validation requires query terms in retrieved chunks
- Refuses gracefully if grounding fails: "I couldn't confidently find information about [topic]"

### Developer Tools (Phase 17A.1)
- Developer page at `/dev` for debugging RAG behavior
- RAG-only mode toggle disables general AI fallback
- When enabled, only document-based answers are returned
- Toggle events logged via EventTracker
- In-memory flag (not persisted to disk)

### Deterministic Extractors (Phase 18.2/27)
- Three-layer architecture: Intent Detection → Extraction → Formatting
- Bypasses LLM for enumeration queries (100% accuracy, no variability)
- Deans extractor: `is_dean_enumeration_query()`, `extract_deans_from_text()`, `format_dean_list()`
- Awards extractor: `is_awards_enumeration_query()`, `extract_awards_from_text()`, `format_awards_list()`
- Handles concatenated single-line content via title pattern splitting
- Filters false positives with role/college pattern matching

### Response Orchestrator (Phase 44-46)
- 4-layer architecture: Governance → Retrieval → Extraction → LLM Synthesis
- All response paths terminate in LLM for natural language generation
- Response modes: EXTRACTOR_AUTHORITATIVE, RAG_AUTHORITATIVE, RAG_SUPPLEMENTED, GENERAL_KNOWLEDGE
- Semantic relevance scoring (HIGH, MEDIUM, LOW) prevents lexical confusion
- Query analyzer detects query types (MATH, GREETING, DEFINITION, CONVERSATIONAL)
- Style hints for kiosk/voice-friendly responses

### Math Engine (Phase 46)
- Deterministic arithmetic evaluation (bypasses LLM)
- Input preprocessing: STT artifact cleanup, number normalization ("5,000" → "5000")
- AST-based evaluation (secure, no eval())
- Supports: +, -, *, /, **, parentheses, word operators (plus, times, etc.)
- Voice-friendly output: "The answer is 42."

### Voice Integration (Phase 32-40)
- Modular STT/TTS architecture with automatic fallback
- Offline-first design: Whisper.cpp for STT, Piper for TTS
- Voice is a MODALITY LAYER - all RAG guarantees preserved
- Endpoints: `/voice/status`, `/voice/transcribe`, `/voice/synthesize`, `/voice/chat`
- Models require separate download (not included in repo)
- Phase 35-37: Runtime provider selection via admin UI
- Phase 38: Google Cloud STT with usage tracking
  - 60-minute monthly free tier quota monitoring
  - Automatic monthly reset on 1st of each month
  - Usage rounded UP to next second per Google billing
  - Admin UI: usage progress bar, credential status display
  - Endpoints: `/admin/voice/usage`, `/admin/voice/credentials/status`
- Phase 39: Admin cloud credential management & debug panel
  - Secure encrypted credential storage (AES-256-GCM)
  - Real-time debug info panel showing LLM/retrieval/grounding details
  - Admin toggle to enable/disable debug visibility
- Phase 40: Silent TTS with implicit interruption
  - TTS plays silently in background (no overlay/modal)
  - Speech auto-stops when user interacts with input controls
  - No explicit "Stop" button required

## Running the Application

```bash
cd campus_rag_chatbot

# IMPORTANT: Use Python 3.11 virtual environment (Piper TTS requires Python 3.11)
# Option 1: Use full path
"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\venv311\Scripts\python.exe" app.py

# Option 2: Activate virtual environment first
# cd C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco
# venv311\Scripts\activate
# cd campus_rag_chatbot
# python app.py

# Access points:
# - User interface: http://localhost:8000/
# - Admin interface: http://localhost:8000/admin
# - Developer tools: http://localhost:8000/dev
# - Voice status: http://localhost:8000/voice/status
```

## Python Version Requirements

**Python 3.11 is required** for full voice functionality (Piper TTS).

- Python 3.13: Piper TTS broken (`espeakbridge` import error)
- Python 3.11: All voice engines working (Piper, Whisper.cpp, Google Cloud STT, edge-tts)

Virtual environment: `venv311/` (Python 3.11.9)
Requirements file: `requirements_py311.txt`

## Environment Variables (.env)

```
OPENAI_API_KEY=sk-...
ADMIN_API_KEY=<uuid for admin authentication>
ADMIN_PASSWORD=<admin password>

# Voice settings (optional)
VOICE_ENABLED=true
WHISPER_MODEL_PATH=/path/to/ggml-tiny.en.bin
PIPER_MODEL_PATH=/path/to/en_US-amy-medium.onnx

# Google Cloud STT (Phase 38)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_STT_ENABLED=true
GOOGLE_STT_QUOTA_SECONDS=3600
USAGE_TRACKING_ENABLED=true
```

## Current Work / Next Steps

The project has completed Phase 42 (Windows Setup & UI Enhancements). Recent additions:
- Phase 40: Silent TTS - audio plays in background, auto-stops on user input
- Phase 41: Voice bug fixes & Python 3.11 migration
- Phase 42: Windows setup & UI enhancements
  - Fullscreen toggle button for kiosk UI (upper-right corner)
  - Auto-focus disabled to prevent virtual keyboard obstruction on RPi
  - TTS reads full responses without truncation (removed 500-char limit)
  - Debug panel now shows actual TTS engine from response header
  - Windows setup script (`win-setup.ps1`) and instructions
  - Added `edge-tts` and `python-magic-bin` to requirements
- Golden test suite: 32 test cases, 87.5% pass rate (28/32)

## RAG Architecture

**Hybrid RAG** - Combines multiple retrieval methods:
- Vector similarity (FAISS/OpenAI embeddings) - 70% weight
- BM25 keyword matching - 30% weight
- RRF (Reciprocal Rank Fusion) for score combination

## Cross-Platform Support

| Platform | Setup Script | Notes |
|----------|--------------|-------|
| Raspberry Pi | `pi-setup.sh` | Primary deployment target |
| Windows | `win-setup.ps1` | Development/testing |

Potential future work (Phases 43+):
- Kiosk hardening (RPi5 optimization, error recovery)
- Multilingual support (Filipino)
- Multi-document namespace support
- Observability dashboard enhancement

## Session Notes

_Use this section to track work in progress between sessions:_

---
