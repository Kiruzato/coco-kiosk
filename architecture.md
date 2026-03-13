# Architecture Overview

This document describes the architecture of the CoCo Campus RAG Chatbot WEB_APP system — the runtime application deployed on a Raspberry Pi 5 kiosk or Windows development machine. It reflects the current operational system as implemented in the codebase.

---

## 1. Project Structure

This section provides a high-level overview of the WEB_APP directory and file structure, organized by architectural layer and functional area.

```
WEB_APP/
├── app.py                          # FastAPI server — main entry point (74 endpoints)
├── __init__.py                     # Python package marker
├── __main__.py                     # Alternative entry point (python -m WEB_APP)
├── .env                            # Environment variables (API keys, passwords)
├── .env.example                    # Template for .env configuration
│
├── modules/                        # Core application modules
│   ├── document_manager.py         # Document ingestion, vector store management
│   ├── response_orchestrator.py    # 4-layer response synthesis engine
│   ├── intent_classifier.py        # Query intent classification
│   ├── confidence_scorer.py        # Retrieval confidence scoring
│   ├── retrieval_validator.py      # Hybrid retrieval, grounding validation
│   ├── query_analyzer.py           # Query type detection for response formatting
│   ├── input_preprocessor.py       # STT artifact cleanup, number normalization
│   ├── math_engine.py              # Deterministic arithmetic evaluation
│   ├── response_formatter.py       # Kiosk-friendly response formatting
│   ├── text_normalizer.py          # Text normalization for embedding/retrieval
│   ├── text_normalizer_pipeline.py # PDF text preprocessing pipeline
│   ├── consolidation_engine.py     # Config-driven entity consolidation
│   ├── metadata_index.py           # O(1) chunk metadata lookups
│   ├── advertisement_manager.py    # Advertisement panel CRUD
│   ├── faq_manager.py              # FAQ management (max 20 items)
│   ├── trivia_manager.py           # Daily trivia, quotes, study tips
│   ├── credential_manager.py       # Encrypted credential storage (AES-256-GCM)
│   ├── event_tracker.py            # Privacy-safe structured event logging
│   ├── query_logger.py             # Conversation logging with feedback
│   ├── voice_routes.py             # Voice API endpoints (FastAPI router)
│   │
│   ├── entity_extractors/          # Deterministic data extractors (no LLM)
│   │   ├── deans.py                # Dean enumeration extraction
│   │   ├── awards.py               # Academic awards extraction
│   │   ├── dates.py                # Event dates extraction
│   │   └── contacts.py             # Office contacts extraction
│   │
│   ├── voice/                      # Voice infrastructure
│   │   ├── config.py               # Voice configuration management
│   │   ├── stt_service.py          # Speech-to-Text service with fallback
│   │   ├── tts_service.py          # Text-to-Speech service with optimization
│   │   ├── voice_orchestrator.py   # STT → Chat → TTS coordination
│   │   ├── provider_registry.py    # Provider discovery and configuration
│   │   ├── usage_tracker.py        # Google Cloud STT quota tracking
│   │   ├── audio_utils.py          # Audio format conversion/normalization
│   │   └── engines/                # Engine implementations
│   │       ├── whisper_cpp.py      # Offline STT (Whisper.cpp, ARM64 NEON)
│   │       ├── google_cloud_stt.py # Cloud STT (Google, free-tier quota)
│   │       ├── piper_tts.py        # Offline TTS (Piper neural voice)
│   │       └── espeak_tts.py       # Lightweight TTS fallback (espeak-ng)
│   │
│   ├── static/                     # Web frontend assets
│   │   ├── index.html              # Chatbot user interface
│   │   ├── admin.html              # Admin panel
│   │   ├── dev.html                # Developer tools page
│   │   ├── dev_login.html          # Developer authentication page
│   │   ├── login.html              # Admin login page
│   │   ├── app.js                  # Chatbot frontend logic
│   │   ├── admin.js                # Admin panel logic
│   │   ├── dev.js                  # Developer tools logic
│   │   ├── style.css               # Chatbot styling
│   │   ├── admin.css               # Admin panel styling
│   │   ├── login.css               # Login page styling
│   │   └── images/                 # Static images (logos)
│   │
│   ├── data/                       # Configuration and runtime data
│   │   ├── debug_settings.json     # Debug panel and metadata visibility
│   │   ├── voice_settings.json     # Voice provider configuration
│   │   ├── welcome_config.json     # Welcome message text and image
│   │   ├── advertisement_registry.json  # Advertisement metadata
│   │   ├── faq_data.json           # FAQ items storage
│   │   ├── trivia_content.json     # Monthly trivia/quotes content
│   │   ├── consolidation_rules.json     # Entity consolidation patterns
│   │   ├── document_registry.json  # Ingested document metadata
│   │   ├── metadata_index.json     # Chunk metadata index
│   │   ├── stt_usage.json          # Google STT monthly usage
│   │   ├── credentials.enc         # Encrypted cloud credentials
│   │   ├── advertisements/         # User-uploaded advertisement images
│   │   └── uploaded/               # User-uploaded documents
│   │
│   ├── logs/                       # Observability logs (JSONL)
│   │   ├── conversations.jsonl     # Conversation history with feedback
│   │   └── events.jsonl            # Structured event tracking
│   │
│   ├── vector_store/               # FAISS vector database (pre-built)
│   │   ├── index.faiss             # FAISS index binary
│   │   └── index.pkl               # LangChain docstore (metadata + mappings)
│   │
│   └── documents_to_ingest/        # Source documents (reference only at runtime)
│
├── deploy/                         # Raspberry Pi kiosk deployment
│   ├── install_kiosk.sh            # Full kiosk installation
│   ├── update_kiosk.sh             # Incremental update script
│   ├── uninstall_kiosk.sh          # Kiosk removal
│   ├── coco-kiosk.service          # systemd service file
│   └── coco-chromium.desktop       # Desktop launcher
│
├── requirements_rpi.txt            # RPi ARM64 dependencies
└── requirements_windows.txt        # Windows development dependencies
```

---

## 2. High-Level System Diagram

The CoCo system is a monolithic FastAPI application serving both the API backend and static frontend from a single process. The application runs locally on the deployment target (Raspberry Pi or Windows machine) with no external database — all data is stored on the local filesystem.

```
                        ┌─────────────────────────────────────────────────┐
                        │                    Kiosk User                   │
                        │             (Touchscreen / Browser)             │
                        └──────────┬──────────────────┬───────────────────┘
                                   │ Text              │ Voice
                                   ▼                   ▼
                        ┌──────────────────────────────────────────────────┐
                        │              Frontend (Static HTML/JS/CSS)       │
                        │   index.html    admin.html    dev.html           │
                        │   app.js        admin.js      dev.js             │
                        └──────────┬──────────────────┬───────────────────┘
                                   │ POST /chat        │ POST /voice/chat
                                   │ POST /chat/stream │
                                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (app.py)                          │
│                                                                          │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ Admin Routes  │  │ Chat Routes      │  │ Voice Routes               │  │
│  │ /admin/*      │  │ /chat            │  │ /voice/transcribe          │  │
│  │ /dev/*        │  │ /chat/stream     │  │ /voice/synthesize          │  │
│  │ /api/*        │  │ /feedback        │  │ /voice/chat                │  │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬─────────────────┘  │
│         │                   │                        │                    │
│         │                   ▼                        ▼                    │
│         │         ┌──────────────────┐    ┌──────────────────────┐        │
│         │         │ Response         │    │ Voice Orchestrator    │        │
│         │         │ Orchestrator     │◄───│ STT → Chat → TTS     │        │
│         │         │ (4-Layer Engine) │    └──────────────────────┘        │
│         │         └────────┬─────────┘                                   │
│         │                  │                                              │
│         │    ┌─────────────┼──────────────────┐                          │
│         │    ▼             ▼                  ▼                          │
│  ┌────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ Intent     │  │ Retrieval      │  │ Entity         │                 │
│  │ Classifier │  │ Validator      │  │ Extractors     │                 │
│  └────────────┘  │ (Hybrid RAG)  │  │ (Deterministic)│                 │
│                  └───────┬────────┘  └────────────────┘                 │
│                          │                                               │
│                          ▼                                               │
│               ┌──────────────────┐          ┌──────────────────┐        │
│               │ FAISS Vector     │          │ OpenAI API       │        │
│               │ Store (Local)    │          │ (Embeddings+LLM) │        │
│               └──────────────────┘          └──────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Data Flow Summary:**
1. User submits text or voice query via the frontend
2. Voice queries are transcribed (STT) before entering the chat pipeline
3. The Response Orchestrator classifies intent, retrieves relevant chunks, validates grounding, and synthesizes a response via LLM
4. Voice responses are additionally synthesized to audio (TTS) before returning
5. All interactions are logged for analytics (metadata only, privacy-safe)

---

## 3. Core Components

### 3.1. Frontend

**Name:** CoCo Kiosk Web Interface

**Description:** A single-page web application providing three interfaces: the chatbot UI for students (index.html), an admin panel for content management (admin.html), and a developer tools page for system configuration (dev.html). The frontend communicates with the backend exclusively through REST API calls and Server-Sent Events for streaming responses.

**Technologies:** HTML5, CSS3, vanilla JavaScript (no framework), Server-Sent Events (SSE)

**Key Features:**
- Chat interface with voice input (microphone button), FAQ quick-actions, and feedback (thumbs up/down)
- Drag-to-scroll for touchscreen kiosk interaction (Pointer Events API with 5px gesture threshold)
- Advertisement slideshow panel with auto-rotation
- Welcome message display with optional logo
- Daily trivia questions and inspirational quotes
- Text selection disabled for kiosk mode (`user-select: none`)
- Admin panel with tabbed interface: Documents, Advertisements, FAQs, Voice Config, Welcome Message, Developer Settings, Kiosk Management, Analytics

**Deployment:** Served as static files by FastAPI's StaticFiles middleware. On RPi, displayed in fullscreen Chromium kiosk mode via systemd.

---

### 3.2. Backend Services

#### 3.2.1. FastAPI Application Server

**Name:** CoCo Backend API

**Description:** Monolithic FastAPI application serving 74 REST endpoints across chat, admin, voice, developer, and kiosk management. Handles all business logic, session management, and file serving from a single process.

**Technologies:** Python 3.11, FastAPI, Uvicorn, Pydantic, LangChain, FAISS, OpenAI SDK

**Deployment:** Single-process Uvicorn server on port 8000. On RPi, managed by systemd (`coco-kiosk.service`). On Windows, launched via `run.ps1` or directly with `python app.py`.

**Endpoint Groups:**

| Group | Count | Prefix | Purpose |
|-------|-------|--------|---------|
| Chat | 3 | `/chat`, `/feedback`, `/reset` | Query processing and feedback |
| Admin Auth | 4 | `/admin/login`, `/admin/logout` | Session-based authentication |
| Documents | 3 | `/admin/documents`, `/admin/upload_rag_package` | Knowledge base management |
| Voice Config | 7 | `/admin/voice/*` | STT/TTS provider and credential management |
| Advertisements | 8 | `/admin/advertisements/*`, `/api/advertisements` | Ad panel CRUD |
| FAQs | 7 | `/admin/faqs/*`, `/api/faqs` | FAQ management |
| Welcome | 3 | `/admin/welcome`, `/api/welcome` | Welcome message configuration |
| Trivia | 5 | `/admin/trivia/*`, `/api/trivia/*` | Daily content management |
| Debug/Metadata | 4 | `/admin/debug/*`, `/admin/metadata/*` | Visibility toggles |
| Developer | 9 | `/dev/*`, `/api/settings/*` | Developer tools and settings |
| Test Harness | 5 | `/admin/test-harness/*` | Automated testing |
| Kiosk | 5 | `/admin/kiosk/*` | Hardware management (WiFi, shutdown, reboot) |
| Analytics | 3 | `/admin/analytics/*` | Event and conversation analytics |
| Health | 2 | `/health`, `/` | Health check and frontend serving |
| Voice | 6+ | `/voice/*` | STT/TTS operations (separate router) |

---

#### 3.2.2. Response Orchestrator

**Name:** LLM-as-Final-Synthesizer Engine

**Description:** The central response generation engine implementing a 4-layer architecture where all response paths terminate in an LLM for natural language synthesis. Coordinates intent classification, hybrid retrieval, deterministic extraction, and prompt-based LLM generation.

**Technologies:** LangChain, OpenAI GPT-4o-mini, FAISS

**Architecture:**

```
Layer 1: Governance
├── Intent classification (campus / general / directory / ambiguous)
├── Safety validation
└── Directory query detection (regex-based)

Layer 2: Retrieval
├── FAISS vector similarity search (k=8)
├── BM25 keyword scoring
├── Reciprocal Rank Fusion (RRF) score combination
├── Grounding validation (query terms must appear in chunks)
├── Semantic relevance scoring (HIGH / MEDIUM / LOW)
├── Section diversity limiting (max 3 chunks per section)
└── Entity confusion detection

Layer 3: Extraction
├── Deans extractor (enumeration queries)
├── Awards extractor (academic honors)
├── Event dates extractor (schedules)
└── Office contacts extractor (phone/email)

Layer 4: LLM Synthesis
├── Mode determination based on layers 1-3
├── Mode-specific prompt construction
├── OpenAI ChatGPT generation
└── Style hints for response formatting
```

**Response Modes:**

| Mode | Trigger | Behavior |
|------|---------|----------|
| EXTRACTOR_AUTHORITATIVE | Deterministic extractor matched and grounded | Present verified data naturally |
| RAG_AUTHORITATIVE | High semantic relevance and grounded | Answer strictly from documents |
| RAG_SUPPLEMENTED | Grounded but low/medium relevance | Use campus info if relevant |
| GENERAL_KNOWLEDGE | No campus relevance or ungrounded | Answer as helpful AI assistant |

**Fast Path:** Arithmetic queries (e.g., "5 + 3") bypass all layers and return immediately via the Math Engine (AST-based evaluation, no LLM call).

---

#### 3.2.3. Voice Pipeline

**Name:** Voice Modality Layer

**Description:** Provides speech input and output capabilities as a modality wrapper around the existing chat pipeline. Voice does not alter RAG logic, grounding rules, or confidence scoring — it only converts between audio and text. Designed offline-first with cloud fallback.

**Technologies:** Whisper.cpp (STT), Piper TTS (speech synthesis), Google Cloud Speech-to-Text (optional cloud STT), espeak-ng (fallback TTS)

**Pipeline Flow:**

```
Microphone Audio (Browser MediaRecorder)
    ↓
POST /voice/chat (multipart audio upload)
    ↓
┌─ STT ──────────────────────────────────┐
│ 1. Audio validation (format, size)     │
│ 2. Normalize to 16kHz mono WAV         │
│ 3. Transcribe with primary engine      │
│ 4. If confidence < 0.7 → try fallback  │
│ 5. Return text + confidence            │
└────────────────────────────────────────┘
    ↓ (preprocessed: STT artifact cleanup)
┌─ Chat ─────────────────────────────────┐
│ Routes through existing /chat pipeline │
│ All RAG guarantees preserved           │
└────────────────────────────────────────┘
    ↓
┌─ TTS ──────────────────────────────────┐
│ 1. Strip markdown from answer          │
│ 2. Expand abbreviations                │
│ 3. Synthesize to audio (Piper TTS)     │
│ 4. Store audio with 5-min TTL          │
│ 5. Return audio URL                    │
└────────────────────────────────────────┘
    ↓
VoiceChatResponse (transcription + answer + audio URL + latencies)
```

**Provider Architecture:**

| Service | Primary (Offline) | Fallback |
|---------|-------------------|----------|
| STT | Whisper.cpp (ARM64 NEON optimized) | Google Cloud STT (60-min/month free tier) |
| TTS | Piper TTS (neural voice model) | espeak-ng (lightweight) |

**Voice API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/status` | GET | Service availability |
| `/voice/health` | GET | Detailed health metrics |
| `/voice/transcribe` | POST | STT only |
| `/voice/synthesize` | POST | TTS only |
| `/voice/chat` | POST | Full STT → Chat → TTS |
| `/voice/audio/{id}` | GET | Retrieve temporary audio |
| `/voice/stream` | WS | WebSocket streaming transcription |

**Rate Limiting:** 30 transcribe / 60 synthesize / 20 chat requests per 60 seconds per client.

---

#### 3.2.4. Admin Subsystem

**Name:** Administration and Content Management

**Description:** Provides web-based management of all configurable aspects of the kiosk: knowledge base (RAG packages), advertisements, FAQs, welcome messages, voice configuration, cloud credentials, and kiosk hardware control.

**Technologies:** FastAPI endpoints, session-based authentication, JSON file persistence

**Capabilities:**

| Feature | Description |
|---------|-------------|
| RAG Package Upload | Upload .zip containing pre-built FAISS index to replace knowledge base |
| Document Management | View and delete ingested documents |
| Advertisement Panel | Upload/delete images, create/edit text ads, reorder, toggle visibility |
| FAQ Management | CRUD for up to 20 FAQ items, reordering, AI-generation from documents |
| Welcome Message | Editable greeting text with optional image |
| Trivia Content | Monthly trivia questions, study tips, quotes (LLM-generated, cached) |
| Voice Configuration | Select STT/TTS providers, configure fallbacks, manage cloud credentials |
| Kiosk Management | WiFi scanning/connection, system shutdown/reboot, IP address display |
| Analytics Dashboard | Query type distribution, confidence rates, conversation viewer |
| Developer Settings | Debug panel toggle, metadata visibility, fusion method selection |

---

## 4. Data Stores

### 4.1. FAISS Vector Store

**Name:** Knowledge Base Vector Index

**Type:** FAISS (Facebook AI Similarity Search) with IndexFlatL2

**Purpose:** Stores document chunk embeddings for semantic similarity search. This is the core data store for the RAG pipeline — all campus information retrieval queries are resolved against this index.

**Key Files:**
- `vector_store/index.faiss` — Binary vector index (1536-dimensional float vectors)
- `vector_store/index.pkl` — LangChain docstore (Document objects with full metadata)

**Schema:** Each entry in the docstore contains:
- `page_content` — Normalized text (lowercase, whitespace-collapsed) used for embedding
- `metadata.document_id` — Source document identifier
- `metadata.document_name` — Original filename
- `metadata.section` / `metadata.section_title` — Section heading
- `metadata.original_text` — Display-quality text (original casing preserved)
- `metadata.chunk_id` — Sequential chunk index within document
- `metadata.page_numbers` — PDF page numbers spanned
- `metadata.element_types` — Structural element types (Title, NarrativeText, etc.)
- `metadata.is_synthetic` — Whether chunk was created by consolidation engine
- `metadata.is_appendix` — Whether chunk belongs to an appendix section

---

### 4.2. Document Registry

**Name:** Ingested Document Metadata

**Type:** JSON file (`data/document_registry.json`)

**Purpose:** Tracks all documents that have been ingested into the vector store, including file hashes for duplicate detection and chunk counts.

**Key Fields:** `document_name`, `file_type`, `file_hash` (SHA-256), `file_path`, `ingestion_timestamp`, `num_chunks`, `chunk_size`, `chunk_overlap`

---

### 4.3. Metadata Index

**Name:** Chunk Metadata Cache

**Type:** JSON file (`data/metadata_index.json`)

**Purpose:** Provides O(1) lookups of chunk metadata by chunk_id, section, page number, or document_id — avoiding iteration over the entire FAISS docstore at query time. Used by the neighbor chunk expansion system and section-filtered queries.

---

### 4.4. Configuration Files

**Type:** JSON files in `data/`

**Purpose:** Persistent storage for all runtime-configurable settings.

| File | Purpose |
|------|---------|
| `debug_settings.json` | Debug panel, metadata visibility, fusion method, developer toggles |
| `voice_settings.json` | Selected STT/TTS providers and fallback configuration |
| `welcome_config.json` | Welcome message text and image path |
| `advertisement_registry.json` | Advertisement metadata, display order, active status |
| `faq_data.json` | FAQ items with questions, answers, and ordering |
| `trivia_content.json` | Monthly generated trivia questions, study tips, quotes |
| `consolidation_rules.json` | Entity consolidation patterns (deans, prayer) |
| `stt_usage.json` | Google Cloud STT monthly quota usage tracking |
| `credentials.enc` | AES-256-GCM encrypted cloud credentials |

---

### 4.5. Observability Logs

**Type:** JSONL files in `logs/`

**Purpose:** Privacy-safe event and conversation logging for analytics.

| File | Purpose | Retention |
|------|---------|-----------|
| `conversations.jsonl` | Query-answer pairs with feedback | Current + previous month |
| `events.jsonl` | Structured events (query types, refusals, voice interactions) | Rolling 10,000 events |

---

## 5. External Integrations / APIs

### OpenAI API

**Purpose:** LLM inference (response generation) and text embedding (vector search)

**Integration Method:** OpenAI Python SDK via LangChain wrappers

**Models Used:**
- `gpt-4o-mini` — Chat completion for response synthesis, intent classification, FAQ generation, trivia generation
- `text-embedding-3-small` — 1536-dimensional embeddings for FAISS vector store

**Usage Points:**
- Response Orchestrator (all response modes except math)
- Intent Classifier (lightweight governance classification)
- FAQ Generator (AI-generated FAQ suggestions from documents)
- Trivia Manager (monthly content generation)

---

### Google Cloud Speech-to-Text

**Purpose:** Cloud-based speech transcription (optional fallback for Whisper.cpp)

**Integration Method:** Google Cloud Python SDK

**Quota:** 60-minute monthly free tier with automatic tracking and reset

**Configuration:** Service account JSON stored encrypted via Credential Manager

---

## 6. Deployment & Infrastructure

### Target Platforms

| Platform | Role | Setup Script | Requirements |
|----------|------|-------------|--------------|
| Raspberry Pi 5 | Production kiosk | `deploy/install_kiosk.sh` | `requirements_rpi.txt` |
| Windows 10/11 | Development and testing | `setup_windows.ps1` | `requirements_windows.txt` |

### Raspberry Pi Kiosk Deployment

**Operating Mode:** Runtime-only (no document ingestion on device)

**Components:**
- **systemd service** (`coco-kiosk.service`): Auto-starts Uvicorn on boot
- **Chromium kiosk mode** (`coco-chromium.desktop`): Fullscreen browser pointed at `localhost:8000`
- **WiFi management**: `nmcli` commands via admin API for network configuration
- **System control**: Shutdown/reboot via admin API (`systemctl poweroff` / `systemctl reboot`)

**Deployment Flow:**
1. Run `install_kiosk.sh` on fresh RPi OS
2. Upload pre-built RAG package (.zip) via Admin UI
3. Configure voice providers and credentials via Admin UI
4. System auto-starts on boot in kiosk mode

**Update Flow:**
- `update_kiosk.sh` pulls latest code from git, preserves data files, restarts service

### Application Server

**Server:** Uvicorn (ASGI)
- Host: `0.0.0.0`
- Port: `8000`
- Workers: 1 (single-process, stateful sessions)

---

## 7. Security Considerations

### Authentication

**Admin Panel:** Session-based authentication
- Password verified against `ADMIN_PASSWORD` environment variable
- Secure random token generated on login (`secrets.token_urlsafe`)
- 8-hour session duration with automatic expiry
- Session stored in-memory (cleared on restart)

**Developer Tools:** Separate session-based authentication
- Password verified against `DEV_PASSWORD` environment variable
- Independent session management from admin

**Kiosk Access:** No authentication for the chatbot user interface (public kiosk)

### Credential Storage

**Mechanism:** AES-256-GCM encryption with PBKDF2 key derivation
- Encryption key derived from `ADMIN_PASSWORD` using 100,000 PBKDF2 iterations
- Random 16-byte salt per encryption operation
- Random 12-byte nonce per encryption
- Stored in `data/credentials.enc`
- Atomic file writes (temp file + rename) prevent corruption

**Protected Credentials:**
- OpenAI API key (maps to `OPENAI_API_KEY` environment variable)
- Google Cloud service account JSON (written to temp file, maps to `GOOGLE_APPLICATION_CREDENTIALS`)

### Data Privacy

- Event tracking is metadata-only (no query text stored in events)
- Conversation logs retain only current + previous calendar month
- No personal user data collected (anonymous kiosk usage)
- Rolling log limits prevent unbounded storage growth

### Input Validation

- Audio uploads validated for format (magic bytes), size (10MB limit), and duration (60s limit)
- File uploads restricted to `.zip` for RAG packages
- Advertisement images restricted to JPEG/PNG, 5MB limit
- Pydantic models validate all API request bodies
- Math engine uses AST-based evaluation (no `eval()`)

### Network

- CORS enabled for all origins (kiosk operates on localhost)
- No TLS termination (local deployment, no external exposure)
- Voice rate limiting prevents abuse (per-client IP tracking)

---

## 8. Development & Testing Environment

### Local Setup (Windows)

```bash
# Create Python 3.11 virtual environment
python -m venv venv311

# Activate
venv311\Scripts\activate

# Install dependencies
pip install -r WEB_APP/requirements_windows.txt

# Configure environment
cp WEB_APP/.env.example WEB_APP/.env
# Edit .env with OpenAI API key and passwords

# Run
python WEB_APP/app.py
# Access: http://localhost:8000
```

### Testing Framework

**Test Harness:** Built-in admin test suite
- Configurable test questions via Admin UI
- Streaming execution with per-question results
- Results exportable as JSON or CSV
- Golden test suite: 32 test cases

**Access:** Admin UI > Test Harness tab, or via API:
- `GET /admin/test-harness/execute/stream` — Execute all tests (SSE)
- `GET /admin/test-harness/results/latest` — View latest results
- `GET /admin/test-harness/results/download` — Export results

### Code Quality

- Python type hints throughout codebase
- Pydantic models for request/response validation
- Structured logging via Python `logging` module
- Modular architecture with clear separation of concerns

---

## 9. Future Considerations / Roadmap

- **Multilingual support:** Filipino language for broader campus accessibility
- **Kiosk hardening:** Error recovery, watchdog monitoring, display sleep management
- **Multi-document namespace support:** Separate vector stores per document category
- **Observability dashboard enhancement:** Richer analytics visualizations
- **Offline LLM:** On-device language model to eliminate OpenAI dependency

---

## 10. Project Identification

**Project Name:** CoCo — Columban College Information Kiosk

**Repository URL:** (Private repository)

**Primary Contact/Team:** Thesis development team, Columban College

**Date of Last Update:** 2026-03-13

**Runtime Version:** 5.0.0 (FastAPI app version)

**Python Version:** 3.11 (required for Piper TTS compatibility)

---

## 11. Glossary / Acronyms

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation — architecture that grounds LLM responses in retrieved documents |
| **FAISS** | Facebook AI Similarity Search — library for efficient similarity search of dense vectors |
| **STT** | Speech-to-Text — converting audio speech to text transcription |
| **TTS** | Text-to-Speech — converting text to synthesized audio speech |
| **LLM** | Large Language Model — AI model for natural language generation (GPT-4o-mini) |
| **RRF** | Reciprocal Rank Fusion — method for combining ranked result lists from multiple retrieval systems |
| **BM25** | Best Matching 25 — probabilistic keyword-based document ranking algorithm |
| **SSE** | Server-Sent Events — HTTP-based protocol for server-to-client streaming |
| **FAISS IndexFlatL2** | Brute-force L2 (Euclidean) distance search index — exact nearest neighbor lookup |
| **NFKC** | Unicode Normalization Form KC — canonical decomposition followed by compatibility composition |
| **AST** | Abstract Syntax Tree — tree representation of source code structure, used for safe math evaluation |
| **AES-256-GCM** | Advanced Encryption Standard with Galois/Counter Mode — authenticated encryption algorithm |
| **PBKDF2** | Password-Based Key Derivation Function 2 — key stretching algorithm for deriving encryption keys |
| **RPi** | Raspberry Pi — single-board ARM computer used as kiosk deployment target |
| **CoCo** | Columban College Information Kiosk — the project name |
| **Grounding** | Validation that LLM responses are supported by retrieved document content |
| **Hybrid Retrieval** | Combining vector similarity search with keyword-based (BM25) search for better recall |
| **Deterministic Extractor** | Regex-based data extraction that bypasses LLM for 100% accurate enumeration queries |
| **Synthetic Chunk** | Consolidation of related content scattered across multiple chunks into a single comprehensive chunk |
