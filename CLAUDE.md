# CoCo - Campus RAG Chatbot

## Project Overview

CoCo (Columban College Information Kiosk) is a RAG-based campus information chatbot built for deployment on a Raspberry Pi 5. It provides students with accurate information about campus locations, services, academic programs, and events.

## Current State

**Completed through Phase 53** - RPi Runtime Optimization

### Phase History
1. **Phase 1-3**: Core RAG pipeline, document management, multi-format support
2. **Phase 4**: Web frontend (FastAPI + static HTML/JS/CSS)
3. **Phase 5**: Confidence scoring system
4. **Phase 6**: Dual-mode answering (intent classification)
5. **Phase 7**: Remote admin document management system (web-based)
6. **Phase 8**: Directory answering with text normalization, query canonicalization
7. **Phase 9-12**: _(Deprecated - entity system removed in Phase 52)_
11. **Phase 13**: Session-scoped conversation memory for follow-up queries
12. **Phase 14**: Memory-aware clarification & disambiguation flow
13. **Phase 15**: Document-aware clarification & scoped RAG
14. **Phase 16**: Observability, analytics & failure monitoring
15. **Phase 17A**: Hybrid retrieval (BM25 + vector) & grounding validation
16. **Phase 17A.1**: _(Removed — RAG-only mode removed in final-phase cleanup)_
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
50. **Phase 48**: Advertisement Panel (admin slideshow, navigation, visibility toggle)
51. **Phase 49**: Welcome Message System (admin-configurable text and image)
52. **Phase 50**: Response Metadata Visibility Toggle (separate from Debug Panel)
53. **Phase 50B**: Mode badges controlled by metadata visibility toggle
54. **Phase 51**: Developer Settings Consistency Fix (immediate toggle effect, debug panel for directory queries)
55. **Phase 52**: Directory Entity → RAG Migration (removed 1,400+ lines of entity code, directory data now in PDF)
56. **Phase 53**: RPi Runtime Optimization (runtime-only requirements, import guards, reduced install footprint)

## Architecture

```
campus_rag_chatbot/
├── app.py                    # FastAPI server (main entry point)
├── document_manager.py       # Document ingestion pipeline
├── intent_classifier.py      # Query intent classification
├── confidence_scorer.py      # Confidence scoring system
├── text_normalizer.py        # Text normalization for queries
├── query_logger.py           # Query logging
├── event_tracker.py          # Phase 16: Observability & analytics
├── retrieval_validator.py    # Phase 17A: Hybrid retrieval & grounding
├── consolidation_engine.py   # Phase 24: Config-driven consolidation
├── metadata_index.py         # Phase 25: Fast chunk lookups by metadata
├── response_orchestrator.py  # Phase 44: LLM-as-Final-Synthesizer architecture
├── query_analyzer.py         # Phase 45: Query type detection for response formatting
├── input_preprocessor.py     # Phase 46: STT artifact cleanup, number normalization
├── math_engine.py            # Phase 46: Deterministic arithmetic evaluation
├── advertisement_manager.py  # Phase 48: Advertisement panel management
├── credential_manager.py     # Phase 39: Encrypted credential storage
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
├── admin.py                  # CLI admin interface (ingestion only)
├── static/                   # Web frontend (index.html, admin.html, etc.)
├── data/                     # Configuration files
│   ├── debug_settings.json   # Phase 50: Debug panel & metadata visibility settings
│   ├── welcome_config.json   # Phase 49: Welcome message configuration
│   ├── ad_settings.json      # Phase 48: Advertisement panel settings
│   ├── voice_settings.json   # Voice provider configuration
│   ├── consolidation_rules.json  # Phase 24: Entity consolidation rules
│   └── metadata_index.json   # Phase 25: Chunk metadata index
├── documents_to_ingest/      # Source documents for ingestion
├── images/                   # Phase 48: Advertisement images
└── vector_store/             # FAISS vector database (pre-built)
```

## Key Components

### Intent Classification
- Classifies queries as: `directory`, `academic`, `event`, `general`, `greeting`, `out_of_scope`
- Directory queries use RAG-based retrieval from ingested directory documents

### Directory Queries (RAG-based, Phase 52)
- All 220 campus locations stored in RAG-optimized PDF document
- Self-contained paragraphs with aliases embedded ("also known as")
- Grouped by building for optimal retrieval
- No structured entity database - fully document-driven

### Conversation Memory (Phase 13)
- Session-scoped memory tracks conversation context
- Follow-up queries use prior context for coherent responses

### Confidence Scoring
- HIGH/MEDIUM/LOW confidence levels
- Similarity-based scoring from RAG retrieval results

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

### Developer Tools
- Developer page at `/dev` with password protection (separate from admin auth)
- Developer visibility toggle controls whether "Developer" section appears in admin sidebar
- Setting persisted in `debug_settings.json` (survives restarts)

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

### Advertisement Panel (Phase 48)
- Admin-configurable slideshow in chatbot UI info panel
- Upload/delete advertisement images via Admin UI
- Configurable auto-rotation interval (default: 5 seconds)
- Visibility toggle to show/hide entire panel
- Left/right navigation zones for manual browsing
- Persisted in `data/ad_settings.json`
- Images stored in `images/` directory
- Endpoints: `/admin/ads/list`, `/admin/ads/upload`, `/admin/ads/delete`, `/admin/ads/settings`

### Welcome Message System (Phase 49)
- Admin-editable welcome message displayed at chat start
- Optional image display (CoCo logo)
- Markdown-style formatting support (newlines → `<br>`, `**bold**`)
- Persisted in `data/welcome_config.json`
- Endpoints: `/api/welcome`, `/admin/welcome`

### Developer Settings (Phase 50-51)
- **Response Metadata Toggle**: Controls visibility of confidence, score, sources, mode badges
  - Separate and independent from Debug Panel toggle
  - Immediate effect without page refresh (server-authoritative)
  - Setting included in each response (`metadata_visible` field)
- **Debug Panel**: Shows technical details for each response
  - LLM provider, retrieval mode, chunks retrieved, grounding status, timing
  - Works for all query types including directory RAG fallback (Phase 51 fix)
- Both toggles in Admin UI → Developer section (`/admin#developer`)
- Settings persisted in `data/debug_settings.json`

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

### Requirements Files

| File | Purpose | Use Case |
|------|---------|----------|
| `requirements.txt` | Full dependencies | Development/Windows |
| `requirements_rpi.txt` | ARM64 optimized | Full RPi install |
| `requirements_rpi_runtime.txt` | Runtime only | RPi deployment (no ingestion) |

**Note**: RPi deployment uses `requirements_rpi_runtime.txt` by default (excludes ingestion packages like `unstructured`, `pypdf`, `python-docx`).

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

The project has completed Phase 53 (RPi Runtime Optimization). Recent changes:

- **Phase 52**: Directory Entity → RAG Migration
  - Removed entity system (~1,400 lines): `entity_registry.py`, `entity_resolver.py`, etc.
  - Directory queries now use unified RAG orchestrator flow
  - All 220 campus locations stored in RAG-optimized PDF document

- **Phase 53**: RPi Runtime Optimization
  - Created `requirements_rpi_runtime.txt` (excludes ingestion packages)
  - Fixed logger initialization bug in `document_manager.py`
  - Updated `pi-setup.sh` for runtime-only deployment
  - ~60 packages removed from RPi install, 30-40% faster setup

- Golden test suite: 32 test cases, 87.5% pass rate (28/32)

## RAG Architecture

**Hybrid RAG** - Combines multiple retrieval methods:
- Vector similarity (FAISS/OpenAI embeddings) - 70% weight
- BM25 keyword matching - 30% weight
- RRF (Reciprocal Rank Fusion) for score combination

## Cross-Platform Support

| Platform | Setup Script | Requirements | Notes |
|----------|--------------|--------------|-------|
| Raspberry Pi | `pi-setup.sh` | `requirements_rpi_runtime.txt` | Runtime-only (no ingestion) |
| Windows | `win-setup.ps1` | `requirements.txt` | Development/testing |

### RPi Deployment Mode
The RPi runs in **runtime-only mode**:
- Loads pre-built FAISS index from git repository
- Does NOT perform document ingestion
- Ingestion packages excluded to reduce install time

Potential future work:
- Kiosk hardening (RPi5 optimization, error recovery)
- Multilingual support (Filipino)
- Multi-document namespace support
- Observability dashboard enhancement

## Session Notes

_Use this section to track work in progress between sessions:_

---
