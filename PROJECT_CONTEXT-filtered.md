1. Project Overview
Name: CoCo (Columban College Information Kiosk)
Description:
CoCo is a Retrieval-Augmented Generation (RAG) campus information chatbot designed for kiosk-style deployment (Raspberry Pi 5). It answers questions using ingested campus documents and provides deterministic directory/wayfinding responses.
Primary Goals
•	Answer campus questions strictly from ingested documents (policies, awards, programs, etc.).
•	Provide directory/location answers deterministically (no LLM hallucination).
•	Refuse when retrieval or grounding is insufficient.
•	Default to campus knowledge first; only fall back to general AI when explicitly allowed.
Primary Entrypoint
•	campus_rag_chatbot/app.py (FastAPI server, routing, handlers)
________________________________________
2. Tech Stack
Backend
•	Python 3.11 (required for Piper TTS)
•	FastAPI + Uvicorn
•	LangChain
•	OpenAI Chat model (gpt-4o-mini)
•	OpenAI Embeddings
Retrieval
•	FAISS (local, persisted under campus_rag_chatbot/vector_store/)
•	Hybrid retrieval:
o	70% vector similarity
o	30% keyword term-coverage scoring
Frontend
•	Static HTML/CSS/JS served by FastAPI (campus_rag_chatbot/static/)
Storage
•	FAISS vector store: campus_rag_chatbot/vector_store/
•	Document registry: campus_rag_chatbot/document_registry.json
•	Debug settings: campus_rag_chatbot/data/debug_settings.json
•	Welcome config: campus_rag_chatbot/data/welcome_config.json
•	Ad settings: campus_rag_chatbot/data/ad_settings.json
•	Voice settings: campus_rag_chatbot/data/voice_settings.json
•	Metadata index: campus_rag_chatbot/data/metadata_index.json
•	Advertisement images: campus_rag_chatbot/images/
•	Logs/events: campus_rag_chatbot/logs/
________________________________________
2.1 Project Directory Structure
•	campus_rag_chatbot/ : Core application package (FastAPI, Logic)
•	scripts/ : Utility scripts for debugging, testing, and maintenance
•	reports/ : Analysis logs, validation reports, and text artifacts
•	whisper.cpp/ : External dependency for offline Speech-to-Text (STT) optimized for ARM64
•	question_generator/ : Tools for generating synthetic Q&A pairs for testing
•	ui_design/ : Kiosk UI sandbox for frontend design iteration
•	PROJECT_CONTEXT.md : Primary architectural documentation
•	pi-setup.sh : Raspberry Pi setup script (primary deployment)
•	win-setup.ps1 : Windows setup script (development/testing)
•	WINDOWS_SETUP_INSTRUCTIONS.txt : Windows setup guide
________________________________________
3. High-Level Architecture
Request Flow
1.	Input Layer (Text or Voice)
o	Text: Direct POST /chat
o	Voice: Audio → STT (Whisper) → Text (Phase 32)
2.	app.py:
o	Directory detection (deterministic)
o	Retrieval-first routing
o	Campus RAG answering (single retrieval pipeline)
o	Optional general fallback (unless RAG-only mode is enabled)
3.	LLM is invoked directly with validated chunks (no second retrieval).
4.	Structured response returned to frontend.
o	Voice: Text Response → TTS (Piper) → Audio Out (Phase 32)

Key Modules
•	API & routing: app.py
•	Response orchestration: response_orchestrator.py (Phase 44)
•	Voice Modality: voice/ package (orchestrator, STT/TTS services)
•	Ingestion & FAISS: document_manager.py
•	Hybrid scoring + grounding: retrieval_validator.py
•	Confidence scoring: confidence_scorer.py
•	Structured answers: response_formatter.py
•	Intent detection: intent_classifier.py
•	Deterministic extractors: entity_extractors/ (deans, awards, dates, contacts)
•	Observability: event_tracker.py, query_logger.py
________________________________________
4. Core Design Rules (Critical)
These must not be violated:
•	Retrieval-first routing: Always attempt document retrieval + grounding before general AI.
•	Single retrieval pipeline (Phase 17C):
The LLM must use exactly the same chunks that were hybrid-ranked and validated. No hidden second retrieval.
•	Mandatory grounding for campus answers:
Query terms must appear in top chunks OR semantic override criteria met (Phase 20: similarity ≥ 0.75 + length ≥ 300).
•	Unified RAG architecture:
Directory queries follow the same orchestrator pipeline as all other queries.
•	Confidence gating:
o	Campus answers require ≥ MEDIUM confidence.
o	All queries go through LLM synthesis.
•	Kiosk UX:
Frontend renders structured_answer.full_answer directly (no expand/collapse).
•	Never invent facts:
System prompt enforces "answer only from provided context; otherwise refuse."
________________________________________
5. Retrieval Pipeline (Current Production Flow)
5.1 Ingestion
1.	Load documents (.pdf, .txt, .docx)
2.	Chunk with RecursiveCharacterTextSplitter
o	chunk_size = 500
o	chunk_overlap = 50
3.	Normalize text (NFKC + lowercase + whitespace collapse)
4.	Embed with OpenAI embeddings
5.	Store in FAISS
6.	Save metadata in document_registry.json
________________________________________
5.2 Query-Time Retrieval (Phase 17A + 17C)
1.	Normalize query
2.	FAISS similarity search:
o	RETRIEVAL_TOP_K = 8
o	RELEVANCE_SCORE_THRESHOLD = 0.5
3.	Extract query terms (stopwords removed, plural handling)
4.	Compute keyword scores (term coverage + frequency bonus)
5.	Hybrid score:
6.	hybrid = 0.7 * vector + 0.3 * keyword
7.	Re-rank by hybrid score
8.	Grounding validation (Phase 20):
o	Keyword mode: Top 4 chunks must contain query terms
o	Semantic mode: Override if similarity ≥ 0.75 AND length ≥ 300 chars
9.	Confidence scoring (HIGH / MEDIUM / LOW)
10.	Context hygiene (Phase 17C + Phase 19):
o	Drop chunks with hybrid_score < 0.6 (fallback if all removed)
o	Expand each selected chunk with ±1 neighbor chunk (Phase 19: heals split lists, tracks metadata)
11.	Build final context from validated chunks
12.	Direct LLM call (llm.invoke) with:
o	System rules
o	Context
o	Conversation history
13.	Structured answer + sources built from the same chunks
________________________________________
6. Answer Formatting & UX
•	API returns:
o	answer (plain text, full)
o	structured_answer:
	direct_answer (summary)
	full_answer (complete)
	key_details
	notes
	disclaimer
•	Frontend (kiosk mode):
o	Displays structured_answer.full_answer
o	Shows confidence badge, mode, and sources
________________________________________
7. Directory System (RAG-Based)
•	Regex-based detection ("where is…", "how do I get to…", etc.)
•	RAG-based resolution via unified orchestrator pipeline
•	All 220 campus locations stored in RAG-optimized PDF document

Architecture
•	Directory queries go through response_orchestrator.process_query()
•	Same hybrid retrieval + grounding as all other queries
•	LLM synthesizes natural language response from retrieved context
•	Fully document-driven approach

Document Format
•	Self-contained paragraphs with aliases embedded ("also known as")
•	Grouped by building for optimal retrieval
•	Landmarks and directions included in paragraph text

Features
•	Follow-up resolution using session context
•	Grounding validation prevents hallucination
•	Graceful refusal when location not found in documents
________________________________________
8. Admin & Developer Tools
Admin
•	/admin UI
•	Document upload/delete
•	Analytics endpoints:
o	/admin/analytics
o	/admin/analytics/recent
•	Advertisement Panel management (Phase 48):
o	Upload/delete slideshow images
o	Configure auto-rotation interval
o	Toggle panel visibility
o	Endpoints: /admin/ads/list, /admin/ads/upload, /admin/ads/delete, /admin/ads/settings
•	Welcome Message configuration (Phase 49):
o	Edit welcome text with markdown-style formatting
o	Configure welcome image (CoCo logo)
o	Endpoint: /admin/welcome
Developer
•	/dev UI
•	RAG-only mode toggle:
o	When enabled, system refuses instead of falling back to general AI.
•	Response Metadata Toggle (Phase 50-51):
o	Controls visibility of confidence, score, sources, mode badges
o	Separate and independent from Debug Panel toggle
o	Server-authoritative (applies immediately without page refresh)
o	Setting included in each response (metadata_visible field)
•	Debug Panel Toggle (Phase 39B, 51):
o	Shows LLM model, retrieval mode, chunks retrieved, grounding status, timing
o	Works for all query types including directory RAG fallback
o	Admin toggle in Developer section (/admin#developer)
________________________________________
9. Key Configuration Values
Retrieval
•	RETRIEVAL_TOP_K = 8
•	RELEVANCE_SCORE_THRESHOLD = 0.5
•	MIN_HYBRID_SCORE_FOR_CONTEXT = 0.6
Hybrid
•	Vector weight: 0.7
•	Keyword weight: 0.3
•	MIN_GROUNDING_TERMS = 1
Confidence
•	HIGH ≥ 0.75 avg similarity + max ≥ 0.80
•	MEDIUM ≥ 0.55
•	Directory requires HIGH
•	Campus requires MEDIUM
Memory
•	Window size: 5
•	Session timeout: 30 minutes
•	Admin session: 8 hours
________________________________________
10. Completed Phases (Summary)
•	Phase 1–3: Core RAG + ingestion foundations
•	Phase 4–5: Grounding + confidence scoring
•	Phase 6: Campus vs general routing
•	Phase 7: Admin document management
•	Phase 13: Conversation memory
•	Phase 15: Document clarification
•	Phase 16: Observability + analytics
•	Phase 17A: Hybrid retrieval + grounding
•	Phase 17A.1: Developer RAG-only mode
•	Phase 17A.2: Retrieval-first routing
•	Phase 17C: Single retrieval pipeline, enumeration stability, adjacent chunk expansion, k=8
•	Phase 18.0: Entity-centric chunk consolidation (synthetic chunks for structured lists)
•	Phase 18.1: Multi-stage text normalization pipeline (5-stage PDF artifact cleanup)
•	Phase 18.2: Deterministic enumeration extraction (intent detection + regex-based entity extraction)
•	Phase 19: Contiguous context reconstruction (neighbor chunk expansion with metadata tracking)
•	Phase 20: Semantic grounding for long-form content (confidence-based grounding override)
•	Phase 21: Semantic trust injection for verified long-form content
•	Phase 21.1: Synthetic prayer consolidation (fixes truncated prayer responses)
•	Phase 22: Appendix-aware chunking (larger max_size for appendix sections)
•	Phase 23: Metadata validation and observability (schema validation + statistics logging)
•	Phase 24: Generic consolidation framework (config-driven consolidation engine)
•	Phase 25: Metadata index for fast filtering (O(1) chunk lookups)
•	Phase 26: RRF hybrid retrieval (industry-standard Reciprocal Rank Fusion)
•	Phase 27: Awards extractor + deans extractor fixes (deterministic enumeration)
•	Phase 28: Query synonym expansion (domain-specific term mapping)
•	Phase 29: Chunk diversity in results (section-based deduplication)
•	Phase 30: Negative examples to grounding (entity confusion detection)
•	Phase 31: Event dates & office contact extractors (additional deterministic extractors)
•	Phase 32: Voice infrastructure foundation (STT/TTS services, offline-first design)
•	Phase 33: Voice API layer (rate limiting, error codes, health monitoring, WebSocket)
•	Phase 34: Frontend voice UI (mic button, state machine, audio recording/playback)
•	Phase 36: Admin sidebar navigation + voice configuration panel
•	Phase 37: Voice provider configuration enhancement (edge-tts primary, pricing labels, fallback selection)
•	Phase 38: Google Cloud STT with usage monitoring (60-min quota tracking)
•	Phase 39: Admin-configurable cloud credentials & real-time debugging panel
•	Phase 40: Silent TTS with implicit interruption (background audio, auto-stop on input)
•	Phase 41: Voice bug fixes & Python 3.11 migration
•	Phase 42: Windows setup & UI enhancements (fullscreen, auto-focus, TTS full response)
•	Phase 44: LLM-as-Final-Synthesizer architecture (4-layer orchestration, semantic relevance scoring)
•	Phase 45: Response Style Policy (query analyzer, kiosk-friendly hints, LaTeX stripping)
•	Phase 46: Arithmetic Query Processing (input preprocessor, deterministic math engine, STT artifact cleanup)
•	Phase 48: Advertisement Panel (admin slideshow, navigation, visibility toggle)
•	Phase 49: Welcome Message System (admin-configurable text and image)
•	Phase 50: Response Metadata Visibility Toggle (separate from Debug Panel)
•	Phase 50B: Mode badges controlled by metadata visibility toggle
•	Phase 51: Developer Settings Consistency Fix (immediate toggle effect, debug panel for directory queries)
•	Phase 53: RPi Runtime Optimization (runtime-only requirements, import guards)
________________________________________
11. Recent Phases Details
Phase 19 — Contiguous Context Reconstruction
•	Goal: Fix long-form content fragmentation (hymns, prayers, policies) by expanding retrieved chunks with adjacent neighbors
•	Implementation:
o	Enhanced _expand_with_adjacent_chunks() from Phase 17C
o	Added metadata tracking (expanded=True, expanded_chunk_ids, expansion_method)
o	Implemented size cap (2000 chars) with sentence-boundary truncation
o	Added _truncate_at_sentence_boundary() helper for intelligent truncation
o	PHASE19 logging with expansion statistics
•	Results:
o	Prayer query: 664 chars (up from partial content)
o	Context expansion: typical 140-240% of original size
o	No regressions in dean enumeration or directory queries
•	Files: campus_rag_chatbot/app.py (lines 802-889)

Phase 20 — Semantic Grounding for Long-Form Content
•	Goal: Allow grounding to pass for high-confidence long-form content without literal keyword matches
•	Problem: Phase 19 expansion worked but keyword-only grounding too strict for semantic matches
•	Implementation:
o	Added check_semantic_grounding_override() function
o	Criteria: similarity ≥ 0.75 AND content_length ≥ 300 chars
o	Updated GroundingResult dataclass with grounding_mode field ("keyword" | "semantic")
o	Enhanced validate_grounding() with allow_semantic_override parameter
o	Added grounding_mode to ChatResponse API model
o	Industry-aligned: gates on confidence + substance, not implementation details
•	Results:
o	Prayer query: 710 chars, grounding_mode="semantic" ✅
o	Dean enumeration: 447 chars, grounding_mode="keyword" ✅ (no regression)
o	Directory queries: grounding_mode="keyword" ✅ (no regression)
o	3/4 acceptance tests pass, 4/4 grounding modes correct
•	Configuration:
o	SEMANTIC_SIMILARITY_THRESHOLD = 0.75
o	MIN_SEMANTIC_CONTENT_LENGTH = 300
•	Files:
o	campus_rag_chatbot/retrieval_validator.py (semantic override logic)
o	campus_rag_chatbot/app.py (ChatResponse model, call sites)

Phase 21 — Semantic Trust Injection
•	Goal: Fix LLM refusals on verified long-form content (hymns, prayers)
•	Problem: LLM refused to output hymn lyrics even when grounding passed
•	Implementation:
o	Added semantic_trust_prefix injection in handle_campus_query()
o	When grounding_mode == "semantic", inject trust instructions at prompt start
o	VERIFIED CONTENT NOTICE tells LLM content is authentic
o	Placed BEFORE critical rules to override default refusal behavior
•	Files: campus_rag_chatbot/app.py (lines 1186-1195)

Phase 21.1 — Synthetic Prayer Consolidation
•	Goal: Fix truncated prayer responses (was 4 fragmented chunks)
•	Implementation:
o	Added consolidate_prayer_chunks() in entity_consolidation.py
o	Two-pass detection: anchor pattern + continuation patterns
o	Creates synthetic chunk with chunk_id=-2, entity_type='prayer'
o	Consolidates 4 prayer fragments into single 607-char chunk
•	Files: campus_rag_chatbot/entity_consolidation.py

Phase 22 — Appendix-Aware Chunking
•	Goal: Prevent fragmentation of appendix content at ingestion time
•	Implementation:
o	Added is_appendix_section() helper for appendix detection
o	Modified group_elements_by_section() to flag appendix sections
o	Modified merge_related_admin_sections() for boundary enforcement
o	Appendix sections use max_size=2000 instead of 800
o	Added is_appendix and appendix_id metadata fields
•	Results:
o	6 appendix sections detected and isolated
o	Hymn: single chunk (510 chars)
o	Prayer: single chunk (584 chars)
•	Files: campus_rag_chatbot/document_manager.py

Phase 23 — Metadata Validation
•	Goal: Add observability and catch ingestion issues
•	Implementation:
o	Defined REQUIRED_METADATA schema (7 required fields)
o	Added validate_chunk_metadata() for per-chunk validation
o	Added validate_all_chunks() with error/warning logging
o	Added log_metadata_statistics() for post-ingestion stats
o	Integrated into ingest_document() pipeline
•	Results:
o	0 errors, 404 warnings ("General Information" sections)
o	Statistics logged: chunks, synthetic, appendix, sections, sizes
•	Files: campus_rag_chatbot/document_manager.py

Phase 24 — Generic Consolidation Framework
•	Goal: Replace hardcoded consolidation functions with config-driven engine
•	Problem: Adding new entity types (hymn, awards) required code changes
•	Implementation:
o	Created consolidation_rules.json with declarative rules
o	Created ConsolidationEngine class with pattern type handlers
o	Two pattern types: "semantic" (deans) and "anchor_continuation" (prayer)
o	Updated document_manager.py to use engine instead of hardcoded functions
o	Deprecated entity_consolidation.py with backward-compatible wrappers
•	Configuration:
o	Rules defined in data/consolidation_rules.json
o	Embedded fallback rules if config file not found
o	Supports: required_patterns, anchor_patterns, exclude_patterns, continuation patterns
•	Results:
o	Same synthetic chunks created (deans=-1, prayer=-2)
o	No regression: 29/32 golden tests passing (90.6%)
o	Adding new entity types now requires only config changes
•	Files:
o	campus_rag_chatbot/data/consolidation_rules.json
o	campus_rag_chatbot/consolidation_engine.py
o	campus_rag_chatbot/document_manager.py (integration)

Phase 25 — Metadata Index for Fast Filtering
•	Goal: Enable O(1) lookups by metadata fields instead of O(n) docstore iteration
•	Problem: Adjacent chunk expansion iterated entire docstore for each lookup
•	Implementation:
o	Created MetadataIndex class with build/save/load methods
o	Indexes by: chunk_id, section, section_title, page, document
o	Tracks synthetic and appendix chunks separately
o	Auto-builds from vector store, persists to JSON
o	Integrated into document ingestion pipeline
o	Used for fast adjacent chunk lookup in Phase 19 expansion
•	Performance:
o	Find chunk by ID: O(n) → O(1)
o	Adjacent chunk lookup: O(n) per chunk → O(1) per chunk
o	Section/page queries now possible
•	Results:
o	749 chunks indexed, 266 sections, 143 pages
o	2 synthetic chunks, 7 appendix chunks tracked
o	No regression in golden tests
•	Files:
o	campus_rag_chatbot/metadata_index.py
o	campus_rag_chatbot/data/metadata_index.json (auto-generated)
o	campus_rag_chatbot/document_manager.py (build after ingestion)
o	campus_rag_chatbot/app.py (load at startup, use for lookups)

Phase 26 — RRF Hybrid Retrieval
•	Goal: Replace linear weighted scoring with industry-standard Reciprocal Rank Fusion
•	Problem: Linear weighted scoring (0.7*vector + 0.3*keyword) assumes comparable score scales
•	Implementation:
o	Added compute_rrf_scores() function for rank-based fusion
o	RRF formula: rrf_score = 1/(k + rank_vector) + 1/(k + rank_keyword)
o	Updated HybridScore dataclass with vector_rank, keyword_rank, scoring_method fields
o	Modified combine_hybrid_scores() to support both "linear" and "rrf" methods
o	Added RRF score normalization to [0,1] range for compatibility
•	Configuration:
o	HYBRID_SCORING_METHOD = "rrf" (can revert to "linear")
o	RRF_K = 60 (industry standard smoothing constant)
•	Benefits:
o	Rank-based, not score-based (automatic normalization)
o	More robust to varying score distributions
o	Industry standard (Elasticsearch, Pinecone, Weaviate)
•	Results:
o	Golden tests: 29/32 passing (90.6%, no regression)
o	Deans enumeration: unchanged, correct ranking
o	Directory queries: unchanged, correct mode routing
•	Files:
o	campus_rag_chatbot/retrieval_validator.py (RRF scoring logic)
o	campus_rag_chatbot/app.py (configuration + call sites)

Phase 27 — Awards Extractor + Deans Fixes
•	Goal: Add deterministic extraction for awards/honors queries
•	Implementation:
o	Created entity_extractors/awards.py following deans.py pattern
o	Three-layer architecture: is_awards_enumeration_query(), extract_awards_from_text(), format_awards_list()
o	Fixed deans extractor for single-line concatenated content (title pattern splitting)
o	Improved dean filtering with role/college pattern matching
•	Results:
o	Awards enumeration: deterministic extraction
o	Deans enumeration: handles edge cases better
o	Golden tests: 29/32 (90.6%, no regression)
•	Files:
o	campus_rag_chatbot/entity_extractors/awards.py
o	campus_rag_chatbot/entity_extractors/deans.py (fixes)

Phase 28 — Query Synonym Expansion
•	Goal: Improve retrieval recall via domain-specific term expansion
•	Problem: Queries like "Where is the CR?" didn't match "restroom" in documents
•	Implementation:
o	Created CAMPUS_SYNONYMS dictionary (~40 bidirectional mappings)
o	Added expand_with_synonyms() function for term expansion
o	Integrated into extract_query_terms() before keyword scoring
o	Categories: locations, administrative, financial, academic terms
•	Examples:
o	library ↔ lib
o	cr ↔ restroom, comfort, bathroom
o	tuition ↔ payment, fees
o	cashier ↔ treasurer, payment
•	Results:
o	Golden tests: 29/32 (90.6%, no regression)
o	Better recall for informal/abbreviated queries
•	Files:
o	campus_rag_chatbot/retrieval_validator.py (CAMPUS_SYNONYMS, expand_with_synonyms)

Phase 29 — Chunk Diversity in Results
•	Goal: Prevent same-section dominance in top-K results
•	Problem: Multiple chunks from same section could crowd out diverse content
•	Implementation:
o	Added apply_section_diversity() function
o	MAX_CHUNKS_PER_SECTION = 3 (limits chunks per section)
o	Applied after hybrid scoring, before context building
o	Also added apply_mmr_diversity() for future use (Maximal Marginal Relevance)
•	Results:
o	Golden tests: 29/32 (90.6%, no regression)
o	More diverse retrieval results
•	Files:
o	campus_rag_chatbot/retrieval_validator.py (diversity functions)
o	campus_rag_chatbot/app.py (integration)

Phase 30 — Negative Examples to Grounding
•	Goal: Detect and refuse on entity confusion (semantic neighbor confusion)
•	Problem: Query "Dean's List" could retrieve "Team Leadership Award" content
•	Implementation:
o	Created CONFUSION_PAIRS dictionary mapping target entities to their semantic neighbors
o	Added detect_entity_confusion() function to scan top-K for confusion entities
o	Added get_confusion_refusal_message() for specific refusal messages
o	Integrated into validate_grounding() pipeline
•	Examples:
o	"dean's list" confusion with: team leadership, leadership award, excellence award
o	"deans" confusion with: dean's list, dean's lister
o	"library" confusion with: bookstore
•	Results:
o	Golden tests: 29/32 (90.6%, no regression)
o	More accurate refusals when semantic confusion detected
•	Files:
o	campus_rag_chatbot/retrieval_validator.py (confusion detection)
o	campus_rag_chatbot/app.py (integration)

Phase 31 — Event Dates & Office Contact Extractors
•	Goal: Add deterministic extractors for event dates and office contacts
•	Implementation:
o	Created entity_extractors/dates.py for event date/time extraction
	is_event_date_query(): Intent detection for schedule/event queries
	extract_events_from_text(): Extracts dates, times, platforms, event names
	format_event_list(): Canonical event list output
	Supports: "January 30, 2026", "9:00 AM", Zoom/Facebook platforms
o	Created entity_extractors/contacts.py for office location extraction
	is_contact_query(): Intent detection for contact/office queries
	extract_contacts_from_text(): Extracts office names, locations, staff
	format_contact_list(): Canonical contact info output
	Privacy by design: Personal phone/email not stored
o	Updated entity_extractors/__init__.py with new exports
o	Integrated into app.py after awards extraction
•	Results:
o	Golden tests: 29/32 (90.6%, no regression)
o	Event queries: deterministic date/time extraction
o	Contact queries: office location info (not personal contacts)
•	Files:
o	campus_rag_chatbot/entity_extractors/dates.py
o	campus_rag_chatbot/entity_extractors/contacts.py
o	campus_rag_chatbot/entity_extractors/__init__.py
o	campus_rag_chatbot/app.py (integration)

Phase 32 — Voice Infrastructure Foundation
•	Goal: Add STT/TTS voice integration infrastructure for kiosk deployment
•	Architecture: Voice is a MODALITY LAYER, not a decision layer. All RAG guarantees preserved.
•	Implementation:
o	Created voice/ package with modular service architecture
o	voice/config.py: Configuration management with environment variables
o	voice/audio_utils.py: Audio format conversion and validation
o	voice/stt_service.py: Speech-to-Text service with automatic fallback
o	voice/tts_service.py: Text-to-Speech service with text optimization
o	voice/voice_orchestrator.py: Coordinates STT -> Chat -> TTS flow
o	voice/engines/: Engine implementations
	whisper_cpp.py: Offline STT using Whisper.cpp (ARM64 optimized)
	whisper_openai.py: Cloud fallback using OpenAI Whisper API
	piper_tts.py: Offline TTS using Piper (neural network voices)
	espeak_tts.py: Fast fallback TTS using espeak-ng
	edge_tts.py: Microsoft Edge TTS fallback (no system dependencies)
o	voice_routes.py: FastAPI endpoints (/voice/status, /voice/transcribe, /voice/synthesize, /voice/chat)
o	Integrated into app.py with startup initialization
•	Key Features:
o	Offline-first design (Whisper.cpp + Piper TTS)
o	Automatic engine fallback on failure (Piper → edge-tts)
o	Confidence-based text input fallback prompt
o	Temporary audio storage with TTL (5 minutes)
o	Voice event logging for analytics
o	16-bit PCM audio normalization for Whisper compatibility
•	Results:
o	Golden tests: 28-29/32 (no regression from voice integration)
o	/voice/status endpoint operational
o	Voice services initialize cleanly (models require separate download)
•	Files:
o	campus_rag_chatbot/voice/ (new package)
o	campus_rag_chatbot/voice_routes.py
o	campus_rag_chatbot/app.py (integration)

Phase 33 — Voice API Layer
•	Goal: Enhance voice API with production-ready features
•	Implementation:
o	Standardized error codes (VoiceErrorCode enum) for consistent error handling
o	Rate limiting per endpoint (transcribe: 30/min, synthesize: 60/min, chat: 20/min)
o	Audio file validation with security checks (format detection, size limits, injection prevention)
o	/voice/health endpoint for monitoring systems with component status and metrics
o	WebSocket /voice/stream endpoint for streaming transcription
o	Request metrics tracking (success/error counts per endpoint)
o	Audio storage metrics (stored/retrieved/expired counts)
•	Key Features:
o	Client identification via IP/X-Forwarded-For for rate limiting
o	Automatic format detection from magic bytes
o	Text length validation for TTS (max 2000 chars)
o	Uptime tracking and version reporting
o	Component-level health status (healthy/degraded/unhealthy)
•	Results:
o	Golden tests: 28-29/32 (no regression)
o	All voice endpoints operational
o	Health endpoint shows detailed component status
•	Files:
o	campus_rag_chatbot/voice_routes.py (enhanced)
o	tests/test_voice_api.py (new integration tests)

Phase 34 — Frontend Voice UI
•	Goal: Complete voice user interface for kiosk frontend
•	Implementation:
o	Voice state machine (IDLE, LISTENING, PROCESSING, RESPONDING, ERROR)
o	Mic button with visual feedback and CSS animations
o	Audio recording via MediaRecorder API (WebM/MP4 formats)
o	/voice/chat integration for voice-to-chat flow
o	TTS audio playback with waveform visualization
o	Audio visualizer canvas for recording feedback
o	API response field mapping (transcribed_text, audio_url, flat response fields)
•	Key Features:
o	Touch-friendly 70px circular mic button
o	State-specific colors (green=listening, orange=processing, blue=speaking)
o	Pulse animations during recording
o	Auto-stop after 30 seconds
o	Stop button to cancel TTS playback
o	Graceful fallback to text-only when voice unavailable
o	Real-time audio visualizer during recording
•	Results:
o	Golden tests: 28/32 (no regression)
o	All voice UI components functional
o	Browser compatibility: Chrome, Firefox, Edge, Safari 14.1+
•	Files:
o	campus_rag_chatbot/static/index.html (voice elements)
o	campus_rag_chatbot/static/style.css (voice CSS)
o	campus_rag_chatbot/static/app.js (voice JavaScript)

Phase 36 — Admin Sidebar Navigation + Voice Configuration Panel
•	Goal: Modernize admin UI with sidebar navigation and add voice provider management
•	Implementation:
o	Replaced tab-based navigation with persistent sidebar layout
o	Section-based routing with URL hash support (#analytics, #upload, #documents, #voice)
o	New Voice Configuration section for STT/TTS provider management
o	Provider cards showing engine status (online/offline), model paths, local/cloud indicators
o	Save configuration button to persist voice settings
o	Responsive design with collapsible sidebar for mobile
•	Key Features:
o	Single-page admin experience with smooth section transitions
o	Visual provider selection with radio buttons
o	Real-time provider status from /voice/status endpoint
o	Configuration persistence via /admin/voice/config endpoint
•	Results:
o	Improved admin UX with clear navigation
o	Voice provider management accessible to non-technical admins
o	Golden tests: no regression
•	Files:
o	campus_rag_chatbot/static/admin.html (sidebar structure, voice section)
o	campus_rag_chatbot/static/admin.css (sidebar styles, voice card styles)
o	campus_rag_chatbot/static/admin.js (navigation logic, voice config handlers)

Phase 37 — Voice Provider Configuration Enhancement
•	Goal: Enhance voice provider selection with pricing labels, selectability rules, and explicit fallback selection
•	Problem: Admin could select engines that don't work as primary; no visibility into pricing tiers
•	Implementation:
o	Extended ProviderInfo dataclass with new fields:
	is_selectable: Controls whether provider can be selected as primary
	pricing_tier: "free" or "paid" classification
	status_label: Display text for non-selectable providers
	can_be_fallback: Whether provider can serve as fallback engine
	is_fallback_active: Current fallback selection state
o	Extended VoiceSettings with fallback provider fields
o	Updated STT/TTS provider definitions with selectability rules:
	whisper.cpp: selectable, free, can be fallback
	whisper-openai: NOT selectable, paid, status="Cloud - Not Operational"
	piper: selectable, free, can be fallback
	edge-tts: selectable, free, can be fallback
	openai-tts: NOT selectable, paid, status="Cloud - Not Operational"
o	Added edge-tts support as primary TTS engine in tts_service.py
o	Added validation in app.py to reject non-selectable providers
o	Added fallback validation rules (must differ from primary, must be free)
•	Admin UI Changes:
o	Pricing badges: Green "FREE" / Yellow "PAID" labels on each provider
o	Non-selectable providers shown with dashed border, reduced opacity, no radio button
o	Status labels shown for non-operational cloud providers
o	Fallback dropdown for each service type (STT/TTS)
o	Fallback dropdown excludes current primary and paid providers
•	Results:
o	Edge-TTS works as primary TTS engine
o	Cloud providers visible but not selectable (with clear messaging)
o	Admins can explicitly choose fallback engine
o	Clear pricing visibility prevents surprise costs
o	Golden tests: no regression
•	Files:
o	campus_rag_chatbot/voice/provider_registry.py (extended data models)
o	campus_rag_chatbot/voice/tts_service.py (edge-tts primary support)
o	campus_rag_chatbot/app.py (VoiceConfigUpdate model, validation)
o	campus_rag_chatbot/static/admin.html (fallback dropdowns)
o	campus_rag_chatbot/static/admin.css (pricing badges, status labels)
o	campus_rag_chatbot/static/admin.js (rendering, fallback logic)

Phase 38 — Google Cloud STT with Usage Monitoring
•	Goal: Add Google Cloud Speech-to-Text as STT option with quota tracking
•	Implementation:
o	Created voice/engines/google_cloud_stt.py for Google Cloud STT integration
o	Created voice/usage_tracker.py for tracking monthly usage
o	60-minute free tier quota with automatic monthly reset
o	Usage rounded UP to next second per Google billing rules
o	Admin UI: usage progress bar, credential status display
o	Endpoints: /admin/voice/usage, /admin/voice/credentials/status
•	Results:
o	Google Cloud STT operational when credentials configured
o	Usage tracking persists across restarts
o	Admin can monitor quota consumption
•	Files:
o	campus_rag_chatbot/voice/engines/google_cloud_stt.py
o	campus_rag_chatbot/voice/usage_tracker.py
o	campus_rag_chatbot/app.py (endpoints)
o	campus_rag_chatbot/static/admin.html (usage display)

Phase 39 — Admin-Configurable Cloud Credentials & Debug Panel
•	Goal: Allow admin to input/update cloud credentials via UI + add real-time debug panel
•	Implementation:
o	Phase 39A: Secure encrypted credential storage (AES-256-GCM with PBKDF2)
o	Credential input forms in admin UI for OpenAI API key, Google Cloud JSON
o	Live reload: credentials apply immediately without server restart
o	Phase 39B: Real-time debug panel showing per-request technical details
o	DebugInfo model: LLM provider, retrieval mode, grounding status, timing
o	Admin toggle to enable/disable debug visibility for all users
o	Debug panel shows STT/TTS engines for voice requests
•	Key Features:
o	Credentials encrypted at rest, never logged
o	Atomic file writes for crash safety
o	Debug info includes: LLM model, chunks retrieved, grounding mode, timing (ms)
o	Collapsible debug panel below each response
•	Results:
o	Admins can configure cloud credentials without SSH access
o	Debug panel shows comprehensive request metadata
o	Works for both text and voice requests
•	Files:
o	campus_rag_chatbot/credential_manager.py (encryption/storage)
o	campus_rag_chatbot/app.py (DebugInfo model, debug_info population)
o	campus_rag_chatbot/voice_routes.py (VoiceChatResponse with debug_info)
o	campus_rag_chatbot/static/admin.html (Developer section, credential forms)
o	campus_rag_chatbot/static/admin.js (toggle handlers, credential handlers)
o	campus_rag_chatbot/static/app.js (renderDebugPanel function)
o	campus_rag_chatbot/static/style.css (debug panel styles)

Phase 40 — Silent TTS with Implicit Interruption
•	Goal: Redesign TTS UX - no visual overlay, auto-stop on user input
•	Problem: Previous TTS showed "Speaking..." overlay that blocked reading the response
•	Implementation:
o	Removed voiceIndicator div and stop button from HTML
o	TTS audio plays silently in background via hidden <audio> element
o	Created centralized interruptTTS() function (idempotent, safe to call multiple times)
o	Created initTTSInterruption() to set up event listeners
o	Speech auto-stops on: text input focus/click/typing, send button, Enter key, voice button
o	Modified setVoiceState(RESPONDING) to not show visual indicators
o	Modified playTTSResponse() and synthesizeAndPlayTTS() for silent playback
•	Key Features:
o	User can read response while listening
o	No explicit "Stop" button needed - any input action stops speech
o	Follows voice assistant industry patterns (Google Assistant, Alexa)
o	Silent failure on TTS errors (no UI disruption)
•	Results:
o	Cleaner UI during TTS playback
o	More natural voice interaction flow
o	No stuck states or race conditions
•	Testing: reports/phase40_silent_tts_testing.txt (12 test cases)
•	Files:
o	campus_rag_chatbot/static/app.js (interruptTTS, initTTSInterruption, silent playback)
o	campus_rag_chatbot/static/index.html (voiceIndicator removed)
o	campus_rag_chatbot/static/style.css (voice indicator styles removed)

Phase 41 — Voice Bug Fixes & Python 3.11 Migration
•	Goal: Fix voice integration bugs and resolve Piper TTS compatibility issues
•	Problem: Multiple voice issues discovered during testing:
o	Google STT not used despite being configured (fell back to whisper.cpp)
o	Piper TTS broken on Python 3.13 (espeakbridge import error)
o	voice_routes.py attribute access error during service reload
•	Implementation:
o	Fixed app.py startup to load voice settings from voice_settings.json via ProviderRegistry
o	Fixed piper_tts.py: synthesize_wav now uses wave.open() wrapper (required by piper-tts API)
o	Fixed voice_routes.py: Changed _chat_handler/_event_tracker to chat_handler/event_tracker
o	Created Python 3.11 virtual environment (venv311/) for Piper compatibility
o	Created requirements_py311.txt (removed audioop-lts, not needed for Python <3.13)
o	Installed google-cloud-speech package for Google Cloud STT
•	Python Version:
o	Python 3.13: Piper TTS broken (espeakbridge module incompatibility)
o	Python 3.11: All voice engines working correctly
o	Migration preserves all functionality, no code changes required
•	Results:
o	Google Cloud STT: Working (0.86-0.98 confidence)
o	Piper TTS: Working (3-18s audio synthesis)
o	Whisper.cpp: Working (fallback STT)
o	edge-tts: Working (fallback TTS)
o	All voice integrations verified
•	Rollback: See backups/python313_env_backup/ROLLBACK_INSTRUCTIONS.md
•	Files:
o	campus_rag_chatbot/app.py (voice settings loading at startup)
o	campus_rag_chatbot/voice/engines/piper_tts.py (wave.open wrapper fix)
o	campus_rag_chatbot/voice_routes.py (attribute name fixes)
o	venv311/ (Python 3.11 virtual environment)
o	requirements_py311.txt (Python 3.11 compatible requirements)
o	PYTHON311_MIGRATION_REPORT.txt (migration documentation)

Phase 42 — Windows Setup & UI Enhancements
•	Goal: Enable Windows development/testing and improve kiosk UI for RPi deployment
•	Implementation:
o	Created win-setup.ps1 PowerShell setup script (mirrors pi-setup.sh)
o	Created WINDOWS_SETUP_INSTRUCTIONS.txt with prerequisites and troubleshooting
o	Added fullscreen toggle button to kiosk UI (upper-right corner)
o	Disabled auto-focus on textbox to prevent virtual keyboard obstruction on RPi
o	Removed TTS 500-character truncation - TTS now reads full responses
o	Fixed debug panel to show actual TTS engine from X-TTS-Engine response header
o	Added platform-specific dependencies to requirements_py311.txt:
	python-magic-bin (Windows only, via sys_platform marker)
	edge-tts (cross-platform, was missing from requirements)
•	Key Features:
o	Cross-platform: Same codebase works on RPi and Windows
o	Fullscreen API for kiosk-mode display
o	TTS reads complete responses regardless of length
o	Debug panel accurately reflects which TTS engine synthesized audio
•	Files:
o	win-setup.ps1 (Windows setup script)
o	WINDOWS_SETUP_INSTRUCTIONS.txt (setup guide)
o	campus_rag_chatbot/static/index.html (fullscreen button, autofocus removed)
o	campus_rag_chatbot/static/style.css (fullscreen styles)
o	campus_rag_chatbot/static/app.js (fullscreen toggle, TTS engine from header)
o	campus_rag_chatbot/voice/tts_service.py (removed truncation)
o	campus_rag_chatbot/voice_routes.py (increased max_text_length to 10000)
o	campus_rag_chatbot/requirements_py311.txt (edge-tts, python-magic-bin)

Phase 44 — LLM-as-Final-Synthesizer Architecture
•	Goal: Unify all response paths through LLM for consistent natural language output
•	Implementation:
o	4-layer architecture: Governance → Retrieval → Extraction → LLM Synthesis
o	Created response_orchestrator.py with ResponseOrchestrator class
o	Response modes: EXTRACTOR_AUTHORITATIVE, RAG_AUTHORITATIVE, RAG_SUPPLEMENTED, GENERAL_KNOWLEDGE
o	Semantic relevance scoring (HIGH, MEDIUM, LOW) prevents lexical confusion
o	All paths terminate in LLM for polished output
•	Key Features:
o	Deterministic extractors provide facts, LLM provides natural language
o	RAG chunks passed with semantic relevance context
o	Style hints for response formatting
•	Files:
o	campus_rag_chatbot/response_orchestrator.py

Phase 45 — Response Style Policy
•	Goal: Optimize responses for kiosk and voice UX
•	Implementation:
o	Created query_analyzer.py for query type detection
o	Query types: MATH, GREETING, DEFINITION, CONVERSATIONAL, FACTUAL, PROCEDURAL
o	Style hints: concise, kiosk-friendly formatting
o	LaTeX stripping for voice compatibility
o	Response length optimization for spoken output
•	Key Features:
o	Detects query intent and adjusts response style
o	Strips mathematical notation unsuitable for TTS
o	Provides natural conversational responses
•	Files:
o	campus_rag_chatbot/query_analyzer.py
o	campus_rag_chatbot/response_orchestrator.py (style integration)

Phase 46 — Arithmetic Query Processing
•	Goal: Deterministic arithmetic evaluation bypassing LLM
•	Implementation:
o	Created input_preprocessor.py for STT artifact cleanup
o	Created math_engine.py for secure AST-based evaluation
o	Number normalization: "5,000" → "5000", "five" → "5"
o	Supports: +, -, *, /, **, parentheses, word operators
o	Voice-friendly output: "The answer is 42."
•	Key Features:
o	No eval() - secure AST parsing
o	STT artifact handling (filler words, false starts)
o	Integration with response orchestrator
•	Files:
o	campus_rag_chatbot/input_preprocessor.py
o	campus_rag_chatbot/math_engine.py

Phase 48 — Advertisement Panel
•	Goal: Admin-configurable slideshow in chatbot UI info panel
•	Implementation:
o	Added image upload/delete endpoints in app.py
o	Created ad_settings.json for configuration persistence
o	Created images/ directory for ad storage
o	Slideshow with configurable auto-rotation interval
o	Left/right navigation zones for manual browsing
o	Visibility toggle to show/hide entire panel
•	Admin UI:
o	Image gallery management (upload, delete, reorder)
o	Interval configuration (default: 5 seconds)
o	Panel visibility toggle
•	Endpoints: /admin/ads/list, /admin/ads/upload, /admin/ads/delete, /admin/ads/settings
•	Files:
o	campus_rag_chatbot/app.py (endpoints)
o	campus_rag_chatbot/data/ad_settings.json
o	campus_rag_chatbot/images/ (storage directory)
o	campus_rag_chatbot/static/admin.html (advertisement section)
o	campus_rag_chatbot/static/admin.js (handlers)
o	campus_rag_chatbot/static/app.js (slideshow rendering)

Phase 49 — Welcome Message System
•	Goal: Admin-editable welcome message displayed at chat start
•	Implementation:
o	Created welcome_config.json for message persistence
o	Added /api/welcome and /admin/welcome endpoints
o	Markdown-style formatting support (newlines → <br>, **bold**)
o	Optional image display (CoCo logo)
o	Frontend renders welcome message on page load
•	Key Features:
o	Persisted across server restarts
o	Rich text formatting without full markdown parser
o	Image URL configuration for branding
•	Files:
o	campus_rag_chatbot/data/welcome_config.json
o	campus_rag_chatbot/app.py (endpoints)
o	campus_rag_chatbot/static/admin.html (welcome section)
o	campus_rag_chatbot/static/app.js (welcome rendering)

Phase 50 — Response Metadata Visibility Toggle
•	Goal: Separate control for response metadata (confidence, sources) from debug panel
•	Problem: Users wanted to hide metadata without losing debug panel for development
•	Implementation:
o	Added debug_settings.json with show_metadata field
o	Added /admin/settings/metadata endpoint
o	Frontend reads metadata_visible from response (server-authoritative)
o	Metadata includes: confidence badge, similarity score, sources, mode badges
•	Key Features:
o	Independent from Debug Panel toggle
o	Server-authoritative setting (no page refresh needed)
o	metadata_visible field in ChatResponse
•	Files:
o	campus_rag_chatbot/data/debug_settings.json
o	campus_rag_chatbot/app.py (ChatResponse model, endpoint)
o	campus_rag_chatbot/static/admin.html (toggle in Developer section)
o	campus_rag_chatbot/static/app.js (conditional rendering)

Phase 50B — Mode Badges Under Metadata Toggle
•	Goal: Include mode badges in metadata visibility control
•	Problem: Mode badges ("Based on campus documents") shown even when metadata hidden
•	Implementation:
o	Wrapped mode badge rendering in metadata visibility conditional
o	Both streaming and non-streaming paths updated
•	Files:
o	campus_rag_chatbot/static/app.js (lines 467-474, 720-725)

Phase 51 — Developer Settings Consistency Fix
•	Goal: Fix immediate toggle effect and debug panel for directory queries
•	Problems:
o	Response Metadata toggle required page refresh
o	Debug Panel not triggering for directory RAG fallback queries
•	Implementation:
o	Server-authoritative: metadata_visible included in each ChatResponse
o	Frontend reads from response instead of cached variable
o	Added debug_info building to directory RAG fallback path
o	DebugInfo populated for all query types
•	Key Features:
o	Toggles apply immediately without page refresh
o	Debug panel shows info for: directory queries, campus RAG, general
o	Consistent behavior across all query paths
•	Files:
o	campus_rag_chatbot/app.py (ChatResponse model, debug_info for RAG fallback)
o	campus_rag_chatbot/response_orchestrator.py (metadata_visible parameter)
o	campus_rag_chatbot/static/app.js (read from response)
________________________________________
12. Phase 18 Details (Entity Consolidation)
Phase 18.0 — Entity-Centric Chunk Consolidation
•	Goal: Guarantee complete entity enumeration (e.g., all deans) in single retrievable chunk
•	Implementation:
o	Synthetic chunk creation for structured lists
o	Consolidates all dean entries into one chunk
o	Deterministic retrieval at rank #2
•	Files: document_manager.py (consolidation logic)

Phase 18.1 — Multi-Stage Text Normalization Pipeline
•	Goal: Remove PDF parsing artifacts from chunks before embedding
•	Implementation:
o	5-stage pipeline: NFKC → hyphen cleanup → duplicate char removal → whitespace normalization → final polish
o	Applied to both regular and synthetic chunks
o	Clean synthetic chunk: 438 chars, artifact-free
•	Files: document_manager.py (normalize_text function)

Phase 18.2 — Deterministic Enumeration Extraction
•	Goal: 100% deterministic enumeration without LLM guessing
•	Implementation:
o	Rule-based intent detection (is_dean_enumeration_query)
o	Regex-based entity extraction (extract_deans_from_text)
o	Name/college normalization
o	Formatted output (format_dean_list)
o	Integrated into handle_campus_query() before LLM call
•	Files:
o	campus_rag_chatbot/entity_extractors/__init__.py
o	campus_rag_chatbot/entity_extractors/deans.py
o	app.py (integration at line ~1069-1115)

Phase 18 Results
•	Before: 4/6 deans extracted (66.7%)
•	After: 6/6 deans extracted (100%)
•	Achievement: Clean synthetic chunk enables complete LLM extraction
•	Verification: All acceptance and regression tests passing
________________________________________
12. How to Run Locally
1.	Set env vars:
o	OPENAI_API_KEY
o	ADMIN_API_KEY
o	ADMIN_PASSWORD
2.	Install (use Python 3.11 for Piper TTS compatibility):
cd vibecoding_coco
# Use Python 3.11 virtual environment
venv311\Scripts\activate
cd campus_rag_chatbot
pip install -r requirements.txt
3.	Run:
# Option 1: With activated venv
python app.py

# Option 2: Direct path (no activation needed)
"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\venv311\Scripts\python.exe" app.py
4.	Access:
•	Chat: /
•	Admin: /admin
•	Dev tools: /dev
________________________________________
13. Current Production Status
Version: Phase 53 (RPi Runtime Optimization)
Python: 3.11.9 (required for Piper TTS - Python 3.13 has compatibility issues)
Virtual Environment: venv311/
Golden Tests: 32 test cases, 87.5% pass rate (28/32)
RAG Architecture: Hybrid RAG (vector + BM25 via RRF) with LLM-as-Final-Synthesizer (Phase 44)
Directory System: Unified RAG
Cross-Platform: Windows (win-setup.ps1) + Raspberry Pi (pi-setup.sh)

Requirements Files:
•	requirements.txt - Development/Windows (full dependencies)
•	requirements_rpi.txt - Full RPi install (ARM64 optimized)
•	requirements_rpi_runtime.txt - RPi runtime only (excludes ingestion packages)
Voice: Full frontend UI + API layer OPERATIONAL
•	STT: Google Cloud STT (primary), Whisper.cpp (fallback)
•	TTS: Piper (primary, offline), edge-tts (fallback)
•	Audio: WebM → 16-bit WAV conversion fixed
•	Admin: Provider selection, credential management, debug panel toggle
•	UX: Silent TTS playback with implicit interruption (Phase 40)
•	TTS: Full response reading without truncation (Phase 42)
Known Issues:
•	404 "General Information" section warnings (detection gaps in PDF parsing)
•	3-4 golden test failures (prayer content, school motto, tuition query routing - LLM variability)
•	Python 3.13 not supported (Piper TTS espeakbridge incompatibility) - use Python 3.11
•	Cloud providers require credential configuration via Admin UI

Voice Configuration (Phase 37-40):
•	Free engines: whisper.cpp (STT), piper (TTS), edge-tts (TTS)
•	Cloud engines: Google Cloud STT (60-min free tier), whisper-openai, openai-tts
•	Edge-TTS now works as primary TTS engine (not just fallback)
•	Explicit fallback selection available in Admin UI
•	Pricing badges (FREE/PAID) shown on all providers
•	Phase 39: Cloud credentials configurable via Admin UI
•	Phase 40: TTS plays silently, auto-stops on user input

Admin Features (Phase 48-49):
•	Advertisement Panel: Admin-configurable slideshow in chatbot UI
•	Welcome Message: Editable welcome text and image at chat start
•	Both features accessible via /admin UI

Developer Settings (Phase 50-51):
•	Response Metadata Toggle: Controls confidence, score, sources, mode badges
•	Debug Panel Toggle: Shows LLM/retrieval/grounding technical details
•	Both toggles independent, server-authoritative (immediate effect)
•	Debug panel works for all query types including directory queries
•	Settings persisted in data/debug_settings.json
Last Updated: 2026-02-20 (Phase 53 - RPi Runtime Optimization)
