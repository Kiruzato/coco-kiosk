"""
FastAPI Backend - Phase 5
==========================
Minimal API for campus information kiosk web interface.

Endpoints:
- POST /chat - Submit a question and get an answer
- POST /feedback - Submit user feedback
- POST /reset - Reset conversation session
- GET /health - Health check
"""

import os
import uuid
import secrets
import logging
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Header, Depends, Request, Response
from sse_starlette.sse import EventSourceResponse  # Phase 42: SSE for test harness streaming
import httpx  # Phase 42: Async HTTP client for internal API calls

# Phase 14.1: Set up logging for clarification flow debugging
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_classic.memory import ConversationBufferWindowMemory

# Load environment variables
load_dotenv()

# Import existing modules
from document_manager import DocumentManager
from confidence_scorer import (
    compute_confidence_score,
    ConfidenceLevel,
    should_answer_confidently
)
from query_logger import QueryLogger
from intent_classifier import (
    classify_intent,
    QueryIntent,
    safety_check_general_mode,
    CAMPUS_KEYWORDS,
    is_directory_query  # Phase 8
)
from text_normalizer import normalize_text, canonicalize_directory_query  # Text normalization for consistent retrieval
from entity_analyzer import check_entity_agreement, should_promote_confidence  # Entity-aware confidence promotion
from entity_registry import EntityRegistry  # Phase 9: Structured directory entities
from entity_manager import EntityManager  # Phase 55: Admin entity management with validation
from entity_resolver import extract_subject, resolve_entity, format_entity_response  # Phase 9: Entity resolution
from event_tracker import EventTracker, EventType  # Phase 16: Observability
from retrieval_validator import (  # Phase 17A: Hybrid retrieval & grounding
    extract_query_terms,
    compute_keyword_scores,
    combine_hybrid_scores,
    validate_grounding,
    get_grounding_refusal_message,
    get_confusion_refusal_message,  # Phase 30: Confusion detection
    apply_section_diversity  # Phase 29: Chunk diversity
)
from response_formatter import format_structured_answer, build_structured_answer  # Phase 17B/17B.1

# Phase 44: LLM-as-Final-Synthesizer Architecture
from response_orchestrator import ResponseOrchestrator, ResponseMode, SemanticRelevance

# Phase 49-50: Campus Query Engine (unified query handling)
try:
    from campus_query_parser import is_campus_query
    from campus_index import get_campus_index
    CAMPUS_QUERY_ENGINE_ENABLED = True
except ImportError as e:
    CAMPUS_QUERY_ENGINE_ENABLED = False
    logger.warning(f"[CQE] Campus Query Engine not available: {e}")
    def is_campus_query(query):
        return False
    def get_campus_index(path=None):
        return None

# Phase 32: Voice Integration
import voice_routes

# Phase 39A: Credential Management
from credential_manager import init_credential_manager, get_credential_manager

# ==============================================================================
# CONFIGURATION
# ==============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
if not ADMIN_API_KEY:
    raise ValueError("ADMIN_API_KEY environment variable not set. Please add it to .env file.")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD environment variable not set. Please add it to .env file.")

# Phase 39A: Initialize credential manager and load encrypted credentials
# This must happen after ADMIN_PASSWORD is loaded but before validating OPENAI_API_KEY
try:
    _cred_manager = init_credential_manager(ADMIN_PASSWORD, Path(__file__).parent)
    if _cred_manager.is_available():
        _applied = _cred_manager.apply_to_environment()
        if _applied > 0:
            logger.info(f"[STARTUP] Applied {_applied} credentials from encrypted storage")
except Exception as e:
    logger.warning(f"[STARTUP] Credential manager init failed: {e}")

PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"
LOG_DIR = PROJECT_ROOT / "logs"
FEEDBACK_LOG_PATH = LOG_DIR / "feedback.jsonl"

# API settings
RETRIEVAL_TOP_K = 8  # Phase 17C: Increased from 4 for complete enumeration
RELEVANCE_SCORE_THRESHOLD = 0.5
MEMORY_WINDOW_SIZE = 5
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.MEDIUM
MIN_CONFIDENCE_DIRECTORY = ConfidenceLevel.HIGH  # Phase 8: Stricter for location queries

# Phase 17A: Hybrid retrieval settings
HYBRID_VECTOR_WEIGHT = 0.7       # Weight for vector similarity score (linear method)
HYBRID_KEYWORD_WEIGHT = 0.3      # Weight for BM25 keyword score (linear method)
MIN_GROUNDING_TERMS = 1          # Minimum query terms required in chunks

# Phase 26: RRF (Reciprocal Rank Fusion) hybrid retrieval
# RRF is industry standard (Elasticsearch, Pinecone) - normalizes by rank position
HYBRID_SCORING_METHOD = "rrf"    # "linear" (Phase 17A) or "rrf" (Phase 26)
RRF_K = 60                       # RRF smoothing constant (higher = more equal rank weights)

# Session settings (chat sessions)
SESSION_TIMEOUT_MINUTES = 30
sessions: Dict[str, Dict] = {}  # In-memory session storage

# Admin session settings
ADMIN_SESSION_DURATION = timedelta(hours=8)
admin_sessions: Dict[str, datetime] = {}  # {session_token: expiry_datetime}

# Phase 17A.1: Developer RAG-only mode (in-memory, not persisted)
rag_only_mode: bool = False

# Phase 39B: Debug panel mode (persisted to debug_settings.json)
DEBUG_SETTINGS_PATH = PROJECT_ROOT / "data" / "debug_settings.json"
debug_mode_enabled: bool = False


def load_debug_settings() -> bool:
    """Load debug mode from settings file."""
    global debug_mode_enabled
    try:
        if DEBUG_SETTINGS_PATH.exists():
            import json
            with open(DEBUG_SETTINGS_PATH, 'r') as f:
                data = json.load(f)
            debug_mode_enabled = data.get('debug_enabled', False)
            return debug_mode_enabled
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to load debug settings: {e}")
    return False


def save_debug_settings(enabled: bool) -> bool:
    """Save debug mode to settings file."""
    global debug_mode_enabled
    try:
        import json
        DEBUG_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'debug_enabled': enabled,
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
        with open(DEBUG_SETTINGS_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        debug_mode_enabled = enabled
        return True
    except Exception as e:
        logger.error(f"[DEBUG] Failed to save debug settings: {e}")
        return False


# Load debug settings at startup
load_debug_settings()

# ==============================================================================
# INITIALIZE SYSTEM
# ==============================================================================

# Initialize document manager
doc_manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)
doc_manager.load_vector_store()

if doc_manager.vector_store is None:
    raise RuntimeError("No vector store found. Please ingest documents first.")

# Phase 25: Load metadata index
from metadata_index import MetadataIndex
metadata_index = MetadataIndex()
if not metadata_index.load():
    logger.info("[PHASE25] Building metadata index from vector store...")
    metadata_index.build_from_vector_store(doc_manager.vector_store)
    metadata_index.save()

# Initialize LLM
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0,
    openai_api_key=OPENAI_API_KEY
)

# Initialize Response Orchestrator (Phase 44: LLM-as-Final-Synthesizer)
# Singleton instance reused across all requests
response_orchestrator = ResponseOrchestrator(
    llm=llm,
    doc_manager=doc_manager,
    config={
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "relevance_threshold": RELEVANCE_SCORE_THRESHOLD,
        "min_grounding_terms": MIN_GROUNDING_TERMS,
        "semantic_threshold_high": 0.78,
        "semantic_threshold_medium": 0.65
    }
)
logger.info("[PHASE44] ResponseOrchestrator initialized (singleton)")

# Initialize query logger
query_logger = QueryLogger(log_dir=LOG_DIR)

# Initialize event tracker for observability (Phase 16)
event_tracker = EventTracker(log_dir=LOG_DIR)

# Initialize entity registry for directory queries (Phase 9)
ENTITY_REGISTRY_PATH = PROJECT_ROOT / "data" / "directory_entities.json"
entity_registry = EntityRegistry(str(ENTITY_REGISTRY_PATH))

# Initialize Campus Query Engine index (Phase 49-50)
_cqe_index = None
if CAMPUS_QUERY_ENGINE_ENABLED:
    try:
        _cqe_index = get_campus_index(str(ENTITY_REGISTRY_PATH))
        logger.info(f"[CQE] Campus Query Engine initialized: {len(_cqe_index.rooms)} rooms, "
                   f"{len(_cqe_index.buildings)} buildings indexed")
    except Exception as e:
        logger.error(f"[CQE] Failed to initialize Campus Query Engine: {e}")
        CAMPUS_QUERY_ENGINE_ENABLED = False

# Phase 55: Initialize EntityManager for admin operations with validation + index rebuild
entity_manager = EntityManager(
    registry=entity_registry,
    index_path=str(ENTITY_REGISTRY_PATH)
)


def rebuild_cqe_index() -> dict:
    """
    Rebuild the CQE index from JSON after entity changes.

    Returns:
        dict with index statistics
    """
    global _cqe_index

    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "CQE not enabled"}

    try:
        from campus_index import CampusQueryIndex
        _cqe_index = CampusQueryIndex()
        _cqe_index.load_from_flat_entities(str(ENTITY_REGISTRY_PATH))

        stats = {
            "rooms": len(_cqe_index.rooms),
            "buildings": len(_cqe_index.buildings),
            "campuses": len(_cqe_index.campuses),
            "outdoor_locations": len(_cqe_index.outdoor_locations),
            "aliases": (
                len(_cqe_index.alias_to_room) +
                len(_cqe_index.alias_to_building) +
                len(_cqe_index.alias_to_campus)
            )
        }
        logger.info(f"[CQE] Index rebuilt: {stats}")
        return stats
    except Exception as e:
        logger.error(f"[CQE] Index rebuild failed: {e}")
        return {"error": str(e)}

# ==============================================================================
# FASTAPI APP
# ==============================================================================

app = FastAPI(
    title="Campus Information Kiosk API",
    description="RAG-powered campus information chatbot with confidence scoring",
    version="5.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 32: Include voice routes
app.include_router(voice_routes.router)

# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None


class Source(BaseModel):
    """Source citation model."""
    document_name: str
    section: str
    chunk_id: int


class StructuredAnswer(BaseModel):
    """Structured answer for frontend rendering - Phase 17B.1."""
    direct_answer: str
    full_answer: str  # Complete answer for "Show more" expansion
    key_details: List[str] = []
    notes: Optional[str] = None
    disclaimer: Optional[str] = None


class DebugInfo(BaseModel):
    """Debug information for developer panel - Phase 39B."""
    # Provider info
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

    # Voice info (if voice request)
    stt_engine: Optional[str] = None
    stt_fallback_used: bool = False
    tts_engine: Optional[str] = None
    tts_fallback_used: bool = False

    # Retrieval info
    retrieval_mode: str = "hybrid"
    retrieval_method: str = "rrf"
    chunks_retrieved: int = 0
    top_chunk_score: float = 0.0

    # Routing info
    intent_classified: str = ""
    routing_path: str = ""

    # Grounding info
    query_terms: List[str] = []
    grounding_passed: bool = True
    grounding_mode: str = "keyword"
    matched_terms: List[str] = []

    # Timing (ms)
    timing: Dict[str, float] = {}

    # Deterministic extractor
    extractor_used: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    answer: str  # Keep for backward compatibility
    structured_answer: Optional[StructuredAnswer] = None  # Phase 17B.1: Structured format
    sources: List[Source]
    confidence_level: str
    confidence_score: float
    grounding_mode: str = "keyword"  # Phase 20: "keyword" | "semantic"
    rejected: bool
    timestamp: str
    mode: str  # "campus" | "general" | "clarification"
    debug_info: Optional[DebugInfo] = None  # Phase 39B: Debug panel data


class FeedbackRequest(BaseModel):
    """Feedback request model."""
    session_id: str
    query_id: str
    is_helpful: bool
    comment: Optional[str] = None


class ResetRequest(BaseModel):
    """Reset session request model."""
    session_id: str


# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

def create_session() -> Dict:
    """Create a new conversation session."""
    memory = ConversationBufferWindowMemory(
        k=MEMORY_WINDOW_SIZE,
        memory_key="chat_history",
        return_messages=True,
        output_key="answer"
    )

    return {
        "memory": memory,
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
        "query_count": 0,
        "conversation_context": {
            "last_intent": None,
            "last_entity_id": None,
            "last_entity_name": None,
            "last_campus": None,
            # Phase 14: Disambiguation state (directory)
            "awaiting_disambiguation": False,
            "disambiguation_candidates": [],
            "disambiguation_query": None,
            # Phase 14.1: Failure handling
            "disambiguation_attempt_count": 0,
            # Phase 15: Document clarification state
            "doc_clarification_active": False,
            "doc_clarification_sources": [],
            "doc_clarification_query": None,
            "doc_last_source": None,
        }
    }


def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, Dict]:
    """
    Get existing session or create new one.

    Args:
        session_id: Optional session ID

    Returns:
        Tuple of (session_id, session_data)
    """
    # Clean up expired sessions
    cleanup_expired_sessions()

    # Create new session if no ID provided
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = create_session()
        return session_id, sessions[session_id]

    # Get existing session or create new one
    if session_id not in sessions:
        sessions[session_id] = create_session()

    # Update last activity
    sessions[session_id]["last_activity"] = datetime.now()

    return session_id, sessions[session_id]


def cleanup_expired_sessions():
    """Remove sessions that have been inactive for too long."""
    timeout = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    now = datetime.now()

    expired = [
        sid for sid, session in sessions.items()
        if now - session["last_activity"] > timeout
    ]

    for sid in expired:
        del sessions[sid]


# ==============================================================================
# CONVERSATION CONTEXT MANAGEMENT (Phase 13)
# ==============================================================================

def update_conversation_context(session: Dict, intent: str, entity_id: str = None,
                                 entity_name: str = None, campus: str = None):
    """Update session conversation context after a successful high-confidence answer.

    Phase 14.1: Uses field-level updates to preserve disambiguation state fields
    instead of replacing the entire context dict.
    """
    context = session.get("conversation_context", {})
    context["last_intent"] = intent
    context["last_entity_id"] = entity_id
    context["last_entity_name"] = entity_name
    context["last_campus"] = campus
    session["conversation_context"] = context


def get_conversation_context(session: Dict) -> Dict:
    """Get the conversation context for follow-up query handling."""
    return session.get("conversation_context", {})


def is_followup_query(query: str) -> bool:
    """Detect if a query appears to be a follow-up question."""
    followup_patterns = [
        "what time", "when does", "when is", "is it open", "is it closed",
        "how do i get there", "where is it", "what floor", "what building",
        "how about", "what about", "and the", "also", "its ", "it's ",
        "their", "the same", "that place", "this place", "that one", "this one"
    ]
    query_lower = query.lower()
    return any(pattern in query_lower for pattern in followup_patterns)


def is_topic_change(query: str, context: Dict) -> bool:
    """
    Detect if user is changing topics (abandoning current disambiguation).

    Phase 14.1: Returns True if user appears to be asking about something else
    while disambiguation is pending.

    Args:
        query: The user's current query
        context: The conversation context dict

    Returns:
        True if this looks like a topic change, False otherwise
    """
    # Only relevant if disambiguation is pending
    if not context.get("awaiting_disambiguation"):
        return False

    query_lower = query.lower().strip()

    # Explicit reset/cancel phrases
    reset_phrases = [
        "never mind", "nevermind", "forget it", "different question",
        "something else", "cancel", "start over", "new question"
    ]
    if any(phrase in query_lower for phrase in reset_phrases):
        return True

    # If query contains a new directory question, it's a topic change
    directory_keywords = [
        "where is", "where's", "find the", "location of",
        "how to get to", "how do i get to", "where can i find"
    ]
    if any(kw in query_lower for kw in directory_keywords):
        return True

    return False


# ==============================================================================
# DOCUMENT CLARIFICATION - Phase 15
# ==============================================================================

def detect_document_ambiguity(
    retrieval_results: List[tuple],
    similarity_threshold: float = 0.05
) -> tuple[bool, List[str]]:
    """
    Detect if multiple documents scored similarly (ambiguous).

    Phase 15: This triggers informational clarification for document queries
    when no single document dominates the results.

    Args:
        retrieval_results: List of (doc, score) tuples from retrieval
        similarity_threshold: Max difference to consider "similar"

    Returns:
        (is_ambiguous, list_of_source_names)
    """
    if len(retrieval_results) < 2:
        return False, []

    # Group by source document (using document_name metadata field)
    source_scores = {}
    for doc, score in retrieval_results:
        source = doc.metadata.get("document_name", doc.metadata.get("source", "Unknown"))
        if source not in source_scores:
            source_scores[source] = []
        source_scores[source].append(score)

    # Get max score per source
    source_max = {src: max(scores) for src, scores in source_scores.items()}

    if len(source_max) < 2:
        return False, []  # Single source, not ambiguous

    # Check if top sources are within threshold
    sorted_sources = sorted(source_max.items(), key=lambda x: x[1], reverse=True)
    top_score = sorted_sources[0][1]

    similar_sources = [
        src for src, score in sorted_sources
        if top_score - score <= similarity_threshold
    ]

    return len(similar_sources) > 1, similar_sources[:4]  # Max 4 sources


def handle_document_clarification(
    query: str,
    similar_sources: List[str],
    session_id: str,
    session: Dict,
    retrieval_results: List[tuple]
) -> ChatResponse:
    """
    Handle ambiguous document queries by presenting source options.

    Phase 15: Uses softer, informational style - may provide summary with follow-up.
    Unlike directory clarification, this is not blocking.
    """
    # Phase 42: Debug timing
    _debug_start = time.perf_counter()

    logger.info(f"[DOC_CLARIFICATION] Multiple sources for '{query}': {similar_sources}")

    # Phase 16: Track clarification event
    event_tracker.track(
        EventType.CLARIFICATION_TRIGGERED,
        session_id=session_id,
        clarification_type="document",
        reason="ambiguity",
        num_sources=len(similar_sources[:4])
    )

    # Build informational clarification message
    options = []
    for i, source in enumerate(similar_sources[:4], 1):
        # Extract filename from path
        display_name = os.path.basename(source).replace('.txt', '').replace('_', ' ').title()
        options.append(f"{i}. {display_name}")

    options_text = "\n".join(options)

    answer = (
        f"I found relevant information in multiple documents:\n\n"
        f"{options_text}\n\n"
        f"Which one would you like me to focus on? Or I can provide a general summary."
    )

    # Store document clarification state
    context = session["conversation_context"]
    context["doc_clarification_active"] = True
    context["doc_clarification_sources"] = similar_sources[:4]
    context["doc_clarification_query"] = query

    # Build clarification debug info
    _clarification_debug_info = None
    if debug_mode_enabled:
        _debug_timing = {
            'resolution_ms': round((time.perf_counter() - _debug_start) * 1000, 1),
            'total_ms': round((time.perf_counter() - _debug_start) * 1000, 1)
        }
        _clarification_debug_info = DebugInfo(
            llm_provider="deterministic",
            llm_model="pattern-match",
            retrieval_mode="document_index",
            retrieval_method="similarity_match",
            chunks_retrieved=len(similar_sources[:4]),
            intent_classified="clarification",
            routing_path="document_clarification",
            timing=_debug_timing
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[],
        confidence_level="Medium",
        confidence_score=50.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification",
        debug_info=_clarification_debug_info
    )


def handle_document_selection(
    selection: str,
    session: Dict,
    session_id: str
) -> Optional[str]:
    """
    Handle user's document source selection.

    Phase 15: Returns selected source path, "ALL" for summary mode, or None if no match.
    """
    context = session["conversation_context"]
    sources = context.get("doc_clarification_sources", [])

    if not sources:
        return None

    logger.info(f"[DOC_CLARIFICATION] Selection attempt: '{selection}'")

    selection_lower = selection.lower().strip()

    # Check for "summary" or "all" request
    if any(word in selection_lower for word in ["summary", "all", "general", "both"]):
        context["doc_clarification_active"] = False
        context["doc_last_source"] = None  # No specific source
        return "ALL"  # Special marker for summary mode

    # Number matching
    num_map = {
        "1": 0, "2": 1, "3": 2, "4": 3,
        "first": 0, "second": 1, "third": 2, "fourth": 3,
        "one": 0, "two": 1, "three": 2, "four": 3
    }

    selected_source = None

    if selection_lower in num_map:
        idx = num_map[selection_lower]
        if 0 <= idx < len(sources):
            selected_source = sources[idx]
    else:
        # Check if number word is in selection phrase
        for key, idx in num_map.items():
            if key in selection_lower.split():
                if 0 <= idx < len(sources):
                    selected_source = sources[idx]
                    break

    # Name matching
    if not selected_source:
        for source in sources:
            source_name = os.path.basename(source).lower().replace('.txt', '').replace('_', ' ')
            if selection_lower in source_name or source_name in selection_lower:
                selected_source = source
                break

    if selected_source:
        logger.info(f"[DOC_CLARIFICATION] Resolved to: {selected_source}")

        # Phase 16: Track successful document clarification resolution
        event_tracker.track(
            EventType.CLARIFICATION_RESOLVED,
            session_id=session_id,
            success=True,
            clarification_type="document"
        )

        context["doc_clarification_active"] = False
        context["doc_last_source"] = selected_source
        return selected_source

    logger.info(f"[DOC_CLARIFICATION] Selection failed")
    return None


def is_doc_topic_change(query: str, context: Dict) -> bool:
    """
    Detect if user is changing topics (abandoning document clarification).

    Phase 15: Returns True if user appears to be asking about something else
    while document clarification is pending.
    """
    # Only relevant if document clarification is pending
    if not context.get("doc_clarification_active"):
        return False

    query_lower = query.lower().strip()

    # Explicit reset/cancel phrases
    reset_phrases = [
        "never mind", "nevermind", "forget it", "different question",
        "something else", "cancel", "start over", "new question"
    ]
    if any(phrase in query_lower for phrase in reset_phrases):
        return True

    # If query contains a new directory question, it's a topic change
    directory_keywords = [
        "where is", "where's", "find the", "location of",
        "how to get to", "how do i get to", "where can i find"
    ]
    if any(kw in query_lower for kw in directory_keywords):
        return True

    return False


# ==============================================================================
# ADMIN AUTHENTICATION
# ==============================================================================

def cleanup_expired_admin_sessions():
    """Remove expired admin sessions."""
    now = datetime.now()
    expired = [token for token, expiry in admin_sessions.items() if now > expiry]
    for token in expired:
        del admin_sessions[token]


def create_admin_session() -> str:
    """Create a new admin session and return the token."""
    cleanup_expired_admin_sessions()
    token = secrets.token_urlsafe(32)
    admin_sessions[token] = datetime.now() + ADMIN_SESSION_DURATION
    return token


def validate_admin_session(token: str) -> bool:
    """Check if an admin session token is valid."""
    if not token or token not in admin_sessions:
        return False
    if datetime.now() > admin_sessions[token]:
        del admin_sessions[token]
        return False
    return True


def invalidate_admin_session(token: str):
    """Remove an admin session."""
    if token in admin_sessions:
        del admin_sessions[token]


async def verify_admin_session(request: Request):
    """
    Verify admin session for protected endpoints.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If session is missing or invalid

    Returns:
        True if authenticated
    """
    token = request.cookies.get("admin_session")
    if not validate_admin_session(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


# Legacy API key auth (kept for backwards compatibility)
async def verify_admin_api_key(x_api_key: str = Header(None)):
    """
    Verify admin API key for protected endpoints (legacy).

    Args:
        x_api_key: API key from X-API-Key header

    Raises:
        HTTPException: If API key is missing or invalid

    Returns:
        True if authenticated
    """
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/")
async def root():
    """Serve the frontend."""
    return FileResponse(PROJECT_ROOT / "static" / "index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    num_documents = len(doc_manager.list_documents())
    num_sessions = len(sessions)

    return {
        "status": "healthy",
        "documents_loaded": num_documents,
        "active_sessions": num_sessions,
        "timestamp": datetime.now().isoformat()
    }


# ==============================================================================
# RETRIEVAL-FIRST ROUTING - Phase 17A.2
# ==============================================================================

def attempt_document_retrieval(query: str) -> dict:
    """
    Attempt document retrieval and grounding validation.

    This is the first step in retrieval-first routing. Returns results
    that can be used to decide whether to use RAG or fall back to general AI.

    Returns:
        dict with keys:
        - is_grounded: bool - whether query terms appear in chunks
        - retrieval_results: list - hybrid-ranked (doc, score) tuples
        - grounding_result: GroundingResult object
        - confidence_level: ConfidenceLevel enum
        - confidence_score: float
        - query_terms: list - extracted meaningful terms
    """
    # Normalize query for consistent retrieval
    normalized_query = normalize_text(query)
    logger.info(f"[PHASE17C] attempt_document_retrieval: query='{query}', normalized='{normalized_query}'")

    # Retrieve with similarity scores
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        normalized_query,
        k=RETRIEVAL_TOP_K,
        score_threshold=RELEVANCE_SCORE_THRESHOLD
    )

    logger.info(f"[PHASE17C] Retrieved {len(retrieval_results)} chunks, scores: {[round(float(s),3) for _,s in retrieval_results[:8]]}")

    # Handle empty retrieval
    if not retrieval_results:
        return {
            "is_grounded": False,
            "retrieval_results": [],
            "grounding_result": None,
            "confidence_level": ConfidenceLevel.LOW,
            "confidence_score": 0.0,
            "query_terms": []
        }

    # Extract meaningful query terms for keyword matching
    query_terms = extract_query_terms(query)

    # Compute keyword scores for retrieved chunks
    retrieved_docs = [doc for doc, score in retrieval_results]
    keyword_scores = compute_keyword_scores(query_terms, retrieved_docs)

    # Combine vector and keyword scores, re-rank results
    # Phase 26: Support RRF and linear scoring methods
    hybrid_results, hybrid_details = combine_hybrid_scores(
        retrieval_results,
        keyword_scores,
        vector_weight=HYBRID_VECTOR_WEIGHT,
        keyword_weight=HYBRID_KEYWORD_WEIGHT,
        method=HYBRID_SCORING_METHOD,
        rrf_k=RRF_K
    )

    # Validate grounding: ensure query terms appear in retrieved chunks
    # Phase 20: Allow semantic override for high-confidence long-form content
    grounding_result = validate_grounding(
        query_terms,
        hybrid_results,
        min_term_matches=MIN_GROUNDING_TERMS,
        allow_semantic_override=True  # Phase 20
    )

    # Compute confidence
    similarity_scores = [float(score) for doc, score in hybrid_results]
    confidence_level, confidence_metrics = compute_confidence_score(
        similarity_scores=similarity_scores,
        min_chunks_retrieved=1
    )

    result = {
        "is_grounded": grounding_result.is_grounded if query_terms else True,
        "retrieval_results": hybrid_results,
        "grounding_result": grounding_result,
        "confidence_level": confidence_level,
        "confidence_score": confidence_metrics.get("confidence_score", 0.0),
        "query_terms": query_terms
    }
    logger.info(f"[PHASE17C] Retrieval result: grounded={result['is_grounded']}, "
                f"confidence={confidence_level.value}, score={result['confidence_score']}, "
                f"terms={query_terms}, matched={grounding_result.matched_terms if grounding_result else 'N/A'}")
    return result


def _expand_with_adjacent_chunks(docs, vector_store, max_size=2000) -> list:
    """
    Phase 19: Expand each retrieved chunk by merging its ±1 neighbors inline.

    When long-form content (hymns, prayers, policies) is split across chunk boundaries,
    this fetches adjacent chunks and merges them to restore semantic continuity.
    
    Args:
        docs: List of retrieved Document objects
        vector_store: FAISS vector store with docstore
        max_size: Maximum size for expanded chunk (chars), default 2000
    
    Returns:
        List of Document objects with expanded content and metadata
    """
    if not docs or not vector_store:
        return docs

    from langchain_core.documents import Document

    # Build set of already-retrieved chunk_ids
    existing_ids = {doc.metadata.get('chunk_id', -1) for doc in docs}

    # Collect all needed ±1 neighbors
    needed = {}  # chunk_id -> None (to be filled)
    doc_names = {}  # chunk_id -> document_name
    # Track which original chunk needs which neighbor
    prev_neighbors = {}  # original_chunk_id -> prev_chunk_id
    next_neighbors = {}  # original_chunk_id -> next_chunk_id
    for doc in docs:
        doc_name = doc.metadata.get('document_name', '')
        chunk_id = doc.metadata.get('chunk_id', -1)
        if chunk_id >= 0:
            prev_id = chunk_id - 1
            next_id = chunk_id + 1
            if prev_id >= 0 and prev_id not in existing_ids and prev_id not in needed:
                needed[prev_id] = None
                doc_names[prev_id] = doc_name
                prev_neighbors[chunk_id] = prev_id
            if next_id not in existing_ids and next_id not in needed:
                needed[next_id] = None
                doc_names[next_id] = doc_name
                next_neighbors[chunk_id] = next_id

    if not needed:
        return docs

    # Phase 25: Fetch needed neighbors using metadata index (O(1) per chunk)
    try:
        docstore = vector_store.docstore
        for chunk_id in needed.keys():
            # O(1) lookup using metadata index instead of O(n) docstore iteration
            docstore_id = metadata_index.get_docstore_id(chunk_id)
            if docstore_id:
                stored_doc = docstore.search(docstore_id)
                if stored_doc and hasattr(stored_doc, 'metadata'):
                    stored_name = stored_doc.metadata.get('document_name', '')
                    if stored_name == doc_names.get(chunk_id, ''):
                        needed[chunk_id] = stored_doc.page_content
    except Exception as e:
        logger.warning(f"[PHASE19] Adjacent chunk expansion failed: {e}")
        return docs

    # Merge each chunk with its ±1 neighbors (inline)
    expanded_docs = []
    expand_count = 0
    total_original_size = 0
    total_expanded_size = 0
    
    for doc in docs:
        chunk_id = doc.metadata.get('chunk_id', -1)
        parts = []
        expanded_chunk_ids = []

        # Prepend -1 neighbor if available
        prev_id = prev_neighbors.get(chunk_id)
        if prev_id is not None and needed.get(prev_id) is not None:
            parts.append(needed[prev_id])
            expanded_chunk_ids.append(prev_id)

        parts.append(doc.page_content)
        expanded_chunk_ids.append(chunk_id)

        # Append +1 neighbor if available
        next_id = next_neighbors.get(chunk_id)
        if next_id is not None and needed.get(next_id) is not None:
            parts.append(needed[next_id])
            expanded_chunk_ids.append(next_id)

        if len(parts) > 1:
            merged_content = " ".join(parts)
            original_size = len(doc.page_content)
            
            # Phase 19: Size cap with intelligent truncation
            if len(merged_content) > max_size:
                merged_content = _truncate_at_sentence_boundary(merged_content, max_size)
            
            # Phase 19: Enhanced metadata tracking
            new_metadata = dict(doc.metadata)
            new_metadata['expanded'] = True
            new_metadata['expanded_chunk_ids'] = expanded_chunk_ids
            new_metadata['expansion_method'] = 'phase19_adjacent'
            new_metadata['original_size'] = original_size
            new_metadata['expanded_size'] = len(merged_content)
            
            expanded_docs.append(Document(
                page_content=merged_content,
                metadata=new_metadata
            ))
            expand_count += 1
            total_original_size += original_size
            total_expanded_size += len(merged_content)
        else:
            expanded_docs.append(doc)

    if expand_count > 0:
        logger.info(f"[PHASE19] Expanded {expand_count}/{len(docs)} chunks with ±1 neighbors")
        logger.info(f"[PHASE19] Total context: {total_original_size} → {total_expanded_size} chars " +
                   f"({round(total_expanded_size/total_original_size*100)}% of original)")
    return expanded_docs


def _truncate_at_sentence_boundary(text: str, max_length: int) -> str:
    """
    Phase 19: Truncate text at sentence boundary without exceeding max_length.
    
    Preserves semantic completeness by cutting at sentence endings.
    """
    if len(text) <= max_length:
        return text
    
    # Find last sentence boundary before max_length
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    last_question = truncated.rfind('?')
    last_exclamation = truncated.rfind('!')
    
    boundary = max(last_period, last_question, last_exclamation)
    
    # Only use sentence boundary if it's reasonably close (at least 70% of max)
    if boundary > max_length * 0.7:
        return text[:boundary + 1]
    
    # Fallback: truncate at word boundary
    last_space = truncated.rfind(' ')
    if last_space > 0:
        return text[:last_space] + '...'
    
    return text[:max_length] + '...'


def _build_annotated_context(docs) -> str:
    """
    Phase 17C: Build LLM context with chunk ordering annotations.

    Chunks are sorted by document + chunk_id and labeled with sequential part numbers.
    Consecutive chunks are marked to help the LLM understand document continuity
    (e.g., a "Deans:" heading in Part 1 applies to names continuing in Part 2).
    """
    if not docs:
        return ""

    # Keep hybrid-ranked order: most relevant chunks first
    # This ensures the LLM sees the best-matching content prominently
    blocks = [doc.page_content for doc in docs]

    logger.info(f"[PHASE17C] Built context from {len(docs)} chunks")
    return "\n\n".join(blocks)


# ==============================================================================
# QUERY HANDLERS - Phase 6
# ==============================================================================

async def handle_campus_query(
    query: str,
    session_id: str,
    memory: ConversationBufferWindowMemory,
    intent_metadata: Dict,
    session: Dict = None,
    precomputed_retrieval: dict = None  # Phase 17A.2: Pre-computed retrieval results
) -> ChatResponse:
    """
    Handle campus query using existing RAG pipeline.

    This function implements the original campus RAG logic with:
    - Vector retrieval
    - Confidence scoring
    - Grounding validation
    - Source citation
    - Phase 15: Document ambiguity detection and clarification
    - Phase 17A.2: Can accept pre-computed retrieval results
    """
    # Phase 39B: Debug timing tracking
    _debug_timing = {}
    _debug_start = time.perf_counter()
    _retrieval_start = time.perf_counter()
    _extractor_used = None  # Track which deterministic extractor was used
    query_terms = []  # Initialize for debug_info
    grounding_result = None  # Initialize for debug_info

    # Phase 17A.2: Use pre-computed results if provided
    if precomputed_retrieval:
        retrieval_results = precomputed_retrieval["retrieval_results"]
        query_terms = precomputed_retrieval["query_terms"]
        grounding_result = precomputed_retrieval["grounding_result"]
        # Phase 39B: Mark retrieval as pre-computed (0ms)
        _debug_timing['retrieval_ms'] = 0.0
        # Skip to confidence calculation since retrieval is done
        logger.debug(f"[PHASE17A.2] Using pre-computed retrieval results")
    else:
        # Original flow: perform retrieval
        # Normalize query for consistent retrieval (case-insensitive matching)
        normalized_query = normalize_text(query)

        # Retrieve with similarity scores using normalized query
        retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
            normalized_query,
            k=RETRIEVAL_TOP_K,
            score_threshold=RELEVANCE_SCORE_THRESHOLD
        )

        # Phase 15: Check for document ambiguity
        if session:
            context = get_conversation_context(session)
            preferred_source = context.get("doc_last_source")

            if preferred_source:
                # Filter results to preferred source (using document_name metadata field)
                filtered_results = [
                    (doc, score) for doc, score in retrieval_results
                    if doc.metadata.get("document_name", doc.metadata.get("source")) == preferred_source
                ]
                if filtered_results:
                    retrieval_results = filtered_results
                    logger.info(f"[DOC_CLARIFICATION] Filtered to source: {preferred_source}")
            else:
                # Check for ambiguity (multiple documents scoring similarly)
                is_ambiguous, similar_sources = detect_document_ambiguity(retrieval_results)
                if is_ambiguous:
                    return handle_document_clarification(
                        query, similar_sources, session_id, session, retrieval_results
                    )

        # =========================================================================
        # Phase 17A: Hybrid Retrieval & Grounding Validation
        # =========================================================================
        # Extract meaningful query terms for keyword matching
        query_terms = extract_query_terms(query)
        logger.debug(f"[PHASE17A] Extracted query terms: {query_terms}")

        # Compute keyword scores for retrieved chunks
        retrieved_docs_for_scoring = [doc for doc, score in retrieval_results]
        keyword_scores = compute_keyword_scores(query_terms, retrieved_docs_for_scoring)

        # Combine vector and keyword scores, re-rank results
        # Phase 26: Support RRF and linear scoring methods
        hybrid_results, hybrid_details = combine_hybrid_scores(
            retrieval_results,
            keyword_scores,
            vector_weight=HYBRID_VECTOR_WEIGHT,
            keyword_weight=HYBRID_KEYWORD_WEIGHT,
            method=HYBRID_SCORING_METHOD,
            rrf_k=RRF_K
        )

        # Validate grounding: ensure query terms appear in retrieved chunks
        # Phase 20: Allow semantic override for high-confidence long-form content
        grounding_result = validate_grounding(
            query_terms,
            hybrid_results,
            min_term_matches=MIN_GROUNDING_TERMS,
            allow_semantic_override=True  # Phase 20
        )

        # If grounding fails, refuse with topic-specific message
        if not grounding_result.is_grounded and query_terms:
            logger.info(f"[PHASE17A] Grounding failed for query: '{query}' - "
                       f"terms {query_terms} not found in chunks")

            # Log grounding failure event
            event_tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="document")
            event_tracker.track(
                EventType.GROUNDING_FAILED,
                session_id=session_id,
                topic=grounding_result.topic,
                query_terms=query_terms,
                matched_terms=grounding_result.matched_terms,
                reason=grounding_result.reason
            )
            event_tracker.track(
                EventType.ANSWER_REFUSED,
                session_id=session_id,
                reason="grounding_failed"
            )

            # Phase 30: Use confusion-specific message if entity confusion detected
            if grounding_result.reason.startswith("entity_confusion:"):
                confusion_entity = grounding_result.reason.split(":", 1)[1]
                refusal_message = get_confusion_refusal_message(
                    grounding_result.topic, confusion_entity
                )
            else:
                refusal_message = get_grounding_refusal_message(grounding_result.topic)

            # Phase 39B: Build debug_info for grounding failure
            _grounding_debug_info = None
            if debug_mode_enabled:
                _debug_timing['retrieval_ms'] = round((time.perf_counter() - _retrieval_start) * 1000, 1)
                _debug_timing['total_ms'] = round((time.perf_counter() - _debug_start) * 1000, 1)
                _grounding_debug_info = DebugInfo(
                    llm_provider="openai",
                    llm_model="gpt-4o-mini",
                    retrieval_mode="hybrid",
                    retrieval_method="rrf",
                    chunks_retrieved=len(hybrid_results),
                    top_chunk_score=round(hybrid_results[0][1], 3) if hybrid_results else 0.0,
                    intent_classified=intent_metadata.get("intent", ""),
                    routing_path="retrieval→grounding_failed",
                    query_terms=query_terms,
                    grounding_passed=False,
                    grounding_mode=grounding_result.grounding_mode,
                    matched_terms=grounding_result.matched_terms,
                    timing=_debug_timing
                )

            return ChatResponse(
                session_id=session_id,
                answer=refusal_message,
                sources=[],
                confidence_level="LOW",
                confidence_score=0.0,
                rejected=True,
                timestamp=datetime.now().isoformat(),
                mode="campus",
                debug_info=_grounding_debug_info  # Phase 39B
            )

        # Use hybrid-ranked results for downstream processing
        retrieval_results = hybrid_results

        # Phase 39B: Record retrieval timing
        _debug_timing['retrieval_ms'] = round((time.perf_counter() - _retrieval_start) * 1000, 1)
        # =========================================================================

    # Phase 17C: Filter out low-scoring noise chunks before passing to LLM
    # After hybrid ranking, chunks without keyword matches score ~0.49 (noise)
    # while relevant chunks score ~0.79+ (keyword match boosted)
    MIN_HYBRID_SCORE_FOR_CONTEXT = 0.6
    filtered_results = [(doc, score) for doc, score in retrieval_results if score >= MIN_HYBRID_SCORE_FOR_CONTEXT]
    if not filtered_results:
        # Fallback: use all results if filtering removes everything
        filtered_results = retrieval_results
    logger.info(f"[PHASE17C] After hybrid filter: {len(filtered_results)} chunks (from {len(retrieval_results)})")

    # Phase 29: Apply section diversity to prevent same-section dominance
    diverse_results = apply_section_diversity(filtered_results)
    if len(diverse_results) < len(filtered_results):
        logger.info(f"[PHASE29] After diversity filter: {len(diverse_results)} chunks (from {len(filtered_results)})")
    retrieved_docs = [doc for doc, score in diverse_results]

    # Phase 17C: Expand with adjacent chunks to capture split lists
    retrieved_docs = _expand_with_adjacent_chunks(retrieved_docs, doc_manager.vector_store)

    # Convert to Python floats to avoid numpy type coercion issues
    similarity_scores = [float(score) for doc, score in retrieval_results]

    # Compute confidence (using hybrid scores now)
    confidence_level, confidence_metrics = compute_confidence_score(
        similarity_scores=similarity_scores,
        min_chunks_retrieved=1
    )

    # Check if we should answer (confidence validation)
    if not should_answer_confidently(confidence_level, MIN_CONFIDENCE_TO_ANSWER):
        answer = "I don't have verified campus information to answer that question confidently. The information I found has low relevance to your query. Please try rephrasing your question or ask about campus services, facilities, or policies."
        rejected = True
        sources = []
    else:
        # Phase 17C: Single retrieval pipeline - use validated chunks directly
        # Merge consecutive chunks from the same document to avoid split lists
        context = _build_annotated_context(retrieved_docs)

        # =====================================================================
        # Phase 18.2: Deterministic Enumeration Extraction
        # =====================================================================
        # For enumeration queries (e.g., "who are the deans"), bypass LLM
        # and use deterministic regex-based extraction for 100% accuracy
        from entity_extractors import is_dean_enumeration_query, extract_deans_from_text, format_dean_list
        
        if is_dean_enumeration_query(query):
            logger.info(f"[PHASE18.2] Dean enumeration query detected, using deterministic extraction")
            deans = extract_deans_from_text(context)

            if len(deans) >= 1:
                # Use deterministic extraction result (bypass LLM)
                answer = format_dean_list(deans)
                rejected = False
                _extractor_used = "deans"  # Phase 39B: Track extractor

                logger.info(f"[PHASE18.2] Extracted {len(deans)} deans deterministically")
                
                # Update conversation memory with deterministic result
                memory.save_context({"question": query}, {"answer": answer})
                
                # Extract sources from retrieved docs
                sources = []
                seen = set()
                for doc in retrieved_docs:
                    doc_name = doc.metadata.get('document_name', 'Unknown')
                    section = doc.metadata.get('section', 'Unknown')
                    chunk_id = doc.metadata.get('chunk_id', 0)
                    
                    key = f"{doc_name}:{section}:{chunk_id}"
                    if key not in seen:
                        sources.append(Source(
                            document_name=doc_name,
                            section=section,
                            chunk_id=chunk_id
                        ))
                        seen.add(key)
                
                # Skip LLM call - use deterministic extraction
                # Continue to logging section below
            else:
                # No deans found via extraction, fall back to LLM
                logger.info(f"[PHASE18.2] No deans extracted, falling back to LLM")
                # Continue with LLM flow below
        # =====================================================================

        # Phase 27: Awards Enumeration Extraction
        # =====================================================================
        # For awards enumeration queries, bypass LLM and use deterministic extraction
        if 'answer' not in locals() or answer is None:
            from entity_extractors import is_awards_enumeration_query, extract_awards_from_text, format_awards_list

            if is_awards_enumeration_query(query):
                logger.info(f"[PHASE27] Awards enumeration query detected, using deterministic extraction")
                awards = extract_awards_from_text(context)

                if len(awards) >= 1:
                    # Use deterministic extraction result (bypass LLM)
                    answer = format_awards_list(awards)
                    rejected = False
                    _extractor_used = "awards"  # Phase 39B: Track extractor

                    logger.info(f"[PHASE27] Extracted {len(awards)} awards deterministically")

                    # Update conversation memory with deterministic result
                    memory.save_context({"question": query}, {"answer": answer})

                    # Extract sources from retrieved docs
                    sources = []
                    seen = set()
                    for doc in retrieved_docs:
                        doc_name = doc.metadata.get('document_name', 'Unknown')
                        section = doc.metadata.get('section', 'Unknown')
                        chunk_id = doc.metadata.get('chunk_id', 0)

                        key = f"{doc_name}:{section}:{chunk_id}"
                        if key not in seen:
                            sources.append(Source(
                                document_name=doc_name,
                                section=section,
                                chunk_id=chunk_id
                            ))
                            seen.add(key)
                else:
                    # No awards found via extraction, fall back to LLM
                    logger.info(f"[PHASE27] No awards extracted, falling back to LLM")
        # =====================================================================

        # Phase 31: Event Dates Extraction
        # =====================================================================
        # For event/schedule queries, bypass LLM and use deterministic extraction
        if 'answer' not in locals() or answer is None:
            from entity_extractors import is_event_date_query, extract_events_from_text, format_event_list

            if is_event_date_query(query):
                logger.info(f"[PHASE31] Event date query detected, using deterministic extraction")
                events = extract_events_from_text(context)

                if len(events) >= 1:
                    # Use deterministic extraction result (bypass LLM)
                    answer = format_event_list(events)
                    rejected = False
                    _extractor_used = "events"  # Phase 39B: Track extractor

                    logger.info(f"[PHASE31] Extracted {len(events)} events deterministically")

                    # Update conversation memory with deterministic result
                    memory.save_context({"question": query}, {"answer": answer})

                    # Extract sources from retrieved docs
                    sources = []
                    seen = set()
                    for doc in retrieved_docs:
                        doc_name = doc.metadata.get('document_name', 'Unknown')
                        section = doc.metadata.get('section', 'Unknown')
                        chunk_id = doc.metadata.get('chunk_id', 0)

                        key = f"{doc_name}:{section}:{chunk_id}"
                        if key not in seen:
                            sources.append(Source(
                                document_name=doc_name,
                                section=section,
                                chunk_id=chunk_id
                            ))
                            seen.add(key)
                else:
                    # No events found via extraction, fall back to LLM
                    logger.info(f"[PHASE31] No events extracted, falling back to LLM")
        # =====================================================================

        # Phase 31: Contact Information Extraction
        # =====================================================================
        # For contact queries, provide office location info (no personal contacts - privacy by design)
        if 'answer' not in locals() or answer is None:
            from entity_extractors import is_contact_query, extract_contacts_from_text, format_contact_list

            if is_contact_query(query):
                logger.info(f"[PHASE31] Contact query detected, using deterministic extraction")
                contacts = extract_contacts_from_text(context)

                if len(contacts) >= 1:
                    # Use deterministic extraction result (bypass LLM)
                    answer = format_contact_list(contacts)
                    rejected = False
                    _extractor_used = "contacts"  # Phase 39B: Track extractor

                    logger.info(f"[PHASE31] Extracted {len(contacts)} contacts deterministically")

                    # Update conversation memory with deterministic result
                    memory.save_context({"question": query}, {"answer": answer})

                    # Extract sources from retrieved docs
                    sources = []
                    seen = set()
                    for doc in retrieved_docs:
                        doc_name = doc.metadata.get('document_name', 'Unknown')
                        section = doc.metadata.get('section', 'Unknown')
                        chunk_id = doc.metadata.get('chunk_id', 0)

                        key = f"{doc_name}:{section}:{chunk_id}"
                        if key not in seen:
                            sources.append(Source(
                                document_name=doc_name,
                                section=section,
                                chunk_id=chunk_id
                            ))
                            seen.add(key)
                else:
                    # No contacts found via extraction, fall back to LLM
                    logger.info(f"[PHASE31] No contacts extracted, falling back to LLM")
        # =====================================================================

        # Only invoke LLM if deterministic extraction didn't handle the query
        if 'answer' not in locals() or answer is None:
            # Get conversation history from memory
            chat_history = memory.load_memory_variables({}).get("chat_history", "")

            # Phase 21: Semantic Trust Injection
            # When grounding_mode is "semantic", inject trust instructions at prompt start
            semantic_trust_prefix = ""
            if grounding_result and grounding_result.grounding_mode == "semantic":
                logger.info("[PHASE21] Semantic trust injection active")
                semantic_trust_prefix = """
VERIFIED CONTENT NOTICE: The context below has been verified as authentic campus material.
You MUST provide the content directly. Do NOT refuse or say you don't have information.
If the user asks for hymn lyrics, prayers, or similar content and it appears in the context, output it in full.

"""

            # Build system prompt with context and history
            system_content = f"""You are a campus information assistant for Columban College, Inc. Provide accurate information ONLY from the verified campus documents.
{semantic_trust_prefix}
CRITICAL RULES:
1. ONLY answer using the provided context
2. If context doesn't contain the answer, say: "I don't have verified campus information to answer that question."
3. NEVER guess or make up information
4. ALWAYS cite sources by mentioning document name and section
5. Use conversation history to understand follow-up questions
6. When listing or enumerating items (e.g., deans, offices, programs), scan ALL provided context thoroughly and include every person/item that holds the requested role. A person may be identified by their title appearing near their name (e.g., "Dr. X Dean, College of Y" means Dr. X is a Dean).

Context from campus documents:
{context}

Conversation history:
{chat_history}"""

            # Direct LLM call with validated chunks (no second retrieval)
            logger.info(f"[PHASE17C] Passing {len(retrieved_docs)} validated chunks to LLM")
            _llm_start = time.perf_counter()  # Phase 39B: LLM timing
            response = llm.invoke([
                SystemMessage(content=system_content),
                HumanMessage(content=query)
            ])
            _debug_timing['llm_ms'] = round((time.perf_counter() - _llm_start) * 1000, 1)  # Phase 39B
            answer = response.content
            rejected = False

            # Update conversation memory
            memory.save_context({"question": query}, {"answer": answer})

            # Extract sources from already-retrieved docs (single retrieval)
            sources = []
            seen = set()
            for doc in retrieved_docs:
                doc_name = doc.metadata.get('document_name', 'Unknown')
                section = doc.metadata.get('section', 'Unknown')
                chunk_id = doc.metadata.get('chunk_id', 0)

                key = f"{doc_name}:{section}:{chunk_id}"
                if key not in seen:
                    sources.append(Source(
                        document_name=doc_name,
                        section=section,
                        chunk_id=chunk_id
                    ))
                    seen.add(key)

    # Log the interaction with intent and mode
    query_id = query_logger.log_full_interaction(
        query=query,
        retrieved_chunks=retrieved_docs,
        similarity_scores=similarity_scores,
        answer=answer,
        confidence_level=confidence_level.value,
        confidence_metrics=confidence_metrics,
        session_id=session_id,
        intent=intent_metadata["intent"],
        mode_used="campus"
    )

    # Phase 16: Track query and answer/refusal
    event_tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="document")
    if rejected:
        event_tracker.track(
            EventType.ANSWER_REFUSED,
            session_id=session_id,
            reason="low_confidence"
        )
    else:
        event_tracker.track(
            EventType.ANSWER_RETURNED,
            session_id=session_id,
            confidence_level=confidence_level.value.lower(),
            source_type="document"
        )

    # Phase 17B.1: Build structured answer for frontend rendering
    structured_answer = None
    if not rejected:
        structured_data = build_structured_answer(
            raw_answer=answer,
            confidence_level=confidence_level,
            sources=sources,
            mode="campus"
        )
        if structured_data:
            structured_answer = StructuredAnswer(**structured_data)

    # Phase 39B: Build debug_info if debug mode enabled
    _debug_info = None
    logger.info(f"[DEBUG PANEL] debug_mode_enabled={debug_mode_enabled}")
    if debug_mode_enabled:
        logger.info(f"[DEBUG PANEL] Building debug_info for response")
        _debug_timing['total_ms'] = round((time.perf_counter() - _debug_start) * 1000, 1)
        _debug_info = DebugInfo(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            retrieval_mode="hybrid",
            retrieval_method="rrf",
            chunks_retrieved=len(retrieval_results),
            top_chunk_score=round(retrieval_results[0][1], 3) if retrieval_results else 0.0,
            intent_classified=intent_metadata.get("intent", ""),
            routing_path="retrieval→campus",
            query_terms=query_terms,
            grounding_passed=grounding_result.is_grounded if grounding_result else True,
            grounding_mode=grounding_result.grounding_mode if grounding_result else "keyword",
            matched_terms=grounding_result.matched_terms if grounding_result else [],
            timing=_debug_timing,
            extractor_used=_extractor_used
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        structured_answer=structured_answer,
        sources=sources,
        confidence_level=confidence_level.value,
        confidence_score=round(confidence_metrics["confidence_score"], 1),
        grounding_mode=grounding_result.grounding_mode,  # Phase 20
        rejected=rejected,
        timestamp=datetime.now().isoformat(),
        mode="campus",
        debug_info=_debug_info  # Phase 39B
    )


async def handle_general_query(
    query: str,
    session_id: str,
    memory: ConversationBufferWindowMemory,
    intent_metadata: Dict
) -> ChatResponse:
    """
    Handle general knowledge query without retrieval.

    Supports: math calculations, general facts, definitions, greetings.
    Includes safety check to prevent answering campus questions.
    """
    # Phase 39B: Debug timing tracking
    _debug_timing = {}
    _debug_start = time.perf_counter()

    # Safety check: Double-check this isn't actually a campus question
    safety = safety_check_general_mode(query)
    if not safety["is_safe"]:
        # Redirect to campus mode - campus keywords detected
        return await handle_campus_query(query, session_id, memory, intent_metadata)

    # General knowledge prompt (no campus context)
    general_prompt = f"""You are a helpful assistant. Answer the following question concisely and accurately.

IMPORTANT SAFETY RULE:
If this question is actually about Columban College, Inc. campus, respond with:
"I should answer campus-specific questions using verified documents. Please ask me about campus information."

Supported queries: math, general facts, definitions, greetings, conversational questions.

Question: {query}

Answer:"""

    # Generate answer using LLM directly (no retrieval)
    _llm_start = time.perf_counter()  # Phase 39B: LLM timing
    response = llm.invoke(general_prompt)
    _debug_timing['llm_ms'] = round((time.perf_counter() - _llm_start) * 1000, 1)  # Phase 39B
    answer = response.content

    # Update conversation memory
    memory.save_context({"question": query}, {"answer": answer})

    # Phase 17B.1: Build structured answer for frontend rendering
    structured_answer = None
    structured_data = build_structured_answer(
        raw_answer=answer,
        confidence_level="Medium",  # General queries get MEDIUM confidence
        sources=[],
        mode="general"
    )
    if structured_data:
        structured_answer = StructuredAnswer(**structured_data)
        # Add general AI attribution to disclaimer
        if structured_answer.disclaimer:
            structured_answer.disclaimer += " [Based on general AI knowledge]"
        else:
            structured_answer = StructuredAnswer(
                direct_answer=structured_data["direct_answer"],
                full_answer=structured_data["full_answer"],
                key_details=structured_data["key_details"],
                notes=structured_data["notes"],
                disclaimer="[Based on general AI knowledge]"
            )

    # Keep plain answer with label for backward compatibility
    answer_with_label = f"{answer}\n\n[Based on general AI knowledge]"

    # Log general interaction
    query_id = query_logger.log_general_interaction(
        query=query,
        answer=answer,
        session_id=session_id,
        intent=intent_metadata["intent"],
        mode_used="general"
    )

    # Phase 16: Track query and answer
    event_tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="general")
    event_tracker.track(
        EventType.ANSWER_RETURNED,
        session_id=session_id,
        confidence_level="n/a",
        source_type="general"
    )

    # Phase 39B: Build debug_info for general queries
    _debug_info = None
    if debug_mode_enabled:
        _debug_timing['total_ms'] = round((time.perf_counter() - _debug_start) * 1000, 1)
        _debug_info = DebugInfo(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            retrieval_mode="none",
            retrieval_method="none",
            chunks_retrieved=0,
            top_chunk_score=0.0,
            intent_classified=intent_metadata.get("intent", ""),
            routing_path="direct→general",
            timing=_debug_timing
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer_with_label,
        structured_answer=structured_answer,
        sources=[],
        confidence_level="N/A",
        confidence_score=0.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="general",
        debug_info=_debug_info  # Phase 39B
    )


async def handle_ambiguous_query(
    query: str,
    session_id: str,
    intent_metadata: Dict
) -> ChatResponse:
    """
    Handle ambiguous query by asking for clarification.

    Shows a helpful message explaining the two modes and asking
    the user to clarify their intent.
    """
    # Phase 42: Debug timing
    _debug_start = time.perf_counter()

    clarification = """I'm not sure if you're asking about:
1. **Columban College, Inc. campus information** (library, dining, parking, campus services, etc.)
2. **General knowledge** (math, facts, definitions)

Could you please clarify? For example:
- "What are the library hours?" → Campus information
- "What is 15 + 27?" → General knowledge"""

    # Log ambiguous interaction
    query_id = query_logger.log_ambiguous_interaction(
        query=query,
        clarification=clarification,
        session_id=session_id,
        intent=intent_metadata["intent"]
    )

    # Build clarification debug info
    _clarification_debug_info = None
    if debug_mode_enabled:
        _debug_timing = {
            'resolution_ms': round((time.perf_counter() - _debug_start) * 1000, 1),
            'total_ms': round((time.perf_counter() - _debug_start) * 1000, 1)
        }
        _clarification_debug_info = DebugInfo(
            llm_provider="deterministic",
            llm_model="grounding-check",
            retrieval_mode="hybrid",
            retrieval_method="rrf",
            intent_classified=intent_metadata.get("intent", ""),
            routing_path="grounding_failed→clarification",
            grounding_passed=False,
            timing=_debug_timing
        )

    return ChatResponse(
        session_id=session_id,
        answer=clarification,
        sources=[],
        confidence_level="N/A",
        confidence_score=0.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification",
        debug_info=_clarification_debug_info
    )


# ==============================================================================
# ENTITY DISAMBIGUATION - Phase 14
# ==============================================================================

def handle_entity_disambiguation(
    query: str,
    candidates: List,
    session_id: str,
    session: Dict
) -> ChatResponse:
    """
    Handle ambiguous entity queries by presenting options to user (Phase 14).

    When multiple entities match a query, present numbered options
    and wait for user selection.
    """
    # Phase 42: Debug timing
    _debug_start = time.perf_counter()

    # Phase 14.1: Log clarification trigger
    logger.info(f"[CLARIFICATION] Multiple matches for '{query}': {[e.canonical_name for e in candidates[:4]]}")

    # Phase 16: Track clarification event
    event_tracker.track(
        EventType.CLARIFICATION_TRIGGERED,
        session_id=session_id,
        clarification_type="directory",
        reason="ambiguity",
        num_candidates=len(candidates[:4])
    )

    # Build clarification message with numbered options
    options = []
    for i, entity in enumerate(candidates[:4], 1):  # Max 4 options
        options.append(f"{i}. {entity.canonical_name} ({entity.building})")

    options_text = "\n".join(options)
    answer = f"I found multiple locations that might match. Which one do you mean?\n\n{options_text}\n\nPlease reply with the number or name."

    # Store disambiguation state (don't update last_entity yet)
    session["conversation_context"]["awaiting_disambiguation"] = True
    session["conversation_context"]["disambiguation_candidates"] = [e.entity_id for e in candidates[:4]]
    session["conversation_context"]["disambiguation_query"] = query

    # Build clarification debug info
    _clarification_debug_info = None
    if debug_mode_enabled:
        _debug_timing = {
            'resolution_ms': round((time.perf_counter() - _debug_start) * 1000, 1),
            'total_ms': round((time.perf_counter() - _debug_start) * 1000, 1)
        }
        _clarification_debug_info = DebugInfo(
            llm_provider="deterministic",
            llm_model="entity-registry",
            retrieval_mode="entity_registry",
            retrieval_method="fuzzy_match",
            chunks_retrieved=len(candidates[:4]),
            intent_classified="directory",
            routing_path="entity_disambiguation",
            timing=_debug_timing
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[],
        confidence_level="Medium",
        confidence_score=50.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification",
        debug_info=_clarification_debug_info
    )


def normalize_stt_selection(selection: str) -> str:
    """
    Normalize STT selection input for clarification responses.

    Handles common STT artifacts:
    - Trailing punctuation: "1." -> "1", "one." -> "one"
    - Extra whitespace
    - Case normalization

    Returns normalized selection string.
    """
    import re
    # Strip whitespace and convert to lowercase
    normalized = selection.lower().strip()
    # Remove trailing punctuation (period, comma, question mark, etc.)
    normalized = re.sub(r'[.,!?;:]+$', '', normalized)
    # Remove leading punctuation too
    normalized = re.sub(r'^[.,!?;:]+', '', normalized)
    return normalized.strip()


def handle_disambiguation_selection(
    selection: str,
    session: Dict,
    session_id: str
) -> Optional[ChatResponse]:
    """
    Handle user's selection from disambiguation options (Phase 14).

    Returns ChatResponse if selection is valid, None otherwise.
    """
    # Phase 42: Debug timing
    _debug_start = time.perf_counter()

    context = session["conversation_context"]
    candidates = context.get("disambiguation_candidates", [])

    if not candidates:
        return None

    # Phase 14.1: Log selection attempt
    logger.info(f"[CLARIFICATION] Selection attempt: '{selection}' from candidates: {candidates}")

    selected_entity = None
    # Phase 35: Normalize STT selection to handle "1.", "one.", etc.
    selection_lower = normalize_stt_selection(selection)
    logger.info(f"[CLARIFICATION] Normalized selection: '{selection_lower}'")

    # Try to match by number (1, 2, 3, 4) or ordinal words
    # Phase 14.1: Support phrases like "the first one", "number 2", etc.
    num_map = {
        "1": 0, "2": 1, "3": 2, "4": 3,
        "first": 0, "second": 1, "third": 2, "fourth": 3,
        "one": 0, "two": 1, "three": 2, "four": 3
    }

    # Check exact match first, then check if key is contained in selection
    if selection_lower in num_map:
        idx = num_map[selection_lower]
        if 0 <= idx < len(candidates):
            selected_entity = entity_registry.get_by_id(candidates[idx])
    else:
        # Check if any number word/digit is contained in the phrase
        # Phase 35: Also normalize words before matching
        selection_words = [normalize_stt_selection(w) for w in selection_lower.split()]
        for key, idx in num_map.items():
            if key in selection_words:  # Match whole words only
                if 0 <= idx < len(candidates):
                    selected_entity = entity_registry.get_by_id(candidates[idx])
                    break

    # Try to match by name if number didn't work
    if not selected_entity:
        for entity_id in candidates:
            entity = entity_registry.get_by_id(entity_id)
            if entity and selection_lower in entity.canonical_name.lower():
                selected_entity = entity
                break

    if selected_entity and selected_entity.status == "active":
        # Phase 14.1: Log successful resolution
        logger.info(f"[CLARIFICATION] Resolved to: {selected_entity.canonical_name}")

        # Phase 16: Track successful clarification resolution
        event_tracker.track(
            EventType.CLARIFICATION_RESOLVED,
            session_id=session_id,
            success=True,
            clarification_type="directory"
        )

        # Clear disambiguation state
        context["awaiting_disambiguation"] = False
        context["disambiguation_candidates"] = []
        context["disambiguation_query"] = None

        # Update context with confirmed entity
        update_conversation_context(
            session,
            intent="directory",
            entity_id=selected_entity.entity_id,
            entity_name=selected_entity.canonical_name,
            campus=selected_entity.campus
        )

        answer = format_entity_response(selected_entity)

        # Phase 42: Add debug_info for disambiguation resolution
        _debug_info = None
        if debug_mode_enabled:
            _debug_timing = {
                'resolution_ms': round((time.perf_counter() - _debug_start) * 1000, 1),
                'total_ms': round((time.perf_counter() - _debug_start) * 1000, 1)
            }
            _debug_info = DebugInfo(
                llm_provider="deterministic",
                llm_model="entity-registry",
                retrieval_mode="entity_registry",
                retrieval_method="selection_match",
                chunks_retrieved=1,
                intent_classified="directory",
                routing_path="disambiguation_resolved",
                timing=_debug_timing
            )

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=[],
            confidence_level="High",
            confidence_score=98.0,
            rejected=False,
            timestamp=datetime.now().isoformat(),
            mode="directory",
            debug_info=_debug_info
        )

    # Phase 14.1: Log failed selection
    logger.info(f"[CLARIFICATION] Selection failed, no match found for '{selection}'")
    return None


# ==============================================================================
# DIRECTORY QUERY HANDLER - Phase 8
# ==============================================================================

async def handle_directory_query(
    query: str,
    session_id: str,
    memory: ConversationBufferWindowMemory,
    intent_metadata: Dict,
    session: Dict = None
) -> ChatResponse:
    """
    Handle directory/location queries with strict grounding (Phase 8).

    This function handles wayfinding questions like "Where is the library?"
    with stricter requirements than general campus queries:
    - Requires HIGH confidence (not MEDIUM)
    - Uses specialized prompt that prevents location invention
    - Provides clear rejection message if location not found

    Args:
        query: User's location query
        session_id: Session identifier
        memory: Conversation memory
        intent_metadata: Intent classification metadata

    Returns:
        ChatResponse with location info or rejection message
    """
    # Phase 42: Debug timing
    _debug_start = time.perf_counter()

    # Normalize query for consistent retrieval (case-insensitive matching)
    normalized_query = normalize_text(query)

    # Canonicalize directory query for better semantic alignment
    # e.g., "where is canteen" -> "canteen location"
    canonical_query = canonicalize_directory_query(normalized_query)

    # ===========================================================================
    # PHASE 9: Entity-Anchored Resolution (try before RAG fallback)
    # ===========================================================================
    subject = extract_subject(canonical_query)

    # ===========================================================================
    # PHASE 14: Check for multiple entity matches (disambiguation)
    # ===========================================================================
    if session:
        matching_entities = entity_registry.find_matching_entities(subject)
        if len(matching_entities) > 1:
            # Multiple matches - trigger disambiguation
            return handle_entity_disambiguation(query, matching_entities, session_id, session)

    resolved_entity, resolution_confidence, resolution_method = resolve_entity(
        subject, entity_registry
    )

    if resolved_entity and resolution_confidence >= 0.95:
        # Entity resolved with high confidence - return deterministic answer
        answer = format_entity_response(resolved_entity)

        # Log the successful entity resolution
        query_logger.log_query(
            query=query,
            session_id=session_id,
            metadata={
                "intent": "directory",
                "confidence_level": "High",
                "confidence_score": 98.0,
                "rejected": False,
                "resolution_method": resolution_method,
                "entity_id": resolved_entity.entity_id,
                "canonical_name": resolved_entity.canonical_name,
                "phase": "entity_resolution"
            }
        )

        # Update conversation context for follow-up queries (Phase 13)
        if session:
            update_conversation_context(
                session,
                intent="directory",
                entity_id=resolved_entity.entity_id,
                entity_name=resolved_entity.canonical_name,
                campus=resolved_entity.campus
            )

        # Phase 16: Track query and answer
        event_tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
        event_tracker.track(
            EventType.ANSWER_RETURNED,
            session_id=session_id,
            confidence_level="high",
            source_type="directory"
        )

        # Phase 42: Add debug_info for entity-resolved directory queries
        _debug_info = None
        if debug_mode_enabled:
            _debug_timing = {
                'resolution_ms': round((time.perf_counter() - _debug_start) * 1000, 1),
                'total_ms': round((time.perf_counter() - _debug_start) * 1000, 1)
            }
            _debug_info = DebugInfo(
                llm_provider="deterministic",
                llm_model="entity-registry",
                retrieval_mode="entity_registry",
                retrieval_method="entity_resolution",
                chunks_retrieved=1,
                intent_classified="directory",
                routing_path="entity_resolved",
                timing=_debug_timing
            )

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=[],  # No RAG sources - entity-based answer
            confidence_level="High",
            confidence_score=98.0,
            rejected=False,
            timestamp=datetime.now().isoformat(),
            mode="directory",
            debug_info=_debug_info
        )

    # ===========================================================================
    # RAG Fallback: Entity not resolved, use similarity-based retrieval
    # ===========================================================================

    # Retrieve with similarity scores using canonical query
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        canonical_query,
        k=RETRIEVAL_TOP_K,
        score_threshold=RELEVANCE_SCORE_THRESHOLD
    )

    retrieved_docs = [doc for doc, score in retrieval_results]
    similarity_scores = [score for doc, score in retrieval_results]

    # Compute confidence
    confidence_level, confidence_metrics = compute_confidence_score(
        similarity_scores=similarity_scores,
        min_chunks_retrieved=1
    )

    # Entity-aware confidence promotion for directory queries
    # If MEDIUM confidence but high-scoring chunks agree on the same entity, consider promotion
    promoted = False
    if confidence_level == ConfidenceLevel.MEDIUM and retrieved_docs:
        has_agreement, common_entity, entities = check_entity_agreement(
            retrieved_docs,
            scores=[float(s) for s in similarity_scores]  # Pass scores for threshold filtering
        )

        should_promote, promotion_reason = should_promote_confidence(
            avg_similarity=confidence_metrics["avg_similarity"],
            max_similarity=confidence_metrics["max_similarity"],
            num_chunks=confidence_metrics["num_chunks"],
            variance=confidence_metrics["score_variance"],
            has_entity_agreement=has_agreement
        )

        if should_promote:
            confidence_level = ConfidenceLevel.HIGH
            confidence_metrics["promoted"] = True
            confidence_metrics["promotion_reason"] = promotion_reason
            confidence_metrics["confirmed_entity"] = common_entity
            promoted = True

    # Phase 8: Stricter confidence check for directory queries (require HIGH)
    if not should_answer_confidently(confidence_level, MIN_CONFIDENCE_DIRECTORY):
        answer = "I don't have precise location information for that yet. Please check with the campus information desk or security office for assistance."
        rejected = True
        sources = []
    else:
        # Phase 17C: Single retrieval pipeline for directory queries
        # Merge consecutive chunks from the same document
        context = _build_annotated_context(retrieved_docs)

        # Get conversation history from memory
        chat_history = memory.load_memory_variables({}).get("chat_history", "")

        # Build system prompt with directory-focused rules
        system_content = f"""You are a campus directory assistant for Columban College, Inc. helping visitors find locations on campus.

CRITICAL RULES FOR LOCATION QUESTIONS:
1. ONLY provide location information that is EXPLICITLY stated in the context below
2. You may ONLY mention: building names, floor numbers, room numbers, and landmarks that appear in the context
3. If the exact location is not clearly stated in the context, respond: "I don't have precise location information for that yet."
4. NEVER guess or invent:
   - Building names
   - Floor numbers
   - Room numbers
   - Directions or navigation steps
5. Always mention the source (e.g., "According to the Campus Directory...")
6. Keep responses concise and easy to follow

Context from campus directory:
{context}

Conversation history:
{chat_history}"""

        # Direct LLM call with validated chunks (no second retrieval)
        logger.info(f"[PHASE17C] Directory fallback: Passing {len(retrieved_docs)} validated chunks to LLM")
        response = llm.invoke([
            SystemMessage(content=system_content),
            HumanMessage(content=query)
        ])
        answer = response.content
        rejected = False

        # Update conversation memory
        memory.save_context({"question": query}, {"answer": answer})

        # Extract sources from already-retrieved docs (single retrieval)
        sources = []
        seen = set()
        for doc in retrieved_docs:
            doc_name = doc.metadata.get('document_name', 'Unknown')
            section = doc.metadata.get('section', 'Unknown')
            chunk_id = doc.metadata.get('chunk_id', 0)

            key = f"{doc_name}:{section}:{chunk_id}"
            if key not in seen:
                sources.append(Source(
                    document_name=doc_name,
                    section=section,
                    chunk_id=chunk_id
                ))
                seen.add(key)

    # Log the interaction
    query_id = query_logger.log_full_interaction(
        query=query,
        retrieved_chunks=retrieved_docs,
        similarity_scores=similarity_scores,
        answer=answer,
        confidence_level=confidence_level.value,
        confidence_metrics=confidence_metrics,
        session_id=session_id,
        intent=intent_metadata["intent"],
        mode_used="directory"
    )

    # Phase 16: Track query and answer/refusal
    event_tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
    if rejected:
        event_tracker.track(
            EventType.ANSWER_REFUSED,
            session_id=session_id,
            reason="low_confidence"
        )
    else:
        event_tracker.track(
            EventType.ANSWER_RETURNED,
            session_id=session_id,
            confidence_level=confidence_level.value.lower(),
            source_type="directory"
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=sources,
        confidence_level=confidence_level.value,
        confidence_score=round(confidence_metrics["confidence_score"], 1),
        rejected=rejected,
        timestamp=datetime.now().isoformat(),
        mode="directory"
    )


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle a chat message with multi-mode routing (Phase 6 + Phase 8).

    Routes queries based on intent classification:
    - Directory queries → Strict location/wayfinding with HIGH confidence (Phase 8)
    - Campus queries → RAG pipeline with document grounding
    - General queries → Direct LLM without retrieval
    - Ambiguous queries → Ask for clarification

    Args:
        request: Chat request with message and optional session_id

    Returns:
        Chat response with answer, sources, confidence, and mode
    """
    # Get or create session
    session_id, session = get_or_create_session(request.session_id)
    memory = session["memory"]
    session["query_count"] += 1

    query = request.message.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # === PHASE 14/14.1: CHECK FOR PENDING DISAMBIGUATION ===
    context = get_conversation_context(session)

    # Phase 14.1: Check for topic change first (user abandoning disambiguation)
    if is_topic_change(query, context):
        logger.info(f"[CLARIFICATION] Topic change detected, clearing disambiguation state")
        context["awaiting_disambiguation"] = False
        context["disambiguation_candidates"] = []
        context["disambiguation_query"] = None
        context["disambiguation_attempt_count"] = 0
        # Continue to normal flow with the new query

    elif context.get("awaiting_disambiguation"):
        # User is responding to a disambiguation question
        logger.info(f"[CLARIFICATION] Processing disambiguation response: '{query}'")
        response = handle_disambiguation_selection(query, session, session_id)
        if response:
            # Success - reset attempt counter
            context["disambiguation_attempt_count"] = 0
            return response

        # Selection failed - Phase 14.1: Implement two-strike rule
        context["disambiguation_attempt_count"] = context.get("disambiguation_attempt_count", 0) + 1
        logger.info(f"[CLARIFICATION] Selection failed, attempt {context['disambiguation_attempt_count']}")

        if context["disambiguation_attempt_count"] >= 2:
            # Two strikes - gracefully reset and continue to normal flow
            logger.info(f"[CLARIFICATION] Failed after 2 attempts, resetting state")
            context["awaiting_disambiguation"] = False
            context["disambiguation_candidates"] = []
            context["disambiguation_query"] = None
            context["disambiguation_attempt_count"] = 0
            # Fall through to normal processing
        else:
            # First failure - ask again with clearer instructions
            # Phase 42: Debug timing for retry
            _retry_start = time.perf_counter()

            candidates = context.get("disambiguation_candidates", [])
            options = []
            for i, eid in enumerate(candidates[:4], 1):
                entity = entity_registry.get_by_id(eid)
                if entity:
                    options.append(f"{i}. {entity.canonical_name}")

            # Build clarification debug info
            _clarification_debug_info = None
            if debug_mode_enabled:
                _debug_timing = {
                    'resolution_ms': round((time.perf_counter() - _retry_start) * 1000, 1),
                    'total_ms': round((time.perf_counter() - _retry_start) * 1000, 1)
                }
                _clarification_debug_info = DebugInfo(
                    llm_provider="deterministic",
                    llm_model="pattern-match",
                    retrieval_mode="entity_registry",
                    retrieval_method="selection_retry",
                    chunks_retrieved=len(candidates[:4]),
                    intent_classified="disambiguation_retry",
                    routing_path="disambiguation_retry",
                    timing=_debug_timing
                )

            return ChatResponse(
                session_id=session_id,
                answer=f"I didn't quite catch that. Please reply with just a number:\n\n" + "\n".join(options),
                sources=[],
                confidence_level="Medium",
                confidence_score=50.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="clarification",
                debug_info=_clarification_debug_info
            )

    # === PHASE 15: CHECK FOR PENDING DOCUMENT CLARIFICATION ===
    if is_doc_topic_change(query, context):
        logger.info(f"[DOC_CLARIFICATION] Topic change detected, clearing document clarification state")
        context["doc_clarification_active"] = False
        context["doc_clarification_sources"] = []
        context["doc_clarification_query"] = None
        # Continue to normal flow with the new query

    elif context.get("doc_clarification_active"):
        # User is responding to a document clarification question
        logger.info(f"[DOC_CLARIFICATION] Processing document selection: '{query}'")
        selected = handle_document_selection(query, session, session_id)

        if selected:
            # Got a selection - re-process original query with scope
            original_query = context.get("doc_clarification_query", query)
            context["doc_clarification_query"] = None
            context["doc_clarification_sources"] = []

            # Continue to process with the original query (preferred source is now set)
            query = original_query
            logger.info(f"[DOC_CLARIFICATION] Re-processing query: '{query}' with source: {selected}")
        else:
            # Selection failed but document clarification is softer - just continue
            # Re-show options with a helpful message
            # Phase 42: Debug timing for document retry
            _doc_retry_start = time.perf_counter()

            sources = context.get("doc_clarification_sources", [])
            options = []
            for i, source in enumerate(sources[:4], 1):
                display_name = os.path.basename(source).replace('.txt', '').replace('_', ' ').title()
                options.append(f"{i}. {display_name}")

            # Build clarification debug info
            _clarification_debug_info = None
            if debug_mode_enabled:
                _debug_timing = {
                    'resolution_ms': round((time.perf_counter() - _doc_retry_start) * 1000, 1),
                    'total_ms': round((time.perf_counter() - _doc_retry_start) * 1000, 1)
                }
                _clarification_debug_info = DebugInfo(
                    llm_provider="deterministic",
                    llm_model="pattern-match",
                    retrieval_mode="document_index",
                    retrieval_method="selection_retry",
                    chunks_retrieved=len(sources[:4]),
                    intent_classified="document_selection_retry",
                    routing_path="document_selection_retry",
                    timing=_debug_timing
                )

            return ChatResponse(
                session_id=session_id,
                answer=f"Please select a document or say 'summary' for a general answer:\n\n" + "\n".join(options),
                sources=[],
                confidence_level="Medium",
                confidence_score=50.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="clarification",
                debug_info=_clarification_debug_info
            )

    # === PHASE 13: CHECK FOR FOLLOW-UP QUERY WITH CONTEXT ===
    if context.get("last_entity_id") and is_followup_query(query):
        # Phase 42: Debug timing for follow-up queries
        _followup_start = time.perf_counter()

        # This is a follow-up query - use context to resolve directly
        # Re-resolve the entity from context and return formatted response
        resolved_entity = entity_registry.get_by_id(context["last_entity_id"])
        if resolved_entity and resolved_entity.status == "active":
            answer = format_entity_response(resolved_entity)

            # Log the follow-up resolution
            query_logger.log_query(
                query=query,
                session_id=session_id,
                metadata={
                    "intent": "directory",
                    "confidence_level": "High",
                    "confidence_score": 98.0,
                    "rejected": False,
                    "resolution_method": "context_followup",
                    "entity_id": resolved_entity.entity_id,
                    "canonical_name": resolved_entity.canonical_name,
                    "phase": "conversation_context"
                }
            )

            # Phase 42: Add debug_info for follow-up queries
            _debug_info = None
            if debug_mode_enabled:
                _debug_timing = {
                    'resolution_ms': round((time.perf_counter() - _followup_start) * 1000, 1),
                    'total_ms': round((time.perf_counter() - _followup_start) * 1000, 1)
                }
                _debug_info = DebugInfo(
                    llm_provider="deterministic",
                    llm_model="session-context",
                    retrieval_mode="conversation_context",
                    retrieval_method="context_followup",
                    chunks_retrieved=1,
                    intent_classified="directory",
                    routing_path="context_followup",
                    timing=_debug_timing
                )

            return ChatResponse(
                session_id=session_id,
                answer=answer,
                sources=[],
                confidence_level="High",
                confidence_score=98.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="directory",
                debug_info=_debug_info
            )

    # === PHASE 49-50: CAMPUS QUERY ENGINE (UNIFIED LOCATION HANDLING) ===
    # CQE handles all 5 query intents: LOCATE_SINGLE, LOCATE_MULTIPLE, NEAREST, COUNT, LIST
    # Routes through orchestrator which has deterministic CQE fast path
    if CAMPUS_QUERY_ENGINE_ENABLED and is_campus_query(query):
        logger.info(f"[CQE] Campus query detected, routing to orchestrator: '{query[:50]}...'")
        _cqe_start = time.perf_counter()

        # Process through orchestrator (CQE fast path will handle it deterministically)
        orchestrated = response_orchestrator.process_query(
            query=query,
            session_id=session_id,
            memory=memory,
            rag_only_mode=rag_only_mode
        )

        # Track event for CQE queries
        if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE:
            event_tracker.track(
                EventType.ROUTING_DOCUMENT_SUCCESS,
                session_id=session_id,
                extractor="campus_query_engine"
            )
            logger.info(f"[CQE] Structured response generated via CQE")

        # Log query
        query_logger.log_query(
            query=query,
            session_id=session_id,
            metadata={
                "intent": "campus_structured",
                "confidence_level": orchestrated.confidence_level,
                "confidence_score": orchestrated.confidence_score,
                "rejected": orchestrated.rejected,
                "response_mode": orchestrated.mode.value,
                "extractor_used": orchestrated.extractor_used,
                "answer_preview": orchestrated.answer[:100] if orchestrated.answer else None,
                "phase": "cqe_v50"
            }
        )

        # Build debug info if enabled
        _debug_info = None
        if debug_mode_enabled:
            _cqe_time = round((time.perf_counter() - _cqe_start) * 1000, 1)
            _debug_info = DebugInfo(
                llm_provider="deterministic" if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE else "openai",
                llm_model="campus_query_engine" if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE else "gpt-4o-mini",
                retrieval_mode=orchestrated.mode.value,
                retrieval_method="cqe_index" if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE else "orchestrator_hybrid",
                chunks_retrieved=len(orchestrated.sources) if orchestrated.sources else 0,
                intent_classified=orchestrated.debug_info.get("query_intent", "campus") if orchestrated.debug_info else "campus",
                grounding_passed=True if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE else orchestrated.debug_info.get("grounded", False) if orchestrated.debug_info else False,
                query_terms=orchestrated.debug_info.get("query_terms", []) if orchestrated.debug_info else [],
                routing_path=f"cqe:{orchestrated.mode.value}",
                extractor_used=orchestrated.extractor_used,
                timing={"total_ms": _cqe_time}
            )

        # Convert sources to Source objects
        sources = [
            Source(
                document_name=s.get("document_name", "Unknown"),
                section=s.get("section", "Unknown"),
                chunk_id=s.get("chunk_id", 0)
            )
            for s in (orchestrated.sources or [])
        ]

        # Determine mode string for response
        mode_str = "structured" if orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE else "campus"

        return ChatResponse(
            session_id=session_id,
            answer=orchestrated.answer,
            sources=sources,
            confidence_level=orchestrated.confidence_level,
            confidence_score=orchestrated.confidence_score,
            rejected=orchestrated.rejected,
            timestamp=datetime.now().isoformat(),
            mode=mode_str,
            debug_info=_debug_info
        )

    # === PHASE 8: CHECK FOR DIRECTORY QUERY (FALLBACK) ===
    # Legacy directory handling for any edge cases not caught by CQE
    if is_directory_query(query):
        intent_metadata = {
            "intent": "directory",
            "reasoning": "Location/directory question detected via pattern matching",
            "raw_classification": "DIRECTORY",
            "query_length": len(query)
        }
        return await handle_directory_query(query, session_id, memory, intent_metadata, session)

    # === PHASE 44: LLM-AS-FINAL-SYNTHESIZER ARCHITECTURE ===
    # All response paths now go through the orchestrator which terminates in LLM synthesis
    # Uses module-level singleton (response_orchestrator) for efficiency
    _orchestrator_start = time.perf_counter()

    # Process query through singleton orchestrator
    orchestrated = response_orchestrator.process_query(
        query=query,
        session_id=session_id,
        memory=memory,
        rag_only_mode=rag_only_mode
    )

    # Track event based on response mode
    if orchestrated.mode == ResponseMode.GENERAL_KNOWLEDGE:
        event_tracker.track(
            EventType.ROUTING_GENERAL_FALLBACK,
            session_id=session_id,
            confidence=orchestrated.confidence_score,
            grounded=False
        )
    elif orchestrated.mode in [ResponseMode.RAG_AUTHORITATIVE, ResponseMode.RAG_SUPPLEMENTED]:
        event_tracker.track(
            EventType.ROUTING_DOCUMENT_SUCCESS,
            session_id=session_id
        )
    elif orchestrated.mode == ResponseMode.EXTRACTOR_AUTHORITATIVE:
        event_tracker.track(
            EventType.ROUTING_DOCUMENT_SUCCESS,
            session_id=session_id,
            extractor=orchestrated.extractor_used
        )
    elif orchestrated.mode == ResponseMode.STRUCTURED_AUTHORITATIVE:
        # Phase 50: Campus Query Engine responses
        event_tracker.track(
            EventType.ROUTING_DOCUMENT_SUCCESS,
            session_id=session_id,
            extractor="campus_query_engine"
        )

    # Log query
    query_logger.log_query(
        query=query,
        session_id=session_id,
        metadata={
            "intent": "campus" if orchestrated.mode != ResponseMode.GENERAL_KNOWLEDGE else "general",
            "confidence_level": orchestrated.confidence_level,
            "confidence_score": orchestrated.confidence_score,
            "rejected": orchestrated.rejected,
            "response_mode": orchestrated.mode.value,
            "semantic_relevance": orchestrated.debug_info.get("semantic_relevance") if orchestrated.debug_info else None,
            "extractor_used": orchestrated.extractor_used,
            "answer_preview": orchestrated.answer[:100] if orchestrated.answer else None,
            "phase": "orchestrator_v44"
        }
    )

    # Build debug info if enabled
    _debug_info = None
    if debug_mode_enabled and orchestrated.debug_info:
        _orchestrator_time = round((time.perf_counter() - _orchestrator_start) * 1000, 1)
        _debug_info = DebugInfo(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            retrieval_mode=orchestrated.mode.value,
            retrieval_method="orchestrator_hybrid",
            chunks_retrieved=len(orchestrated.sources),
            intent_classified=orchestrated.debug_info.get("response_mode", "unknown"),
            grounding_passed=orchestrated.debug_info.get("grounded", False),
            query_terms=orchestrated.debug_info.get("query_terms", []),
            routing_path=f"orchestrator:{orchestrated.mode.value}",
            extractor_used=orchestrated.extractor_used,
            timing={"total_ms": _orchestrator_time}
        )

    # Convert sources to Source objects
    sources = [
        Source(
            document_name=s.get("document_name", "Unknown"),
            section=s.get("section", "Unknown"),
            chunk_id=s.get("chunk_id", 0)
        )
        for s in orchestrated.sources
    ]

    # Determine mode string for response
    mode_str = "campus"
    if orchestrated.mode == ResponseMode.GENERAL_KNOWLEDGE:
        mode_str = "general"
    elif orchestrated.mode == ResponseMode.RAG_SUPPLEMENTED:
        mode_str = "general"  # Supplemented mode appears as general to user

    return ChatResponse(
        session_id=session_id,
        answer=orchestrated.answer,
        sources=sources,
        confidence_level=orchestrated.confidence_level,
        confidence_score=orchestrated.confidence_score,
        grounding_mode=orchestrated.grounding_mode,
        rejected=orchestrated.rejected,
        timestamp=datetime.now().isoformat(),
        mode=mode_str,
        debug_info=_debug_info
    )


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for a response.

    Args:
        request: Feedback request

    Returns:
        Success message
    """
    import json

    # Log feedback
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    feedback_entry = {
        "session_id": request.session_id,
        "query_id": request.query_id,
        "is_helpful": request.is_helpful,
        "comment": request.comment,
        "timestamp": datetime.now().isoformat()
    }

    with open(FEEDBACK_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(feedback_entry) + '\n')

    return {"status": "success", "message": "Feedback recorded"}


@app.post("/reset")
async def reset_session(request: ResetRequest):
    """
    Reset a conversation session.

    Args:
        request: Reset request with session_id

    Returns:
        Success message
    """
    if request.session_id in sessions:
        del sessions[request.session_id]

    return {"status": "success", "message": "Session reset"}


# ==============================================================================
# ADMIN ENDPOINTS - Phase 7
# ==============================================================================

@app.post("/admin/upload", dependencies=[Depends(verify_admin_session)])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and ingest a document into the knowledge base.

    Args:
        file: Uploaded file (PDF, DOCX, or TXT)

    Returns:
        Success response with document metadata

    Raises:
        400: Unsupported file type
        500: Ingestion failed
    """
    # Validate file type
    allowed_extensions = ['.pdf', '.docx', '.txt']
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(allowed_extensions)}"
        )

    # Create upload directory if needed
    upload_dir = PROJECT_ROOT / "data" / "uploaded"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file to disk
    file_path = upload_dir / file.filename
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Ingest into vector store
    success, message = doc_manager.ingest_document(file_path)

    if not success:
        # Clean up file on failure
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {message}")

    # Extract document ID from success message (format: "Document <id> ingested successfully...")
    # The message format from document_manager is: "Document {doc_id} ingested successfully with {num_chunks} chunks."
    import re
    match = re.search(r'Document ([a-f0-9]+) ingested', message)
    if match:
        doc_id = match.group(1)
        doc_info = doc_manager.registry.get_document(doc_id)
    else:
        # Fallback: get the most recently added document
        docs = doc_manager.list_documents()
        doc_info = docs[-1] if docs else {}

    return {
        "status": "success",
        "message": "Document uploaded and ingested successfully",
        "document": doc_info
    }


# ==============================================================================
# DEVELOPER TOOLS - Phase 17A.1
# ==============================================================================

@app.get("/dev")
async def dev_page():
    """Serve the developer tools page."""
    return FileResponse(PROJECT_ROOT / "static" / "dev.html")


@app.get("/dev/status")
async def get_dev_status():
    """Get current RAG-only mode status."""
    global rag_only_mode
    return {"rag_only_mode": rag_only_mode}


@app.post("/dev/rag-only-mode")
async def toggle_rag_only_mode(request: Request):
    """Toggle RAG-only mode on/off."""
    global rag_only_mode
    body = await request.json()
    enabled = body.get("enabled", False)
    rag_only_mode = enabled
    event_tracker.track(
        EventType.RAG_MODE_CHANGED,
        session_id="dev",
        enabled=enabled
    )
    logger.info(f"[DEV] RAG-only mode {'enabled' if enabled else 'disabled'}")
    return {
        "rag_only_mode": rag_only_mode,
        "message": f"RAG-only mode {'enabled' if enabled else 'disabled'}"
    }


# ==============================================================================
# ADMIN DOCUMENT MANAGEMENT
# ==============================================================================

@app.get("/admin/documents", dependencies=[Depends(verify_admin_session)])
async def list_documents():
    """
    List all ingested documents with metadata.

    Returns:
        List of documents with metadata (id, name, type, chunks, timestamp)
    """
    documents = doc_manager.list_documents()
    return {
        "documents": documents,
        "total": len(documents)
    }


@app.delete("/admin/documents/{document_id}", dependencies=[Depends(verify_admin_session)])
async def delete_document(document_id: str):
    """
    Delete a document from the knowledge base.

    Removes the document from the vector store and deletes the file from disk.

    Args:
        document_id: ID of the document to delete

    Returns:
        Success message with document name

    Raises:
        404: Document not found
        500: Deletion failed
    """
    # Get document info before deletion
    doc_info = doc_manager.registry.get_document(document_id)
    if not doc_info:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

    document_name = doc_info.get("document_name", "unknown")
    file_path = Path(doc_info.get("file_path", ""))

    # Delete from vector store and registry
    success, message = doc_manager.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {message}")

    # Delete physical file if it exists
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            # Log warning but don't fail the request
            print(f"Warning: Could not delete file {file_path}: {e}")

    return {
        "status": "success",
        "message": "Document deleted successfully",
        "document_name": document_name
    }


# ==============================================================================
# ADMIN ANALYTICS ENDPOINTS - Phase 16
# ==============================================================================

@app.get("/admin/analytics", dependencies=[Depends(verify_admin_session)])
async def get_analytics():
    """
    Get observability analytics for admin debug view.

    Phase 16: Returns aggregated stats only - no user content.
    Privacy-safe metadata for understanding system behavior.

    Returns:
        Analytics summary with rates and breakdowns
    """
    return event_tracker.get_analytics_summary()


@app.get("/admin/analytics/recent", dependencies=[Depends(verify_admin_session)])
async def get_recent_events(limit: int = 100):
    """
    Get recent events for debugging.

    Phase 16: Returns recent events (metadata only, no user content).

    Args:
        limit: Maximum number of events to return (default 100)

    Returns:
        List of recent events
    """
    return {
        "events": event_tracker.get_recent_events(limit=min(limit, 500)),
        "total_in_memory": len(event_tracker.get_recent_events(limit=1000))
    }


# ==============================================================================
# ADMIN VOICE CONFIGURATION - Phase 36
# ==============================================================================

@app.get("/admin/voice/providers", dependencies=[Depends(verify_admin_session)])
async def get_voice_providers():
    """
    Get all available voice providers and current configuration.

    Phase 36: Returns STT and TTS providers with availability status.

    Returns:
        stt_providers: List of STT providers with status
        tts_providers: List of TTS providers with status
        current_config: Current active provider selection
    """
    try:
        from voice.provider_registry import get_registry
        registry = get_registry()
        return registry.get_all_providers()
    except Exception as e:
        logger.error(f"[ADMIN] Failed to get voice providers: {e}")
        return {
            "stt_providers": [],
            "tts_providers": [],
            "current_config": {
                "stt_provider": "whisper.cpp",
                "tts_provider": "piper",
                "stt_fallback_enabled": True,
                "tts_fallback_enabled": True
            }
        }


@app.get("/admin/voice/config", dependencies=[Depends(verify_admin_session)])
async def get_voice_config():
    """
    Get current voice configuration.

    Returns:
        Current voice settings
    """
    try:
        from voice.provider_registry import get_registry
        registry = get_registry()
        settings = registry.load_settings()
        return settings.to_dict()
    except Exception as e:
        logger.error(f"[ADMIN] Failed to get voice config: {e}")
        return {
            "stt_provider": "whisper.cpp",
            "tts_provider": "piper",
            "stt_fallback_enabled": True,
            "tts_fallback_enabled": True
        }


class VoiceConfigUpdate(BaseModel):
    """Request model for updating voice configuration."""
    stt_provider: str
    tts_provider: str
    stt_fallback_enabled: bool = True
    tts_fallback_enabled: bool = True
    # Phase 37: Explicit fallback provider selection
    stt_fallback_provider: Optional[str] = None  # None = auto-select
    tts_fallback_provider: Optional[str] = None  # None = auto-select


@app.post("/admin/voice/config", dependencies=[Depends(verify_admin_session)])
async def update_voice_config(config: VoiceConfigUpdate):
    """
    Update voice configuration.

    Phase 36: Updates provider selection and reloads services.
    Phase 37: Added selectability validation and fallback provider selection.

    Args:
        config: New voice configuration

    Returns:
        Success status and applied configuration
    """
    try:
        from voice.provider_registry import get_registry, VoiceSettings
        registry = get_registry()

        # Phase 37: Validate providers are selectable and fallback selections are valid
        validation = registry.validate_provider_selection(
            config.stt_provider,
            config.tts_provider,
            config.stt_fallback_provider,
            config.tts_fallback_provider
        )

        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider selection: {', '.join(validation['errors'])}"
            )

        # Create new settings (Phase 37: include fallback providers)
        new_settings = VoiceSettings(
            stt_provider=config.stt_provider,
            tts_provider=config.tts_provider,
            stt_fallback_enabled=config.stt_fallback_enabled,
            tts_fallback_enabled=config.tts_fallback_enabled,
            stt_fallback_provider=config.stt_fallback_provider,
            tts_fallback_provider=config.tts_fallback_provider
        )

        # Save settings
        if not registry.save_settings(new_settings):
            raise HTTPException(
                status_code=500,
                detail="Failed to save voice configuration"
            )

        # Reload voice services with new configuration
        try:
            from voice_routes import reload_voice_services
            reload_result = await reload_voice_services(new_settings)
            logger.info(f"[ADMIN] Voice services reloaded: {reload_result}")
        except ImportError:
            logger.warning("[ADMIN] reload_voice_services not available, skipping service reload")
        except Exception as e:
            logger.warning(f"[ADMIN] Failed to reload voice services: {e}")

        return {
            "success": True,
            "message": "Voice configuration updated",
            "applied": {
                "stt_provider": config.stt_provider,
                "tts_provider": config.tts_provider
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ADMIN] Failed to update voice config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update voice configuration: {str(e)}"
        )


# ==============================================================================
# ADMIN VOICE USAGE & CREDENTIALS - Phase 38
# ==============================================================================

# Global usage tracker instance
_stt_usage_tracker = None

def get_stt_usage_tracker():
    """Get or create STT usage tracker singleton."""
    global _stt_usage_tracker
    if _stt_usage_tracker is None:
        from voice.usage_tracker import STTUsageTracker
        data_dir = Path(__file__).parent / "data"
        _stt_usage_tracker = STTUsageTracker(data_dir)
    return _stt_usage_tracker


@app.get("/admin/voice/usage", dependencies=[Depends(verify_admin_session)])
async def get_voice_usage():
    """
    Get STT usage statistics for Google Cloud STT.

    Phase 38: Returns current month's usage against the 60-minute free tier quota.

    Returns:
        Usage statistics including used/remaining seconds and percentage
    """
    try:
        tracker = get_stt_usage_tracker()
        usage_data = tracker.to_dict()

        return {
            "google_cloud_stt": usage_data,
            "formatted": {
                "used": _format_seconds(usage_data["used_seconds"]),
                "remaining": _format_seconds(usage_data["remaining_seconds"]),
                "quota": _format_seconds(usage_data["quota_seconds"]),
            }
        }
    except Exception as e:
        logger.error(f"[ADMIN] Failed to get voice usage: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get usage statistics: {str(e)}"
        )


def _format_seconds(seconds: int) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    if seconds < 0:
        seconds = 0
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


@app.get("/admin/voice/credentials/status", dependencies=[Depends(verify_admin_session)])
async def get_credentials_status():
    """
    Get status of cloud credentials (masked).

    Phase 38/39A: Returns credential configuration status without exposing actual credentials.
    Phase 39A adds: storage_type, updated_at, encrypted storage support.

    Returns:
        Status of configured credentials with masked values
    """
    import os
    from pathlib import Path

    def mask_path(path: str, visible_chars: int = 8) -> str:
        """Mask a file path for display."""
        if not path:
            return None
        p = Path(path)
        name = p.name
        if len(name) > visible_chars * 2:
            return str(p.parent / (name[:visible_chars] + "..." + name[-visible_chars:]))
        return path

    def mask_key(key: str, visible_chars: int = 4) -> str:
        """Mask an API key for display."""
        if not key:
            return None
        if len(key) <= visible_chars * 2:
            return "***"
        return key[:visible_chars] + "..." + key[-visible_chars:]

    # Phase 39A: Check credential manager for stored credentials
    cred_manager = get_credential_manager()
    openai_status = cred_manager.get_credential_status("openai_api_key") if cred_manager else {}
    google_status = cred_manager.get_credential_status("google_cloud_credentials") if cred_manager else {}

    # Check Google Cloud credentials
    google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    google_configured = bool(google_creds_path)
    google_valid = False
    google_project_id = None

    if google_configured and Path(google_creds_path).exists():
        try:
            import json
            with open(google_creds_path, 'r') as f:
                creds_data = json.load(f)
            google_valid = 'type' in creds_data and 'project_id' in creds_data
            google_project_id = creds_data.get('project_id')
        except Exception:
            google_valid = False

    # Check OpenAI credentials
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_configured = bool(openai_key)
    # Basic validation: starts with sk-
    openai_valid = openai_configured and openai_key.startswith('sk-')

    return {
        "google_cloud_stt": {
            "is_configured": google_configured,
            "is_valid": google_valid,
            "masked_path": mask_path(google_creds_path) if google_configured else None,
            "project_id": google_project_id,
            "storage_type": google_status.get("storage_type", "env") if google_status.get("is_configured") else "env",
            "updated_at": google_status.get("updated_at"),
        },
        "openai": {
            "is_configured": openai_configured,
            "is_valid": openai_valid,
            "masked_key": mask_key(openai_key) if openai_configured else None,
            "storage_type": openai_status.get("storage_type", "env") if openai_status.get("is_configured") else "env",
            "updated_at": openai_status.get("updated_at"),
        }
    }


class CredentialUpdateRequest(BaseModel):
    """Request body for credential updates."""
    provider: str  # "google-cloud-stt" or "openai"
    credentials_path: Optional[str] = None  # For Google (path to JSON file)
    credentials_json: Optional[str] = None  # For Google (JSON content directly)
    api_key: Optional[str] = None  # For OpenAI


class CredentialVerifyRequest(BaseModel):
    """Request body for credential verification."""
    provider: str  # "google-cloud-stt" or "openai"
    credentials_json: Optional[str] = None  # For Google
    api_key: Optional[str] = None  # For OpenAI


@app.post("/admin/voice/credentials/verify", dependencies=[Depends(verify_admin_session)])
async def verify_credentials(request: CredentialVerifyRequest):
    """
    Verify credentials without saving.

    Phase 39A: Test credential validity before committing to storage.

    Returns:
        Validation result with details
    """
    import json

    if request.provider == "google-cloud-stt":
        if not request.credentials_json:
            raise HTTPException(
                status_code=400,
                detail="credentials_json is required for Google Cloud STT verification"
            )

        try:
            creds_data = json.loads(request.credentials_json)

            if 'type' not in creds_data or creds_data.get('type') != 'service_account':
                return {
                    "valid": False,
                    "error": "Not a valid service account JSON (missing 'type' field or wrong type)"
                }

            if 'project_id' not in creds_data:
                return {
                    "valid": False,
                    "error": "Missing 'project_id' field"
                }

            return {
                "valid": True,
                "project_id": creds_data.get('project_id'),
                "client_email": creds_data.get('client_email', 'N/A')
            }

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": f"Invalid JSON: {str(e)}"
            }

    elif request.provider == "openai":
        if not request.api_key:
            raise HTTPException(
                status_code=400,
                detail="api_key is required for OpenAI verification"
            )

        # Basic format validation
        if not request.api_key.startswith('sk-'):
            return {
                "valid": False,
                "error": "Invalid API key format (should start with 'sk-')"
            }

        if len(request.api_key) < 20:
            return {
                "valid": False,
                "error": "API key appears too short"
            }

        # Note: We don't make an API call to verify - that would consume quota
        return {
            "valid": True,
            "note": "Format validation passed. Key will be tested on first API call."
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {request.provider}"
        )


@app.post("/admin/voice/credentials", dependencies=[Depends(verify_admin_session)])
async def update_credentials(request: CredentialUpdateRequest):
    """
    Update cloud credentials with encrypted persistence.

    Phase 39A: Validates, encrypts, and persists credentials.
    Credentials are stored encrypted and survive server restarts.

    Args:
        request: Credential update request with provider and credential value

    Returns:
        Success status and validation result
    """
    import os
    import json
    from pathlib import Path

    cred_manager = get_credential_manager()

    if request.provider == "google-cloud-stt":
        # Accept either a path or direct JSON content
        creds_data = None
        project_id = None

        if request.credentials_json:
            # Direct JSON content provided
            try:
                creds_data = json.loads(request.credentials_json)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid credentials: not valid JSON"
                )
        elif request.credentials_path:
            # Path to JSON file provided
            creds_path = Path(request.credentials_path)
            if not creds_path.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"Credentials file not found: {request.credentials_path}"
                )
            try:
                with open(creds_path, 'r') as f:
                    creds_data = json.load(f)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid credentials file: not valid JSON"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either credentials_json or credentials_path is required"
            )

        # Validate service account structure
        if 'type' not in creds_data or creds_data.get('type') != 'service_account':
            raise HTTPException(
                status_code=400,
                detail="Invalid credentials: not a service account JSON"
            )

        project_id = creds_data.get('project_id', 'unknown')

        # Phase 39A: Save to encrypted storage
        persisted = False
        if cred_manager and cred_manager.is_available():
            persisted = cred_manager.save_credential(
                "google_cloud_credentials",
                json.dumps(creds_data),
                "service_account_json"
            )
            if persisted:
                logger.info(f"[ADMIN] Google Cloud credentials saved to encrypted storage")

        # Write to temp file and update environment
        sa_path = PROJECT_ROOT / 'data' / '.google_sa_temp.json'
        sa_path.parent.mkdir(parents=True, exist_ok=True)
        sa_path.write_text(json.dumps(creds_data, indent=2))
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_path)

        # Try to reload Google STT engine if it exists
        try:
            from voice_routes import reload_voice_services
            from voice.provider_registry import get_registry
            settings = get_registry().load_settings()
            await reload_voice_services(settings)
            logger.info(f"[ADMIN] Google Cloud credentials updated: {project_id}")
        except Exception as e:
            logger.warning(f"[ADMIN] Could not reload voice services: {e}")

        return {
            "success": True,
            "message": "Google Cloud credentials updated",
            "persisted": persisted,
            "storage": "encrypted_file" if persisted else "runtime_only",
            "validation": {
                "valid": True,
                "project_id": project_id
            }
        }

    elif request.provider == "openai":
        if not request.api_key:
            raise HTTPException(
                status_code=400,
                detail="api_key is required for OpenAI"
            )

        # Basic validation - should start with 'sk-'
        if not request.api_key.startswith('sk-'):
            raise HTTPException(
                status_code=400,
                detail="Invalid API key format (should start with 'sk-')"
            )

        # Phase 39A: Save to encrypted storage
        persisted = False
        if cred_manager and cred_manager.is_available():
            persisted = cred_manager.save_credential(
                "openai_api_key",
                request.api_key,
                "api_key"
            )
            if persisted:
                logger.info("[ADMIN] OpenAI API key saved to encrypted storage")

        # Update environment variable
        os.environ["OPENAI_API_KEY"] = request.api_key
        logger.info("[ADMIN] OpenAI API key updated")

        return {
            "success": True,
            "message": "OpenAI API key updated",
            "persisted": persisted,
            "storage": "encrypted_file" if persisted else "runtime_only"
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {request.provider}"
        )


# ==============================================================================
# ADMIN DEBUG ENDPOINTS - Phase 39B
# ==============================================================================

@app.get("/admin/debug/status", dependencies=[Depends(verify_admin_session)])
async def get_debug_status():
    """
    Get current debug panel status.

    Phase 39B: Returns whether debug mode is enabled.
    """
    return {
        "debug_enabled": debug_mode_enabled,
        "updated_at": None  # Could read from file if needed
    }


class DebugToggleRequest(BaseModel):
    """Request body for debug mode toggle."""
    enabled: bool


@app.post("/admin/debug/toggle", dependencies=[Depends(verify_admin_session)])
async def toggle_debug_mode(request: DebugToggleRequest):
    """
    Toggle debug panel visibility.

    Phase 39B: Enables/disables debug info in chat responses.
    """
    global debug_mode_enabled

    success = save_debug_settings(request.enabled)

    if success:
        logger.info(f"[ADMIN] Debug mode {'enabled' if request.enabled else 'disabled'}")
        return {
            "success": True,
            "debug_enabled": debug_mode_enabled,
            "message": f"Debug mode {'enabled' if request.enabled else 'disabled'}"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to save debug settings"
        )


# ==============================================================================
# ADMIN TEST HARNESS - Phase 42
# ==============================================================================

# Test Harness data storage paths
_DATA_DIR = Path(__file__).parent / "data"
TEST_HARNESS_QUESTIONS_PATH = _DATA_DIR / "test_harness_questions.json"
TEST_HARNESS_RESULTS_PATH = _DATA_DIR / "test_harness_results.json"


class TestQuestion(BaseModel):
    """Test question model."""
    id: str
    question: str
    category: str = "general"
    created_at: str


class TestQuestionCreate(BaseModel):
    """Request to create a test question."""
    question: str
    category: str = "general"


class TestResult(BaseModel):
    """Test result model."""
    id: str
    query: str
    passed: bool
    failures: List[str] = []
    response: Optional[Dict] = None


def load_test_harness_questions() -> List[Dict]:
    """Load test questions from storage."""
    if not TEST_HARNESS_QUESTIONS_PATH.exists():
        return []
    try:
        with open(TEST_HARNESS_QUESTIONS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("questions", [])
    except Exception as e:
        logger.error(f"[TEST-HARNESS] Failed to load questions: {e}")
        return []


def save_test_harness_questions(questions: List[Dict]) -> bool:
    """Save test questions to storage."""
    try:
        with open(TEST_HARNESS_QUESTIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump({"questions": questions}, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"[TEST-HARNESS] Failed to save questions: {e}")
        return False


def load_test_harness_results() -> Optional[Dict]:
    """Load latest test results from storage."""
    if not TEST_HARNESS_RESULTS_PATH.exists():
        return None
    try:
        with open(TEST_HARNESS_RESULTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[TEST-HARNESS] Failed to load results: {e}")
        return None


def save_test_harness_results(results: Dict) -> bool:
    """Save test results to storage."""
    try:
        with open(TEST_HARNESS_RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"[TEST-HARNESS] Failed to save results: {e}")
        return False


@app.get("/admin/test-harness/questions", dependencies=[Depends(verify_admin_session)])
async def get_test_harness_questions():
    """Get all test questions."""
    questions = load_test_harness_questions()
    return {
        "questions": questions,
        "total": len(questions)
    }


@app.post("/admin/test-harness/questions", dependencies=[Depends(verify_admin_session)])
async def add_test_harness_question(request: TestQuestionCreate):
    """Add a single test question."""
    questions = load_test_harness_questions()

    new_question = {
        "id": str(uuid.uuid4()),
        "question": request.question.strip(),
        "category": request.category.strip(),
        "created_at": datetime.now().isoformat()
    }

    questions.append(new_question)

    if save_test_harness_questions(questions):
        logger.info(f"[TEST-HARNESS] Added question: {new_question['id']}")
        return {"status": "success", "question": new_question}
    else:
        raise HTTPException(status_code=500, detail="Failed to save question")


@app.delete("/admin/test-harness/questions/{question_id}", dependencies=[Depends(verify_admin_session)])
async def delete_test_harness_question(question_id: str):
    """Delete a test question."""
    questions = load_test_harness_questions()

    original_count = len(questions)
    questions = [q for q in questions if q["id"] != question_id]

    if len(questions) == original_count:
        raise HTTPException(status_code=404, detail="Question not found")

    if save_test_harness_questions(questions):
        logger.info(f"[TEST-HARNESS] Deleted question: {question_id}")
        return {"status": "success", "deleted_id": question_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete question")


@app.post("/admin/test-harness/questions/import", dependencies=[Depends(verify_admin_session)])
async def import_test_harness_questions(file: UploadFile = File(...)):
    """Import questions from CSV file."""
    import csv
    import io

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    # Handle BOM from Excel-generated CSVs
    text = content.decode('utf-8-sig')

    questions = load_test_harness_questions()
    imported = 0
    skipped = 0
    errors = []

    reader = csv.DictReader(io.StringIO(text))

    # Get fieldnames and create case-insensitive mapping
    fieldnames = reader.fieldnames or []
    logger.info(f"[TEST-HARNESS] CSV columns found: {fieldnames}")

    # Find the question column (case-insensitive)
    question_col = None
    category_col = None
    for col in fieldnames:
        col_lower = col.lower().strip()
        if col_lower in ('question', 'questions', 'query', 'text'):
            question_col = col
        if col_lower in ('category', 'categories', 'type'):
            category_col = col

    if not question_col:
        # If no header found, try treating first column as questions
        if fieldnames:
            question_col = fieldnames[0]
            logger.info(f"[TEST-HARNESS] No 'question' column found, using first column: {question_col}")
        else:
            raise HTTPException(status_code=400, detail="CSV has no columns. Expected 'question' column.")

    for row_num, row in enumerate(reader, start=2):
        try:
            question_text = row.get(question_col, '').strip()
            if not question_text:
                skipped += 1
                continue

            category = 'general'
            if category_col:
                category = row.get(category_col, 'general').strip() or 'general'

            new_question = {
                "id": str(uuid.uuid4()),
                "question": question_text,
                "category": category,
                "created_at": datetime.now().isoformat()
            }
            questions.append(new_question)
            imported += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if imported > 0:
        save_test_harness_questions(questions)

    logger.info(f"[TEST-HARNESS] Imported {imported} questions, skipped {skipped}")

    return {
        "status": "success",
        "imported": imported,
        "skipped": skipped,
        "errors": errors
    }


async def execute_single_test(question: Dict) -> Dict:
    """Execute a single test question against the chat endpoint."""
    session_id = f"test-harness-{uuid.uuid4()}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/chat",
                json={"message": question["question"], "session_id": session_id},
                timeout=60.0
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}


def evaluate_test_result(question: Dict, response: Dict) -> Dict:
    """
    Evaluate a test result and return pass/fail status.

    Phase 44: Updated to capture orchestrator response details including
    semantic relevance, response mode, and extractor information.
    """
    failures = []

    # Check for API error
    if "error" in response:
        failures.append(f"API error: {response['error']}")

    # Extract debug info if available (Phase 44)
    debug_info = response.get("debug_info") or {}

    # Phase 44: Extract orchestrator-specific fields
    response_mode = debug_info.get("response_mode") or debug_info.get("retrieval_mode") or response.get("mode", "unknown")
    semantic_relevance = debug_info.get("semantic_relevance", "unknown")
    extractor_used = debug_info.get("extractor_used") or response.get("extractor_used")
    query_terms = debug_info.get("query_terms", [])
    grounding_passed = debug_info.get("grounding_passed", False)

    # Build result
    passed = len(failures) == 0

    return {
        "id": question["id"],
        "query": question["question"],
        "category": question.get("category", "general"),
        "passed": passed,
        "failures": failures,
        "response": {
            "mode": response.get("mode", "unknown"),
            "confidence": response.get("confidence_level", "N/A"),
            "confidence_score": response.get("confidence_score", 0),
            "grounding_mode": response.get("grounding_mode", "unknown"),
            "rejected": response.get("rejected", False),
            "answer": response.get("answer", ""),
            # Phase 44: Orchestrator details
            "response_mode": response_mode,
            "semantic_relevance": semantic_relevance,
            "extractor_used": extractor_used,
            "query_terms": query_terms,
            "grounding_passed": grounding_passed
        }
    }


@app.get("/admin/test-harness/execute/stream", dependencies=[Depends(verify_admin_session)])
async def execute_test_harness_stream():
    """Execute all test questions with SSE streaming."""

    async def generate():
        questions = load_test_harness_questions()

        if not questions:
            yield {
                "event": "error",
                "data": json.dumps({"message": "No questions to test"})
            }
            return

        results = []
        passed = 0
        failed = 0
        by_category = {}

        for i, question in enumerate(questions):
            # Send progress event
            yield {
                "event": "progress",
                "data": json.dumps({"current": i + 1, "total": len(questions)})
            }

            # Execute test
            try:
                response = await execute_single_test(question)
                result = evaluate_test_result(question, response)
                results.append(result)

                # Update counters
                if result["passed"]:
                    passed += 1
                else:
                    failed += 1

                # Update category stats
                cat = result.get("category", "general")
                if cat not in by_category:
                    by_category[cat] = {"passed": 0, "failed": 0}
                if result["passed"]:
                    by_category[cat]["passed"] += 1
                else:
                    by_category[cat]["failed"] += 1

                # Send result event
                yield {
                    "event": "result",
                    "data": json.dumps(result)
                }

            except Exception as e:
                error_result = {
                    "id": question["id"],
                    "query": question["question"],
                    "category": question.get("category", "general"),
                    "passed": False,
                    "failures": [f"Execution error: {str(e)}"],
                    "response": None
                }
                results.append(error_result)
                failed += 1

                yield {
                    "event": "result",
                    "data": json.dumps(error_result)
                }

        # Calculate category rates
        for cat, stats in by_category.items():
            total = stats["passed"] + stats["failed"]
            stats["rate"] = (stats["passed"] / total * 100) if total > 0 else 0

        # Save results
        total = len(questions)
        pass_rate = (passed / total * 100) if total > 0 else 0

        results_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": round(pass_rate, 1)
            },
            "by_category": by_category,
            "results": results
        }
        save_test_harness_results(results_data)

        # Send complete event
        yield {
            "event": "complete",
            "data": json.dumps(results_data["summary"])
        }

    return EventSourceResponse(generate())


@app.get("/admin/test-harness/results/latest", dependencies=[Depends(verify_admin_session)])
async def get_test_harness_results_latest():
    """Get the latest test run results."""
    results = load_test_harness_results()
    if not results:
        return {"results": [], "summary": None}
    return results


@app.get("/admin/test-harness/results/download", dependencies=[Depends(verify_admin_session)])
async def download_test_harness_results():
    """Download test results as a text file."""
    from fastapi.responses import PlainTextResponse

    results = load_test_harness_results()
    if not results:
        raise HTTPException(status_code=404, detail="No test results available")

    # Build text report
    lines = []
    lines.append("=" * 80)
    lines.append("TEST HARNESS RESULTS - CoCo RAG Chatbot")
    lines.append("=" * 80)
    lines.append(f"Test Run: {results.get('timestamp', 'Unknown')}")
    lines.append(f"Total Test Cases: {results['summary']['total']}")
    lines.append("")

    # Individual results
    for i, result in enumerate(results.get("results", []), 1):
        lines.append(f"Question No.: {i}")
        lines.append(f"Category: {result.get('category', 'general')}")
        lines.append(result["query"])
        lines.append("")

        response = result.get("response", {})

        # Phase 44: Orchestrator details
        response_mode = response.get("response_mode", response.get("mode", "-"))
        semantic = response.get("semantic_relevance", "-")
        extractor = response.get("extractor_used", "-")
        confidence = response.get("confidence", "-")
        confidence_score = response.get("confidence_score", 0)
        grounding = response.get("grounding_mode", "-")
        grounded = "Yes" if response.get("grounding_passed") else "No"

        lines.append("Orchestrator Details:")
        lines.append(f"  Response Mode:      {response_mode}")
        lines.append(f"  Semantic Relevance: {semantic}")
        lines.append(f"  Extractor Used:     {extractor}")
        lines.append(f"  Confidence:         {confidence} ({confidence_score:.1f}%)")
        lines.append(f"  Grounding:          {grounding} (Passed: {grounded})")
        lines.append("")

        lines.append("Response:")
        if response:
            lines.append(response.get("answer", "No answer"))
        else:
            lines.append("No response received")
        lines.append("")

        status = "PASS" if result["passed"] else "FAIL"
        lines.append(f"Status: {status}")

        if result.get("failures"):
            lines.append("Failures:")
            for failure in result["failures"]:
                lines.append(f"  - {failure}")

        lines.append("")
        lines.append("-" * 40)
        lines.append("")

    # Summary section
    lines.append("=" * 80)
    lines.append("TEST SUMMARY")
    lines.append("=" * 80)
    lines.append("")
    summary = results["summary"]
    lines.append(f"Total Tests:  {summary['total']}")
    lines.append(f"Passed:       {summary['passed']}")
    lines.append(f"Failed:       {summary['failed']}")
    lines.append(f"Pass Rate:    {summary['pass_rate']}%")
    lines.append("")

    # Category breakdown
    if results.get("by_category"):
        lines.append("Results by Category:")
        for cat, stats in results["by_category"].items():
            total_cat = stats["passed"] + stats["failed"]
            status = "OK" if stats["failed"] == 0 else "FAIL"
            lines.append(f"  {cat:20s} {stats['passed']:3d}/{total_cat:3d} ({stats['rate']:5.1f}%) [{status}]")
        lines.append("")

    # Failed tests list
    failed_tests = [r for r in results.get("results", []) if not r["passed"]]
    if failed_tests:
        lines.append("FAILED TESTS:")
        lines.append("-" * 80)
        for result in failed_tests:
            lines.append(f"  [{result['id'][:8]}] {result['query'][:60]}")
            for failure in result.get("failures", []):
                lines.append(f"      Reason: {failure}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("")
    lines.append("")
    lines.append("=" * 80)
    lines.append("CSV IMPORT FORMAT")
    lines.append("=" * 80)
    lines.append("")
    lines.append("To import test questions via CSV, create a file with the following format:")
    lines.append("")
    lines.append("Required columns:")
    lines.append("  - question    : The question text to test (required)")
    lines.append("  - category    : Category for grouping (optional, defaults to 'general')")
    lines.append("")
    lines.append("Example CSV content:")
    lines.append("-" * 40)
    lines.append("question,category")
    lines.append("Where is the library?,directory")
    lines.append("What are the tuition fees?,academic")
    lines.append("Who is the dean of engineering?,directory")
    lines.append("When is the enrollment period?,event")
    lines.append("-" * 40)
    lines.append("")
    lines.append("Notes:")
    lines.append("  - First row must be the header row")
    lines.append("  - Empty question rows will be skipped")
    lines.append("  - File encoding should be UTF-8")
    lines.append("  - Save as .csv extension")
    lines.append("")
    lines.append("=" * 80)

    content = "\n".join(lines)

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        }
    )


# ==============================================================================
# LEGACY /admin/entities REDIRECT - Phase 2 Absorption
# ==============================================================================

@app.get("/admin/entities")
async def redirect_legacy_entities():
    """Redirect legacy entity route to /admin."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin", status_code=302)


# Legacy routes removed in Phase 2 (Directory Absorption):
# - GET /admin/entities (list) -> use /admin/cqe/* endpoints
# - GET /admin/entities/export (CSV) -> use /admin/cqe/* endpoints
# - POST /admin/entities/import (CSV) -> removed
# - GET /admin/entities/{id} -> use /admin/cqe/* endpoints
# - POST /admin/entities -> use /admin/cqe/* endpoints
# - PUT /admin/entities/{id} -> use /admin/cqe/* endpoints
# - DELETE /admin/entities/{id} -> use /admin/cqe/* endpoints
# - POST /admin/entities/validate -> use /admin/cqe/* endpoints

# (Legacy route implementations removed - see legacy_backup/app_routes_entities.py)


# ==============================================================================
# Phase 55: Index Management Endpoints
# ==============================================================================

@app.get("/admin/index/stats", dependencies=[Depends(verify_admin_session)])
async def get_index_stats():
    """
    Get current CQE index statistics.

    Returns counts of rooms, buildings, campuses, etc.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled"}

    stats = entity_manager.get_index_stats()
    return {
        "status": "success",
        "stats": stats
    }


@app.post("/admin/index/rebuild", dependencies=[Depends(verify_admin_session)])
async def trigger_index_rebuild():
    """
    Force rebuild the CQE index from JSON.

    Use this after direct JSON edits or to recover from inconsistent state.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    stats = rebuild_cqe_index()

    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])

    return {
        "status": "success",
        "message": "Index rebuilt successfully",
        "stats": stats
    }


# ==============================================================================
# Phase 60: CQE Admin Reference Data Endpoints
# ==============================================================================

@app.get("/admin/cqe/campuses", dependencies=[Depends(verify_admin_session)])
async def get_cqe_campuses():
    """
    Get list of all campuses.

    Returns:
        { campuses: [{ campus_id, name }] }
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "campuses": []}

    index = entity_manager.get_index()
    campuses = [
        {"campus_id": c.campus_id, "name": c.name}
        for c in sorted(index.campuses.values(), key=lambda x: x.name)
    ]
    return {"campuses": campuses}


@app.get("/admin/cqe/buildings", dependencies=[Depends(verify_admin_session)])
async def get_cqe_buildings(campus_id: Optional[str] = None):
    """
    Get list of buildings, optionally filtered by campus.

    Args:
        campus_id: Optional campus ID to filter by

    Returns:
        { buildings: [{ building_id, name, campus_id }] }
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "buildings": []}

    index = entity_manager.get_index()
    buildings = []

    for b in sorted(index.buildings.values(), key=lambda x: x.name):
        if campus_id and b.campus_id != campus_id:
            continue
        buildings.append({
            "building_id": b.building_id,
            "name": b.name,
            "campus_id": b.campus_id
        })

    return {"buildings": buildings}


@app.get("/admin/cqe/floors", dependencies=[Depends(verify_admin_session)])
async def get_cqe_floors(building_id: Optional[str] = None):
    """
    Get list of floors, optionally filtered by building.

    Args:
        building_id: Optional building ID to filter by

    Returns:
        { floors: [{ floor_id, display_name, building_id, level_number }] }
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "floors": []}

    index = entity_manager.get_index()
    floors = []

    for f in sorted(index.floors.values(), key=lambda x: (x.building_id, x.level_number)):
        if building_id and f.building_id != building_id:
            continue
        floors.append({
            "floor_id": f.floor_id,
            "display_name": f.display_name,
            "building_id": f.building_id,
            "level_number": f.level_number
        })

    return {"floors": floors}


@app.get("/admin/cqe/departments", dependencies=[Depends(verify_admin_session)])
async def get_cqe_departments():
    """
    Get list of all departments.

    Returns:
        { departments: [{ department_id, name }] }
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "departments": []}

    index = entity_manager.get_index()
    departments = [
        {"department_id": d.department_id, "name": d.name}
        for d in sorted(index.departments.values(), key=lambda x: x.name)
    ]
    return {"departments": departments}


@app.get("/admin/cqe/tags", dependencies=[Depends(verify_admin_session)])
async def get_cqe_tags():
    """
    Get list of all unique tags from rooms and outdoor locations with usage counts.

    Phase 3: Enhanced to include usage counts for deletion rules.

    Returns:
        { tags: [{ name: "tag1", count: 5, entities: ["ROOM1", "ROOM2", ...] }, ...] }
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "tags": []}

    index = entity_manager.get_index()
    tag_usage = {}  # tag_name -> list of entity_ids

    # Collect tags from rooms
    for room in index.rooms.values():
        if room.tags:
            for tag in room.tags:
                if tag not in tag_usage:
                    tag_usage[tag] = []
                tag_usage[tag].append(room.room_id)

    # Collect tags from outdoor locations
    for outdoor in index.outdoor_locations.values():
        if outdoor.tags:
            for tag in outdoor.tags:
                if tag not in tag_usage:
                    tag_usage[tag] = []
                tag_usage[tag].append(outdoor.location_id)

    # Format response with usage counts
    tags = [
        {"name": tag, "count": len(entities), "entities": entities}
        for tag, entities in sorted(tag_usage.items())
    ]

    return {"tags": tags}


@app.delete("/admin/cqe/tag/{tag_name}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_tag(tag_name: str):
    """
    Delete a tag from all entities.

    Phase 3: Tag deletion is blocked if any entities use the tag.
    To delete a tag, first remove it from all entities using it.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    tag_name = tag_name.lower().strip()
    index = entity_manager.get_index()

    # Find all entities using this tag
    entities_using_tag = []

    for room in index.rooms.values():
        if room.tags and tag_name in room.tags:
            entities_using_tag.append(room.room_id)

    for outdoor in index.outdoor_locations.values():
        if outdoor.tags and tag_name in outdoor.tags:
            entities_using_tag.append(outdoor.location_id)

    if entities_using_tag:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tag '{tag_name}': used by {len(entities_using_tag)} entity(ies). "
                   f"Remove tag from these entities first: {', '.join(entities_using_tag[:5])}"
                   + (f" and {len(entities_using_tag) - 5} more" if len(entities_using_tag) > 5 else "")
        )

    # Tag not in use - nothing to delete (tag doesn't have standalone storage)
    return {
        "status": "success",
        "message": f"Tag '{tag_name}' is not in use and can be safely removed from any tag lists."
    }


@app.get("/admin/cqe/primary-types", dependencies=[Depends(verify_admin_session)])
async def get_cqe_primary_types():
    """
    Get list of available primary room types.

    Returns:
        { types: ["classroom", "office", "restroom", "other"] }
    """
    from campus_schema import RoomPrimaryType
    return {"types": [pt.value for pt in RoomPrimaryType]}


# ==============================================================================
# Phase 61: CQE Admin Entity CRUD Endpoints
# ==============================================================================

# --- Pydantic Models for CQE Admin ---

class CampusCreate(BaseModel):
    """Request model for creating a campus."""
    name: str
    aliases: List[str] = []
    description: Optional[str] = None  # Phase 5
    landmarks: Optional[str] = None    # Phase 5


class CampusUpdate(BaseModel):
    """Request model for updating a campus."""
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None  # Phase 5
    landmarks: Optional[str] = None    # Phase 5


class BuildingCreate(BaseModel):
    """Request model for creating a building."""
    campus_id: str
    name: str
    aliases: List[str] = []
    description: Optional[str] = None  # Phase 5
    landmarks: Optional[str] = None    # Phase 5


class BuildingUpdate(BaseModel):
    """Request model for updating a building."""
    campus_id: Optional[str] = None
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None  # Phase 5
    landmarks: Optional[str] = None    # Phase 5


class FloorCreate(BaseModel):
    """Request model for creating a floor."""
    building_id: str
    level_number: int
    display_name: str
    aliases: List[str] = []


class FloorUpdate(BaseModel):
    """Request model for updating a floor."""
    building_id: Optional[str] = None
    level_number: Optional[int] = None
    display_name: Optional[str] = None
    aliases: Optional[List[str]] = None


class RoomCreate(BaseModel):
    """Request model for creating a room."""
    room_id: str
    canonical_name: str
    campus_id: str
    building_id: str
    floor_id: str
    room_number: Optional[str] = None
    primary_type: str = "other"
    department_id: Optional[str] = None
    tags: List[str] = []
    aliases: List[str] = []
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"


class RoomUpdate(BaseModel):
    """Request model for updating a room."""
    canonical_name: Optional[str] = None
    campus_id: Optional[str] = None
    building_id: Optional[str] = None
    floor_id: Optional[str] = None
    room_number: Optional[str] = None
    primary_type: Optional[str] = None
    department_id: Optional[str] = None
    tags: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class OutdoorCreate(BaseModel):
    """Request model for creating an outdoor location."""
    location_id: str
    canonical_name: str
    campus_id: str
    tags: List[str] = []
    aliases: List[str] = []
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"


class OutdoorUpdate(BaseModel):
    """Request model for updating an outdoor location."""
    canonical_name: Optional[str] = None
    campus_id: Optional[str] = None
    tags: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DepartmentCreate(BaseModel):
    """Request model for creating a department."""
    name: str
    campus_id: Optional[str] = None
    aliases: List[str] = []
    description: Optional[str] = None
    landmarks: Optional[str] = None  # Phase 5


class DepartmentUpdate(BaseModel):
    """Request model for updating a department."""
    name: Optional[str] = None
    campus_id: Optional[str] = None
    aliases: Optional[List[str]] = None
    description: Optional[str] = None
    landmarks: Optional[str] = None  # Phase 5


# --- Campus CRUD ---

@app.get("/admin/cqe/campus", dependencies=[Depends(verify_admin_session)])
async def list_cqe_campuses():
    """List all campuses with full details."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "campuses": []}

    index = entity_manager.get_index()
    campuses = []
    for c in sorted(index.campuses.values(), key=lambda x: x.name):
        campuses.append({
            "campus_id": c.campus_id,
            "name": c.name,
            "aliases": c.aliases,
            "building_ids": c.building_ids,
            "description": getattr(c, 'description', None),  # Phase 5
            "landmarks": getattr(c, 'landmarks', None),      # Phase 5
            "status": "active"  # Campuses are always active
        })
    return {"campuses": campuses}


@app.post("/admin/cqe/campus", dependencies=[Depends(verify_admin_session)])
async def create_cqe_campus(data: CampusCreate):
    """
    Create a new campus.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    from campus_schema import generate_campus_id
    campus_id = generate_campus_id(data.name)

    index = entity_manager.get_index()
    if campus_id in index.campuses:
        raise HTTPException(status_code=400, detail=f"Campus '{data.name}' already exists")

    # Phase 3: Persist via EntityRegistry
    success, message = entity_registry.add_entity(
        entity_id=campus_id,
        canonical_name=data.name,
        aliases=data.aliases or [data.name.lower()],
        building="",  # Campus has no building
        floor="",     # Campus has no floor
        campus=data.name,  # Campus name is self-referential
        entity_type="campus",
        description=data.description,
        landmarks=data.landmarks,
        child_ids=[]  # Buildings will be added later
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Rebuild CQE index from JSON
    entity_manager.rebuild_index()

    return {"status": "success", "campus_id": campus_id, "message": f"Campus '{data.name}' created"}


@app.put("/admin/cqe/campus/{campus_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_campus(campus_id: str, data: CampusUpdate):
    """
    Update an existing campus.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if campus_id not in index.campuses:
        raise HTTPException(status_code=404, detail=f"Campus '{campus_id}' not found")

    # Phase 3: Check if entity exists in registry, if not create it first
    if campus_id not in entity_registry.entities:
        # Entity only exists in index, create it in registry first
        campus = index.campuses[campus_id]
        entity_registry.add_entity(
            entity_id=campus_id,
            canonical_name=campus.name,
            aliases=campus.aliases,
            building="",
            floor="",
            campus=campus.name,
            entity_type="campus",
            description=getattr(campus, 'description', None),
            landmarks=getattr(campus, 'landmarks', None),
            child_ids=campus.building_ids
        )

    # Phase 3: Update via EntityRegistry
    success, message = entity_registry.update_entity(
        entity_id=campus_id,
        canonical_name=data.name if data.name else None,
        aliases=data.aliases if data.aliases is not None else None,
        description=data.description if data.description is not None else None,
        landmarks=data.landmarks if data.landmarks is not None else None
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Rebuild CQE index from JSON
    entity_manager.rebuild_index()

    return {"status": "success", "message": f"Campus '{campus_id}' updated"}


@app.delete("/admin/cqe/campus/{campus_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_campus(campus_id: str):
    """
    Campus deletion is not allowed.

    Phase 3: Campuses cannot be deleted to maintain data integrity.
    """
    raise HTTPException(
        status_code=403,
        detail="Campus deletion is not allowed. Contact system administrator."
    )


# --- Building CRUD ---

@app.get("/admin/cqe/building", dependencies=[Depends(verify_admin_session)])
async def list_cqe_buildings(campus_id: Optional[str] = None):
    """List all buildings with full details."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "buildings": []}

    index = entity_manager.get_index()
    buildings = []
    for b in sorted(index.buildings.values(), key=lambda x: x.name):
        if campus_id and b.campus_id != campus_id:
            continue
        buildings.append({
            "building_id": b.building_id,
            "name": b.name,
            "aliases": b.aliases,
            "campus_id": b.campus_id,
            "floor_ids": b.floor_ids,
            "description": getattr(b, 'description', None),  # Phase 5
            "landmarks": getattr(b, 'landmarks', None),      # Phase 5
            "status": "active"
        })
    return {"buildings": buildings}


@app.post("/admin/cqe/building", dependencies=[Depends(verify_admin_session)])
async def create_cqe_building(data: BuildingCreate):
    """
    Create a new building.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    from campus_schema import generate_building_id
    building_id = generate_building_id(data.name)

    index = entity_manager.get_index()
    if building_id in index.buildings:
        raise HTTPException(status_code=400, detail=f"Building '{data.name}' already exists")

    if data.campus_id not in index.campuses:
        raise HTTPException(status_code=400, detail=f"Campus '{data.campus_id}' not found")

    # Get campus name from index
    campus_name = index.campuses[data.campus_id].name

    # Phase 3: Persist via EntityRegistry
    success, message = entity_registry.add_entity(
        entity_id=building_id,
        canonical_name=data.name,
        aliases=data.aliases or [data.name.lower()],
        building=data.name,  # Building name stored in building field
        floor="",            # Building has no floor
        campus=campus_name,
        entity_type="building",
        description=data.description,
        landmarks=data.landmarks,
        child_ids=[]  # Floors will be added later
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Rebuild CQE index from JSON
    entity_manager.rebuild_index()

    return {"status": "success", "building_id": building_id, "message": f"Building '{data.name}' created"}


@app.put("/admin/cqe/building/{building_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_building(building_id: str, data: BuildingUpdate):
    """
    Update an existing building.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if building_id not in index.buildings:
        raise HTTPException(status_code=404, detail=f"Building '{building_id}' not found")

    building = index.buildings[building_id]

    # Phase 3: Check if entity exists in registry, if not create it first
    if building_id not in entity_registry.entities:
        # Get campus name
        campus_name = index.campuses.get(building.campus_id, None)
        campus_name = campus_name.name if campus_name else "Main Campus"

        entity_registry.add_entity(
            entity_id=building_id,
            canonical_name=building.name,
            aliases=building.aliases,
            building=building.name,
            floor="",
            campus=campus_name,
            entity_type="building",
            description=getattr(building, 'description', None),
            landmarks=getattr(building, 'landmarks', None),
            child_ids=building.floor_ids
        )

    # Phase 3: Update via EntityRegistry
    update_fields = {}
    if data.name:
        update_fields['canonical_name'] = data.name
        update_fields['building'] = data.name
    if data.aliases is not None:
        update_fields['aliases'] = data.aliases
    if data.campus_id:
        campus = index.campuses.get(data.campus_id)
        if campus:
            update_fields['campus'] = campus.name
    if data.description is not None:
        update_fields['description'] = data.description
    if data.landmarks is not None:
        update_fields['landmarks'] = data.landmarks

    if update_fields:
        success, message = entity_registry.update_entity(entity_id=building_id, **update_fields)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        # Rebuild CQE index from JSON
        entity_manager.rebuild_index()

    return {"status": "success", "message": f"Building '{building_id}' updated"}


@app.delete("/admin/cqe/building/{building_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_building(building_id: str):
    """
    Delete a building.

    Phase 3: Building deletion is blocked if any rooms exist in the building.
    If no rooms exist, the building and all its floors are automatically deleted.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if building_id not in index.buildings:
        raise HTTPException(status_code=404, detail=f"Building '{building_id}' not found")

    # Phase 3: Check for rooms in ANY floor of this building (not just floors)
    rooms_in_building = [r for r in index.rooms.values() if r.building_id == building_id]
    if rooms_in_building:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete building with {len(rooms_in_building)} room(s). Delete all rooms first."
        )

    # No rooms - auto-delete all floors in this building
    floors_to_delete = list(index.floors_by_building.get(building_id, []))
    deleted_floors = []
    for floor_id in floors_to_delete:
        if floor_id in index.floors:
            del index.floors[floor_id]
            deleted_floors.append(floor_id)

    # Clean up floor index
    if building_id in index.floors_by_building:
        del index.floors_by_building[building_id]

    # Delete the building
    building = index.buildings[building_id]
    campus_id = building.campus_id

    # Remove from campus building list
    if campus_id in index.buildings_by_campus:
        if building_id in index.buildings_by_campus[campus_id]:
            index.buildings_by_campus[campus_id].remove(building_id)

    # Remove from campus object
    if campus_id in index.campuses:
        if building_id in index.campuses[campus_id].building_ids:
            index.campuses[campus_id].building_ids.remove(building_id)

    del index.buildings[building_id]

    return {
        "status": "success",
        "message": f"Building '{building_id}' deleted with {len(deleted_floors)} floor(s)",
        "deleted_floors": deleted_floors
    }


# --- Floor CRUD ---

@app.get("/admin/cqe/floor", dependencies=[Depends(verify_admin_session)])
async def list_cqe_floors(building_id: Optional[str] = None):
    """List all floors with full details."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "floors": []}

    index = entity_manager.get_index()
    floors = []
    for f in sorted(index.floors.values(), key=lambda x: (x.building_id, x.level_number)):
        if building_id and f.building_id != building_id:
            continue
        floors.append({
            "floor_id": f.floor_id,
            "building_id": f.building_id,
            "level_number": f.level_number,
            "display_name": f.display_name,
            "aliases": f.aliases,
            "status": "active"
        })
    return {"floors": floors}


@app.post("/admin/cqe/floor", dependencies=[Depends(verify_admin_session)])
async def create_cqe_floor(data: FloorCreate):
    """
    Create a new floor.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    from campus_schema import generate_floor_id

    index = entity_manager.get_index()
    if data.building_id not in index.buildings:
        raise HTTPException(status_code=400, detail=f"Building '{data.building_id}' not found")

    # Generate floor_id using level_number directly (supports any level, not just -1 to 5)
    floor_id = generate_floor_id(data.building_id, data.level_number)

    if floor_id in index.floors:
        raise HTTPException(status_code=400, detail=f"Floor already exists for level {data.level_number}")

    # Get building and campus info
    building = index.buildings[data.building_id]
    campus = index.campuses.get(building.campus_id)
    campus_name = campus.name if campus else "Main Campus"

    # Phase 3: Persist via EntityRegistry
    success, message = entity_registry.add_entity(
        entity_id=floor_id,
        canonical_name=data.display_name,
        aliases=data.aliases or [],
        building=building.name,
        floor=data.display_name,
        campus=campus_name,
        entity_type="floor",
        level_number=data.level_number,
        child_ids=[]  # Rooms will be added later
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Rebuild CQE index from JSON
    entity_manager.rebuild_index()

    return {"status": "success", "floor_id": floor_id, "message": f"Floor '{data.display_name}' created"}


@app.put("/admin/cqe/floor/{floor_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_floor(floor_id: str, data: FloorUpdate):
    """
    Update an existing floor.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if floor_id not in index.floors:
        raise HTTPException(status_code=404, detail=f"Floor '{floor_id}' not found")

    floor = index.floors[floor_id]

    # Phase 3: Check if entity exists in registry, if not create it first
    if floor_id not in entity_registry.entities:
        building = index.buildings.get(floor.building_id)
        campus = index.campuses.get(building.campus_id) if building else None
        campus_name = campus.name if campus else "Main Campus"
        building_name = building.name if building else ""

        entity_registry.add_entity(
            entity_id=floor_id,
            canonical_name=floor.display_name,
            aliases=floor.aliases,
            building=building_name,
            floor=floor.display_name,
            campus=campus_name,
            entity_type="floor",
            level_number=floor.level_number,
            child_ids=floor.room_ids
        )

    # Phase 3: Update via EntityRegistry
    update_fields = {}
    if data.display_name:
        update_fields['canonical_name'] = data.display_name
        update_fields['floor'] = data.display_name
    if data.aliases is not None:
        update_fields['aliases'] = data.aliases
    if data.level_number is not None:
        update_fields['level_number'] = data.level_number

    if update_fields:
        success, message = entity_registry.update_entity(entity_id=floor_id, **update_fields)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        # Rebuild CQE index from JSON
        entity_manager.rebuild_index()

    return {"status": "success", "message": f"Floor '{floor_id}' updated"}


@app.delete("/admin/cqe/floor/{floor_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_floor(floor_id: str):
    """Soft delete a floor (not recommended - has cascading effects)."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if floor_id not in index.floors:
        raise HTTPException(status_code=404, detail=f"Floor '{floor_id}' not found")

    # Check for dependent rooms
    floor = index.floors[floor_id]
    dependent_rooms = [r for r in index.rooms.values() if r.floor_id == floor_id]
    if dependent_rooms:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete floor with {len(dependent_rooms)} room(s)"
        )

    del index.floors[floor_id]
    return {"status": "success", "message": f"Floor '{floor_id}' deleted"}


# --- Room CRUD ---

@app.get("/admin/cqe/room", dependencies=[Depends(verify_admin_session)])
async def list_cqe_rooms(
    campus_id: Optional[str] = None,
    building_id: Optional[str] = None,
    floor_id: Optional[str] = None,
    primary_type: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None
):
    """
    List rooms with optional filters.

    Args:
        campus_id: Filter by campus
        building_id: Filter by building
        floor_id: Filter by floor
        primary_type: Filter by primary type (classroom, office, restroom, other)
        status: Filter by status (active, inactive)
        q: Search query for name/aliases
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "rooms": []}

    index = entity_manager.get_index()
    rooms = []

    for r in sorted(index.rooms.values(), key=lambda x: x.canonical_name):
        # Apply filters
        if campus_id and r.campus_id != campus_id:
            continue
        if building_id and r.building_id != building_id:
            continue
        if floor_id and r.floor_id != floor_id:
            continue
        if primary_type and r.primary_type.value != primary_type.lower():
            continue
        if status and r.status != status.lower():
            continue
        if q:
            q_lower = q.lower()
            if (q_lower not in r.canonical_name.lower() and
                not any(q_lower in a for a in r.aliases)):
                continue

        rooms.append({
            "room_id": r.room_id,
            "canonical_name": r.canonical_name,
            "room_number": r.room_number,
            "campus_id": r.campus_id,
            "building_id": r.building_id,
            "floor_id": r.floor_id,
            "primary_type": r.primary_type.value,
            "tags": r.tags,
            "aliases": r.aliases,
            "department_id": r.department_id,
            "landmarks": r.landmarks,
            "description": r.description,
            "status": r.status
        })

    return {"rooms": rooms}


@app.post("/admin/cqe/room", dependencies=[Depends(verify_admin_session)])
async def create_cqe_room(data: RoomCreate):
    """Create a new room (persists to JSON and rebuilds index)."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()

    # Validate references
    if data.campus_id not in index.campuses:
        raise HTTPException(status_code=400, detail=f"Campus '{data.campus_id}' not found")
    if data.building_id not in index.buildings:
        raise HTTPException(status_code=400, detail=f"Building '{data.building_id}' not found")
    if data.floor_id not in index.floors:
        raise HTTPException(status_code=400, detail=f"Floor '{data.floor_id}' not found")

    # Get building and floor names for flat entity format
    building = index.buildings[data.building_id]
    floor = index.floors[data.floor_id]
    campus = index.campuses[data.campus_id]

    # Create flat entity via entity_manager
    entity_data = {
        "entity_id": data.room_id.upper(),
        "canonical_name": data.canonical_name,
        "building": building.name,
        "floor": floor.display_name,
        "room": data.room_number,
        "campus": campus.name,
        "department": None,
        "aliases": data.aliases,
        "tags": data.tags,
        "landmarks": data.landmarks,
        "description": data.description,
        "status": data.status
    }

    # Handle department
    if data.department_id and data.department_id in index.departments:
        entity_data["department"] = index.departments[data.department_id].name

    success, message, result = entity_manager.create_entity(entity_data)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.create_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "room_id": data.room_id.upper(),
        "message": f"Room '{data.canonical_name}' created",
        "warnings": result.warnings if result else []
    }


@app.put("/admin/cqe/room/{room_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_room(room_id: str, data: RoomUpdate):
    """Update an existing room (persists to JSON and rebuilds index)."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    room_id = room_id.upper()
    index = entity_manager.get_index()

    if room_id not in index.rooms:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    # Build update data for flat entity
    update_data = {}
    if data.canonical_name:
        update_data["canonical_name"] = data.canonical_name
    if data.building_id:
        if data.building_id not in index.buildings:
            raise HTTPException(status_code=400, detail=f"Building '{data.building_id}' not found")
        update_data["building"] = index.buildings[data.building_id].name
    if data.floor_id:
        if data.floor_id not in index.floors:
            raise HTTPException(status_code=400, detail=f"Floor '{data.floor_id}' not found")
        update_data["floor"] = index.floors[data.floor_id].display_name
    if data.campus_id:
        if data.campus_id not in index.campuses:
            raise HTTPException(status_code=400, detail=f"Campus '{data.campus_id}' not found")
        update_data["campus"] = index.campuses[data.campus_id].name
    if data.room_number is not None:
        update_data["room"] = data.room_number
    if data.aliases is not None:
        update_data["aliases"] = data.aliases
    if data.tags is not None:
        update_data["tags"] = data.tags
    if data.landmarks is not None:
        update_data["landmarks"] = data.landmarks
    if data.description is not None:
        update_data["description"] = data.description
    if data.status:
        update_data["status"] = data.status

    success, message, result = entity_manager.update_entity(room_id, update_data)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.update_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "message": f"Room '{room_id}' updated",
        "warnings": result.warnings if result else []
    }


@app.delete("/admin/cqe/room/{room_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_room(room_id: str, hard: bool = False):
    """
    Delete a room (soft or hard delete).

    Args:
        room_id: Room ID to delete
        hard: If True, permanently remove; if False, set status to inactive
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    room_id = room_id.upper()

    success, message = entity_manager.delete_entity(room_id, hard=hard)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.delete_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "message": f"Room '{room_id}' {'permanently deleted' if hard else 'deactivated'}"
    }


# --- OutdoorLocation CRUD ---

@app.get("/admin/cqe/outdoor", dependencies=[Depends(verify_admin_session)])
async def list_cqe_outdoor_locations(
    campus_id: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None
):
    """List outdoor locations with optional filters."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "outdoor_locations": []}

    index = entity_manager.get_index()
    locations = []

    for o in sorted(index.outdoor_locations.values(), key=lambda x: x.canonical_name):
        if campus_id and o.campus_id != campus_id:
            continue
        if status and o.status != status.lower():
            continue
        if q:
            q_lower = q.lower()
            if (q_lower not in o.canonical_name.lower() and
                not any(q_lower in a for a in o.aliases)):
                continue

        locations.append({
            "location_id": o.location_id,
            "canonical_name": o.canonical_name,
            "campus_id": o.campus_id,
            "tags": o.tags,
            "aliases": o.aliases,
            "landmarks": o.landmarks,
            "description": o.description,
            "status": o.status
        })

    return {"outdoor_locations": locations}


@app.post("/admin/cqe/outdoor", dependencies=[Depends(verify_admin_session)])
async def create_cqe_outdoor_location(data: OutdoorCreate):
    """Create a new outdoor location (persists to JSON and rebuilds index)."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()

    # Validate campus
    if data.campus_id not in index.campuses:
        raise HTTPException(status_code=400, detail=f"Campus '{data.campus_id}' not found")

    campus = index.campuses[data.campus_id]

    # Create flat entity with _OUTDOOR marker
    entity_data = {
        "entity_id": data.location_id.upper(),
        "canonical_name": data.canonical_name,
        "building": "_OUTDOOR",
        "floor": "_OUTDOOR",
        "campus": campus.name,
        "aliases": data.aliases,
        "tags": data.tags,
        "landmarks": data.landmarks,
        "description": data.description,
        "status": data.status
    }

    success, message, result = entity_manager.create_entity(entity_data)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.create_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "location_id": data.location_id.upper(),
        "message": f"Outdoor location '{data.canonical_name}' created",
        "warnings": result.warnings if result else []
    }


@app.put("/admin/cqe/outdoor/{location_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_outdoor_location(location_id: str, data: OutdoorUpdate):
    """Update an existing outdoor location."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    location_id = location_id.upper()
    index = entity_manager.get_index()

    if location_id not in index.outdoor_locations:
        raise HTTPException(status_code=404, detail=f"Outdoor location '{location_id}' not found")

    # Build update data
    update_data = {
        "building": "_OUTDOOR",
        "floor": "_OUTDOOR"
    }
    if data.canonical_name:
        update_data["canonical_name"] = data.canonical_name
    if data.campus_id:
        if data.campus_id not in index.campuses:
            raise HTTPException(status_code=400, detail=f"Campus '{data.campus_id}' not found")
        update_data["campus"] = index.campuses[data.campus_id].name
    if data.aliases is not None:
        update_data["aliases"] = data.aliases
    if data.tags is not None:
        update_data["tags"] = data.tags
    if data.landmarks is not None:
        update_data["landmarks"] = data.landmarks
    if data.description is not None:
        update_data["description"] = data.description
    if data.status:
        update_data["status"] = data.status

    success, message, result = entity_manager.update_entity(location_id, update_data)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.update_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "message": f"Outdoor location '{location_id}' updated",
        "warnings": result.warnings if result else []
    }


@app.delete("/admin/cqe/outdoor/{location_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_outdoor_location(location_id: str, hard: bool = False):
    """Delete an outdoor location (soft or hard delete)."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    location_id = location_id.upper()

    success, message = entity_manager.delete_entity(location_id, hard=hard)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Phase 4: EntityManager.delete_entity() already calls rebuild_index() internally

    return {
        "status": "success",
        "message": f"Outdoor location '{location_id}' {'permanently deleted' if hard else 'deactivated'}"
    }


# --- Department CRUD ---

@app.get("/admin/cqe/department", dependencies=[Depends(verify_admin_session)])
async def list_cqe_departments_full():
    """List all departments with full details."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        return {"error": "Campus Query Engine not enabled", "departments": []}

    index = entity_manager.get_index()
    departments = []
    for d in sorted(index.departments.values(), key=lambda x: x.name):
        departments.append({
            "department_id": d.department_id,
            "name": d.name,
            "aliases": d.aliases,
            "campus_id": d.campus_id,
            "description": d.description,
            "landmarks": getattr(d, 'landmarks', None),  # Phase 5
            "status": "active"
        })
    return {"departments": departments}


@app.post("/admin/cqe/department", dependencies=[Depends(verify_admin_session)])
async def create_cqe_department(data: DepartmentCreate):
    """
    Create a new department.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    from campus_schema import normalize_id
    department_id = normalize_id(data.name)

    index = entity_manager.get_index()
    if department_id in index.departments:
        raise HTTPException(status_code=400, detail=f"Department '{data.name}' already exists")

    # Get campus name
    campus = index.campuses.get(data.campus_id)
    campus_name = campus.name if campus else "Main Campus"

    # Phase 3: Persist via EntityRegistry
    success, message = entity_registry.add_entity(
        entity_id=department_id,
        canonical_name=data.name,
        aliases=data.aliases or [data.name.lower()],
        building="",  # Department has no building
        floor="",     # Department has no floor
        campus=campus_name,
        entity_type="department",
        description=data.description,
        landmarks=data.landmarks,
        office_room_ids=[]  # Office rooms will be added later
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Rebuild CQE index from JSON
    entity_manager.rebuild_index()

    return {"status": "success", "department_id": department_id, "message": f"Department '{data.name}' created"}


@app.put("/admin/cqe/department/{department_id}", dependencies=[Depends(verify_admin_session)])
async def update_cqe_department(department_id: str, data: DepartmentUpdate):
    """
    Update an existing department.

    Phase 3 (Arch Remediation): Persists to JSON via EntityRegistry.
    """
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if department_id not in index.departments:
        raise HTTPException(status_code=404, detail=f"Department '{department_id}' not found")

    dept = index.departments[department_id]

    # Phase 3: Check if entity exists in registry, if not create it first
    if department_id not in entity_registry.entities:
        campus = index.campuses.get(dept.campus_id)
        campus_name = campus.name if campus else "Main Campus"

        entity_registry.add_entity(
            entity_id=department_id,
            canonical_name=dept.name,
            aliases=dept.aliases,
            building="",
            floor="",
            campus=campus_name,
            entity_type="department",
            description=dept.description,
            landmarks=getattr(dept, 'landmarks', None),
            office_room_ids=dept.office_room_ids
        )

    # Phase 3: Update via EntityRegistry
    update_fields = {}
    if data.name:
        update_fields['canonical_name'] = data.name
    if data.aliases is not None:
        update_fields['aliases'] = data.aliases
    if data.campus_id is not None:
        campus = index.campuses.get(data.campus_id)
        if campus:
            update_fields['campus'] = campus.name
    if data.description is not None:
        update_fields['description'] = data.description
    if data.landmarks is not None:
        update_fields['landmarks'] = data.landmarks

    if update_fields:
        success, message = entity_registry.update_entity(entity_id=department_id, **update_fields)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        # Rebuild CQE index from JSON
        entity_manager.rebuild_index()

    return {"status": "success", "message": f"Department '{department_id}' updated"}


@app.delete("/admin/cqe/department/{department_id}", dependencies=[Depends(verify_admin_session)])
async def delete_cqe_department(department_id: str):
    """Soft delete a department."""
    if not CAMPUS_QUERY_ENGINE_ENABLED:
        raise HTTPException(status_code=400, detail="Campus Query Engine not enabled")

    index = entity_manager.get_index()
    if department_id not in index.departments:
        raise HTTPException(status_code=404, detail=f"Department '{department_id}' not found")

    # Check for rooms using this department
    dependent_rooms = [r for r in index.rooms.values() if r.department_id == department_id]
    if dependent_rooms:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete department with {len(dependent_rooms)} room(s) assigned"
        )

    del index.departments[department_id]
    return {"status": "success", "message": f"Department '{department_id}' deleted"}


@app.get("/admin/cqe")
async def serve_cqe_admin():
    """Serve the CQE Admin interface."""
    return FileResponse(PROJECT_ROOT / "static" / "cqe-admin.html")


# ==============================================================================
# ADMIN LOGIN/LOGOUT ENDPOINTS
# ==============================================================================

class LoginRequest(BaseModel):
    """Login request model."""
    password: str


@app.get("/admin/login")
async def serve_login_page():
    """Serve the admin login page."""
    return FileResponse(PROJECT_ROOT / "static" / "login.html")


@app.post("/admin/login")
async def admin_login(login_data: LoginRequest, response: Response):
    """
    Authenticate admin and create session.

    Args:
        login_data: Login credentials (password)
        response: FastAPI response object for setting cookies

    Returns:
        Success message with redirect URL
    """
    if login_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Create session and set cookie
    token = create_admin_session()
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=int(ADMIN_SESSION_DURATION.total_seconds())
    )

    return {"status": "success", "message": "Login successful", "redirect": "/admin"}


@app.post("/admin/logout", dependencies=[Depends(verify_admin_session)])
async def admin_logout(request: Request, response: Response):
    """
    Logout admin and destroy session.

    Args:
        request: FastAPI request object
        response: FastAPI response object for clearing cookies

    Returns:
        Success message with redirect URL
    """
    token = request.cookies.get("admin_session")
    if token:
        invalidate_admin_session(token)

    response.delete_cookie(key="admin_session")
    return {"status": "success", "message": "Logout successful", "redirect": "/admin/login"}


@app.get("/admin")
async def serve_admin_ui():
    """Serve the admin interface."""
    return FileResponse(PROJECT_ROOT / "static" / "admin.html")


# ==============================================================================
# MOUNT STATIC FILES
# ==============================================================================

# Serve static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

# Serve images from project root images directory (for logo, etc.)
app.mount("/images", StaticFiles(directory=PROJECT_ROOT.parent / "images"), name="images")


# ==============================================================================
# STARTUP/SHUTDOWN
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("="*80)
    print("Campus Information Kiosk API - Phase 32 (Voice Integration)")
    print("="*80)
    print(f"Documents loaded: {len(doc_manager.list_documents())}")

    # Phase 32: Initialize voice services
    try:
        from voice.config import VOICE_CONFIG, is_voice_enabled, log_config_summary
        from voice import STTService, TTSService, VoiceOrchestrator
        from voice.provider_registry import ProviderRegistry

        if is_voice_enabled():
            # Load persisted voice settings and apply to VOICE_CONFIG
            # This ensures admin-configured providers (e.g., Google STT) are used after restart
            try:
                registry = ProviderRegistry()
                saved_settings = registry.load_settings()
                if saved_settings.stt_provider:
                    VOICE_CONFIG['stt']['primary']['engine'] = saved_settings.stt_provider
                    logger.info(f"[VOICE] Applied saved STT provider: {saved_settings.stt_provider}")
                if saved_settings.tts_provider:
                    VOICE_CONFIG['tts']['primary']['engine'] = saved_settings.tts_provider
                    logger.info(f"[VOICE] Applied saved TTS provider: {saved_settings.tts_provider}")
            except Exception as e:
                logger.warning(f"[VOICE] Could not load saved voice settings: {e}")

            stt_service = STTService(VOICE_CONFIG.get('stt', {}))
            tts_service = TTSService(VOICE_CONFIG.get('tts', {}))

            # Create orchestrator with chat handler
            async def voice_chat_handler(message: str, session_id: str):
                """Handle chat for voice interactions - routes to existing chat logic."""
                # Create a minimal request object
                class VoiceChatRequest:
                    def __init__(self, msg, sid):
                        self.message = msg
                        self.session_id = sid

                request = VoiceChatRequest(message, session_id)
                # Call the existing chat endpoint logic
                response = await chat(request)
                # Phase 35: Include structured_answer for unified rendering
                structured = None
                if response.structured_answer:
                    structured = response.structured_answer.dict()
                # Phase 39B: Include debug_info for debug panel
                debug_info = None
                if response.debug_info:
                    debug_info = response.debug_info.dict()
                return {
                    "answer": response.answer,
                    "mode": response.mode,
                    "confidence": response.confidence_level,
                    "confidence_score": response.confidence_score,
                    "sources": [s.dict() for s in response.sources],
                    "rejected": response.rejected,
                    "structured_answer": structured,
                    "debug_info": debug_info,
                }

            orchestrator = VoiceOrchestrator(
                stt_service=stt_service,
                tts_service=tts_service,
                chat_handler=voice_chat_handler,
                event_tracker=event_tracker
            )

            # Initialize voice routes with services
            voice_routes.init_voice_services(
                orchestrator=orchestrator,
                stt=stt_service,
                tts=tts_service
            )

            log_config_summary()
            print(f"Voice services: ENABLED (STT: {stt_service.is_available()}, TTS: {tts_service.is_available()})")
        else:
            print("Voice services: DISABLED (set VOICE_ENABLED=true to enable)")

    except ImportError as e:
        print(f"Voice services: NOT AVAILABLE (missing dependencies: {e})")
    except Exception as e:
        print(f"Voice services: INITIALIZATION FAILED ({e})")
        logger.exception("[VOICE] Failed to initialize voice services")

    print(f"API ready at: http://localhost:8000")
    print(f"Kiosk interface at: http://localhost:8000/")
    print(f"Voice status at: http://localhost:8000/voice/status")
    print("="*80)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("Shutting down API...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
