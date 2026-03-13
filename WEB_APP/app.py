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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Header, Depends, Request, Response
from sse_starlette.sse import EventSourceResponse  # Phase 42: SSE for test harness streaming
import httpx  # Phase 42: Async HTTP client for internal API calls

# Phase 14.1: Set up logging for clarification flow debugging
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import shutil
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_classic.memory import ConversationBufferWindowMemory

# Load environment variables from WEB_APP/.env (explicit path so it works
# regardless of working directory, e.g. when launched via systemd)
_APP_DIR = Path(__file__).parent  # WEB_APP/
load_dotenv(_APP_DIR / ".env")

# Import existing modules
from WEB_APP.modules.document_manager import DocumentManager
from WEB_APP.modules.query_logger import QueryLogger
from WEB_APP.modules.advertisement_manager import AdvertisementManager  # Phase 48: Advertisement panel
from WEB_APP.modules.faq_manager import FAQManager  # FAQ management
from WEB_APP.modules.event_tracker import EventTracker, EventType  # Phase 16: Observability

# Phase 44: LLM-as-Final-Synthesizer Architecture
from WEB_APP.modules.response_orchestrator import ResponseOrchestrator, ResponseMode

# Phase 32: Voice Integration
import WEB_APP.modules.voice_routes as voice_routes

# Phase 39A: Credential Management
from WEB_APP.modules.credential_manager import init_credential_manager, get_credential_manager
from WEB_APP.modules import trivia_manager

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ADMIN_PASSWORD must load first — it's the encryption key for credential storage
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD environment variable not set. Please add it to .env file.")

# Phase 39A: Initialize credential manager and apply encrypted credentials to os.environ
# This MUST happen before validating OPENAI_API_KEY so that keys stored via
# the admin UI are available even when .env doesn't contain them.
try:
    _cred_manager = init_credential_manager(ADMIN_PASSWORD, Path(__file__).parent)
    if _cred_manager.is_available():
        _applied = _cred_manager.apply_to_environment()
        if _applied > 0:
            logger.info(f"[STARTUP] Applied {_applied} credentials from encrypted storage")
except Exception as e:
    logger.warning(f"[STARTUP] Credential manager init failed: {e}")

# Now validate required keys (may come from .env OR encrypted storage)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
if not ADMIN_API_KEY:
    raise ValueError("ADMIN_API_KEY environment variable not set. Please add it to .env file.")

DEV_PASSWORD = os.getenv("DEV_PASSWORD")
if not DEV_PASSWORD:
    raise ValueError("DEV_PASSWORD environment variable not set. Please add it to .env file.")

PROJECT_ROOT = Path(__file__).parent / "modules"
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"
LOG_DIR = PROJECT_ROOT / "logs"

# API settings
RETRIEVAL_TOP_K = 8  # Phase 17C: Increased from 4 for complete enumeration
RELEVANCE_SCORE_THRESHOLD = 0.5
MEMORY_WINDOW_SIZE = 5

# Session settings (chat sessions)
SESSION_TIMEOUT_MINUTES = 30
sessions: Dict[str, Dict] = {}  # In-memory session storage

# Admin session settings
ADMIN_SESSION_DURATION = timedelta(hours=8)
admin_sessions: Dict[str, datetime] = {}  # {session_token: expiry_datetime}

# Phase 39B: Debug panel mode (persisted to debug_settings.json)
# Phase 50: Extended to include metadata_visible setting
DEBUG_SETTINGS_PATH = PROJECT_ROOT / "data" / "debug_settings.json"
debug_mode_enabled: bool = False
metadata_visible: bool = True  # Phase 50: Default to showing metadata
dev_section_visible: bool = True  # Controls Developer section visibility in admin sidebar
fusion_method: str = "linear"  # "linear" or "rrf" — hybrid score combination method
fusion_label_visible: bool = True  # Show fusion mode label in kiosk responses
rrf_k: int = 60  # RRF k parameter (default 60)
voice_advanced_visible: bool = False  # Show advanced voice config elements in admin


def load_debug_settings() -> dict:
    """Load debug/developer settings from JSON file."""
    global debug_mode_enabled, metadata_visible, dev_section_visible
    global fusion_method, fusion_label_visible, rrf_k, voice_advanced_visible
    try:
        if DEBUG_SETTINGS_PATH.exists():
            import json
            with open(DEBUG_SETTINGS_PATH, 'r') as f:
                data = json.load(f)
            debug_mode_enabled = data.get('debug_enabled', False)
            metadata_visible = data.get('metadata_visible', True)
            dev_section_visible = data.get('dev_section_visible', True)
            fusion_method = data.get('fusion_method', 'linear')
            fusion_label_visible = data.get('fusion_label_visible', True)
            rrf_k = data.get('rrf_k', 60)
            voice_advanced_visible = data.get('voice_advanced_visible', False)
            return data
    except Exception as e:
        logger.warning(f"[DEBUG] Failed to load debug settings: {e}")
    return {"debug_enabled": False, "metadata_visible": True, "dev_section_visible": True,
            "fusion_method": "linear", "fusion_label_visible": True, "rrf_k": 60,
            "voice_advanced_visible": False, "updated_at": None}


def save_debug_settings(debug_enabled: bool = None, metadata_visible_setting: bool = None,
                        dev_section_visible_setting: bool = None, fusion_method_setting: str = None,
                        fusion_label_visible_setting: bool = None, rrf_k_setting: int = None,
                        voice_advanced_visible_setting: bool = None) -> dict:
    """Save debug/developer settings to JSON file.

    Only updates the fields that are passed (not None).
    """
    global debug_mode_enabled, metadata_visible, dev_section_visible
    global fusion_method, fusion_label_visible, rrf_k, voice_advanced_visible
    try:
        import json
        DEBUG_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Read current file without updating globals
        current = {"debug_enabled": debug_mode_enabled, "metadata_visible": metadata_visible,
                    "dev_section_visible": dev_section_visible, "fusion_method": fusion_method,
                    "fusion_label_visible": fusion_label_visible, "rrf_k": rrf_k}
        if DEBUG_SETTINGS_PATH.exists():
            try:
                with open(DEBUG_SETTINGS_PATH, 'r') as f:
                    current = json.load(f)
            except Exception:
                pass

        # Update only the fields that were passed
        if debug_enabled is not None:
            debug_mode_enabled = debug_enabled
            current['debug_enabled'] = debug_enabled
        if metadata_visible_setting is not None:
            metadata_visible = metadata_visible_setting
            current['metadata_visible'] = metadata_visible_setting
        if dev_section_visible_setting is not None:
            dev_section_visible = dev_section_visible_setting
            current['dev_section_visible'] = dev_section_visible_setting
        if fusion_method_setting is not None:
            fusion_method = fusion_method_setting
            current['fusion_method'] = fusion_method_setting
        if fusion_label_visible_setting is not None:
            fusion_label_visible = fusion_label_visible_setting
            current['fusion_label_visible'] = fusion_label_visible_setting
        if rrf_k_setting is not None:
            rrf_k = rrf_k_setting
            current['rrf_k'] = rrf_k_setting
        if voice_advanced_visible_setting is not None:
            voice_advanced_visible = voice_advanced_visible_setting
            current['voice_advanced_visible'] = voice_advanced_visible_setting

        current['updated_at'] = datetime.utcnow().isoformat() + 'Z'

        with open(DEBUG_SETTINGS_PATH, 'w') as f:
            json.dump(current, f, indent=2)

        return current
    except Exception as e:
        logger.error(f"[DEBUG] Failed to save debug settings: {e}")
        return {"debug_enabled": debug_mode_enabled, "metadata_visible": metadata_visible,
                "dev_section_visible": dev_section_visible, "fusion_method": fusion_method,
                "fusion_label_visible": fusion_label_visible, "rrf_k": rrf_k,
                "voice_advanced_visible": voice_advanced_visible, "updated_at": None}


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
    raise RuntimeError(
        "No vector store found. This server runs in RUNTIME MODE only.\n"
        "To create a vector store:\n"
        "  1. On your dev machine: python ingest.py <documents_folder> (from INGESTION_MODULE)\n"
        "  2. Upload via Admin UI > RAG Package, OR\n"
        "  3. Copy vector_store/ folder and restart server"
    )

# Phase 25: Load metadata index
from WEB_APP.modules.metadata_index import MetadataIndex
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

# Phase 47: Streaming LLM instance for SSE responses
llm_streaming = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0,
    openai_api_key=OPENAI_API_KEY,
    streaming=True
)

# Initialize Response Orchestrator (Phase 44: LLM-as-Final-Synthesizer)
# Singleton instance reused across all requests
response_orchestrator = ResponseOrchestrator(
    llm=llm,
    doc_manager=doc_manager,
    config={
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "relevance_threshold": RELEVANCE_SCORE_THRESHOLD,
        "min_grounding_terms": 1,
        "semantic_threshold_high": 0.78,
        "semantic_threshold_medium": 0.65
    }
)
logger.info("[PHASE44] ResponseOrchestrator initialized (singleton)")

# Phase 47: Streaming Response Orchestrator
response_orchestrator_streaming = ResponseOrchestrator(
    llm=llm_streaming,
    doc_manager=doc_manager,
    config={
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "relevance_threshold": RELEVANCE_SCORE_THRESHOLD,
        "min_grounding_terms": 1,
        "semantic_threshold_high": 0.78,
        "semantic_threshold_medium": 0.65
    }
)
logger.info("[PHASE47] Streaming ResponseOrchestrator initialized")


def _reload_llm(new_api_key: str):
    """Recreate LLM instances and orchestrators with a new OpenAI API key."""
    global llm, llm_streaming, response_orchestrator, response_orchestrator_streaming, OPENAI_API_KEY
    OPENAI_API_KEY = new_api_key
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=new_api_key)
    llm_streaming = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=new_api_key, streaming=True)
    orch_config = {
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "relevance_threshold": RELEVANCE_SCORE_THRESHOLD,
        "min_grounding_terms": 1,
        "semantic_threshold_high": 0.78,
        "semantic_threshold_medium": 0.65,
    }
    response_orchestrator = ResponseOrchestrator(llm=llm, doc_manager=doc_manager, config=orch_config)
    response_orchestrator_streaming = ResponseOrchestrator(llm=llm_streaming, doc_manager=doc_manager, config=orch_config)
    logger.info("[CREDENTIALS] LLM instances recreated with new OpenAI API key")


# Initialize query logger
query_logger = QueryLogger(log_dir=LOG_DIR)

# Initialize event tracker for observability (Phase 16)
event_tracker = EventTracker(log_dir=LOG_DIR)

# Initialize advertisement manager for kiosk display (Phase 48)
advertisement_manager = AdvertisementManager(data_dir=PROJECT_ROOT / "data")
logger.info(f"[PHASE48] AdvertisementManager initialized")

# Initialize FAQ manager
faq_manager = FAQManager(data_dir=PROJECT_ROOT / "data")
logger.info(f"[FAQ] FAQManager initialized")

# ==============================================================================
# PHASE 49: WELCOME MESSAGE CONFIGURATION
# ==============================================================================

WELCOME_CONFIG_PATH = PROJECT_ROOT / "data" / "welcome_config.json"

DEFAULT_WELCOME_MESSAGE = """Welcome! I can help you with information about:

- Library hours and services
- Dining options and meal plans
- Parking and transportation
- IT services and Wi-Fi
- Student employment
- Campus events and activities

What would you like to know?"""


def load_welcome_config() -> dict:
    """Load welcome message configuration from JSON file."""
    if WELCOME_CONFIG_PATH.exists():
        try:
            with open(WELCOME_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[WELCOME] Failed to load config: {e}")
    return {
        "version": "1.0",
        "message": DEFAULT_WELCOME_MESSAGE,
        "updated_at": None
    }


def save_welcome_config(message: str) -> dict:
    """Save welcome message configuration to JSON file."""
    config = {
        "version": "1.0",
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(WELCOME_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(f"[WELCOME] Config saved")
    return config


logger.info(f"[PHASE49] Welcome message config initialized")

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
    retrieval_method: str = "hybrid"
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
    metadata_visible: bool = True  # Phase 51: Include visibility setting in each response
    fusion_mode: str = "linear"  # "linear" or "rrf" — actual fusion method used
    fusion_label_visible: bool = True  # Whether kiosk should render fusion label


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
            "last_campus": None,
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

def get_conversation_context(session: Dict) -> Dict:
    """Get the conversation context for follow-up query handling."""
    return session.get("conversation_context", {})


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
# DEVELOPER AUTHENTICATION
# ==============================================================================

DEV_SESSION_DURATION = timedelta(hours=8)
dev_sessions: Dict[str, datetime] = {}  # {session_token: expiry_datetime}


def cleanup_expired_dev_sessions():
    """Remove expired dev sessions."""
    now = datetime.now()
    expired = [token for token, expiry in dev_sessions.items() if now > expiry]
    for token in expired:
        del dev_sessions[token]


def create_dev_session() -> str:
    """Create a new dev session and return the token."""
    cleanup_expired_dev_sessions()
    token = secrets.token_urlsafe(32)
    dev_sessions[token] = datetime.now() + DEV_SESSION_DURATION
    return token


def validate_dev_session(token: str) -> bool:
    """Check if a dev session token is valid."""
    if not token or token not in dev_sessions:
        return False
    if datetime.now() > dev_sessions[token]:
        del dev_sessions[token]
        return False
    return True


def invalidate_dev_session(token: str):
    """Remove a dev session."""
    if token in dev_sessions:
        del dev_sessions[token]


async def verify_dev_session(request: Request):
    """
    Verify dev session for protected endpoints.

    Raises:
        HTTPException: If session is missing or invalid

    Returns:
        True if authenticated
    """
    token = request.cookies.get("dev_session")
    if not validate_dev_session(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
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

    # Get conversation context for document clarification
    context = get_conversation_context(session)

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
                debug_info=_clarification_debug_info,
                metadata_visible=metadata_visible,
                fusion_mode=fusion_method,
                fusion_label_visible=fusion_label_visible
            )

    # === PHASE 44: LLM-AS-FINAL-SYNTHESIZER ARCHITECTURE ===
    # All response paths now go through the orchestrator which terminates in LLM synthesis
    # Uses module-level singleton (response_orchestrator) for efficiency
    _orchestrator_start = time.perf_counter()

    # Process query through singleton orchestrator
    orchestrated = response_orchestrator.process_query(
        query=query,
        session_id=session_id,
        memory=memory
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

    # Generate a single timestamp for both log and response (feedback linking)
    response_ts = datetime.now().isoformat()

    # Log the conversation (query + answer only)
    query_logger.log_conversation(query=query, answer=orchestrated.answer or "", timestamp=response_ts)

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
        timestamp=response_ts,
        mode=mode_str,
        debug_info=_debug_info,
        metadata_visible=metadata_visible,
        fusion_mode=orchestrated.fusion_method,
        fusion_label_visible=fusion_label_visible
    )


# ==============================================================================
# PHASE 47: STREAMING CHAT ENDPOINT
# ==============================================================================

class StreamChatRequest(BaseModel):
    """Streaming chat request model."""
    message: str
    session_id: Optional[str] = None


@app.post("/chat/stream")
async def chat_stream(request: StreamChatRequest):
    """
    Handle a chat message with streaming response via SSE.

    Returns Server-Sent Events with progressive token delivery.

    Event types:
    - metadata: Sources, confidence, mode (sent first)
    - token: Individual LLM tokens
    - complete: Timing and final status
    - error: Error information

    Args:
        request: Chat request with message and optional session_id

    Returns:
        EventSourceResponse with streaming events
    """
    import json

    # Get or create session
    session_id, session = get_or_create_session(request.session_id)
    memory = session["memory"]
    session["query_count"] += 1

    query = request.message.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def generate():
        """SSE event generator."""
        try:
            async for event in response_orchestrator_streaming.process_query_streaming(
                query=query,
                session_id=session_id,
                memory=memory,
                metadata_visible=metadata_visible  # Phase 51
            ):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }
        except Exception as e:
            logger.error(f"[STREAM] Error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "code": "stream_error"})
            }

    return EventSourceResponse(generate())


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for a response.

    Updates the feedback field in the conversation log entry
    whose timestamp matches request.query_id.
    """
    found = query_logger.update_feedback(
        query_id=request.query_id,
        is_helpful=request.is_helpful,
    )
    if not found:
        logger.warning(f"[Feedback] No conversation found for query_id={request.query_id}")

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
    DEPRECATED: Document upload/ingestion is no longer supported on the server.

    The server runs in RUNTIME MODE only - it loads pre-built vector stores
    but does not perform document ingestion.

    To add documents:
    1. Run ingestion on your development machine:
       python ingest.py <documents_folder> (from INGESTION_MODULE)
    2. Upload the generated .zip package via /admin/upload_rag_package

    Returns:
        410 Gone: Endpoint deprecated
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Document ingestion is no longer supported on the server. "
            "Use the standalone ingestion module on your development machine: "
            "python ingest.py <documents_folder> (from INGESTION_MODULE). "
            "Then upload the RAG package via Admin UI > RAG Package."
        )
    )


# ==============================================================================
# RAG PACKAGE UPLOAD - Runtime Vector Store Replacement
# ==============================================================================

@app.post("/admin/upload_rag_package", dependencies=[Depends(verify_admin_session)])
async def upload_rag_package(file: UploadFile = File(...)):
    """
    Upload and replace the vector store with a new RAG package.

    Accepts a .zip file containing:
    - vector_store/index.faiss (required)
    - vector_store/index.pkl (required)
    - document_registry.json (optional)

    The vector store is replaced atomically with backup/rollback on failure.
    After successful upload, the vector store is reloaded in memory.

    Returns:
        Success response with document count
    """
    global doc_manager, metadata_index
    import zipfile
    import tempfile

    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail="File must be a .zip archive"
        )

    logger.info(f"[RAG_UPLOAD] Received package: {file.filename}")

    try:
        # Save to temp location
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "upload.zip"

            # Save uploaded file
            content = await file.read()
            with open(zip_path, "wb") as f:
                f.write(content)

            logger.info(f"[RAG_UPLOAD] Saved zip ({len(content)} bytes)")

            # Extract zip
            extract_dir = temp_path / "extracted"
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            except zipfile.BadZipFile:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid zip file"
                )

            # Find vector_store folder (may be at root or nested)
            vs_path = None
            for root, dirs, files in os.walk(extract_dir):
                if "index.faiss" in files and "index.pkl" in files:
                    vs_path = Path(root)
                    break

            if not vs_path:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid package: missing index.faiss or index.pkl"
                )

            logger.info(f"[RAG_UPLOAD] Found vector store at: {vs_path}")

            # Validate required files
            required_files = ["index.faiss", "index.pkl"]
            for req in required_files:
                if not (vs_path / req).exists():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing required file: {req}"
                    )

            # Atomic replacement with backup
            target = VECTOR_STORE_PATH
            backup = target.parent / "vector_store_backup_upload"

            # Backup existing
            if target.exists():
                if backup.exists():
                    shutil.rmtree(backup)
                shutil.move(str(target), str(backup))
                logger.info(f"[RAG_UPLOAD] Backed up existing vector store")

            try:
                # Copy new vector store
                shutil.copytree(str(vs_path), str(target))
                logger.info(f"[RAG_UPLOAD] Copied new vector store")

                # Check for document_registry.json at package root or vs folder
                registry_path = None
                for check_path in [
                    extract_dir / "document_registry.json",
                    vs_path / "document_registry.json",
                    vs_path.parent / "document_registry.json"
                ]:
                    if check_path.exists():
                        registry_path = check_path
                        break

                if registry_path:
                    shutil.copy(str(registry_path), str(REGISTRY_PATH))
                    logger.info(f"[RAG_UPLOAD] Copied document registry from {registry_path}")
                    # Reload registry into memory
                    doc_manager.registry.documents = doc_manager.registry._load_registry()
                    logger.info(f"[RAG_UPLOAD] Reloaded document registry: {len(doc_manager.registry.documents)} documents")
                else:
                    logger.warning(f"[RAG_UPLOAD] No document_registry.json found in package")

                # Reload vector store in memory
                doc_manager.load_vector_store()

                if doc_manager.vector_store is None:
                    raise Exception("Failed to load new vector store")

                # Rebuild metadata index
                metadata_index.build_from_vector_store(doc_manager.vector_store)
                metadata_index.save()
                logger.info(f"[RAG_UPLOAD] Rebuilt metadata index")

                # Remove backup on success
                if backup.exists():
                    shutil.rmtree(backup)

                # Get document count from registry
                doc_count = len(doc_manager.registry.documents) if doc_manager.registry.documents else 0

                logger.info(f"[RAG_UPLOAD] Success! {doc_count} documents loaded")

                return {
                    "success": True,
                    "message": "RAG package uploaded and loaded successfully",
                    "documents": doc_count
                }

            except Exception as e:
                # Restore backup on failure
                logger.error(f"[RAG_UPLOAD] Failed: {e}")
                if backup.exists():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.move(str(backup), str(target))
                    doc_manager.load_vector_store()
                    logger.info(f"[RAG_UPLOAD] Restored backup")
                raise HTTPException(
                    status_code=500,
                    detail=f"Upload failed, restored previous vector store: {str(e)}"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RAG_UPLOAD] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


# ==============================================================================
# DEVELOPER TOOLS
# ==============================================================================

class DevLoginRequest(BaseModel):
    """Login request model for developer tools."""
    password: str


class DevSectionToggleRequest(BaseModel):
    """Request model for toggling developer section visibility."""
    enabled: bool


class FusionMethodRequest(BaseModel):
    """Request model for setting fusion method."""
    method: str  # "linear" or "rrf"
    rrf_k: Optional[int] = None


class FusionLabelToggleRequest(BaseModel):
    """Request model for toggling fusion label visibility."""
    enabled: bool

class VoiceAdvancedToggleRequest(BaseModel):
    """Request model for toggling voice advanced config visibility."""
    enabled: bool


@app.get("/dev/login")
async def serve_dev_login_page():
    """Serve the developer login page."""
    return FileResponse(PROJECT_ROOT / "static" / "dev_login.html")


@app.post("/dev/login")
async def dev_login(login_data: DevLoginRequest, response: Response):
    """Authenticate developer and create session."""
    if login_data.password != DEV_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_dev_session()
    response.set_cookie(
        key="dev_session",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=int(DEV_SESSION_DURATION.total_seconds())
    )

    return {"status": "success", "message": "Login successful", "redirect": "/dev"}


@app.get("/dev")
async def dev_page(request: Request):
    """Serve the developer tools page (requires dev auth)."""
    token = request.cookies.get("dev_session")
    if not validate_dev_session(token):
        return RedirectResponse(url="/dev/login")
    return FileResponse(PROJECT_ROOT / "static" / "dev.html")


@app.get("/dev/settings", dependencies=[Depends(verify_dev_session)])
async def get_dev_settings():
    """Get developer settings."""
    return {
        "dev_section_visible": dev_section_visible,
        "fusion_method": fusion_method,
        "fusion_label_visible": fusion_label_visible,
        "rrf_k": rrf_k,
        "voice_advanced_visible": voice_advanced_visible
    }


@app.post("/dev/settings/dev-section-visible", dependencies=[Depends(verify_dev_session)])
async def toggle_dev_section_visible(request: DevSectionToggleRequest):
    """Toggle Developer section visibility in admin sidebar."""
    save_debug_settings(dev_section_visible_setting=request.enabled)
    logger.info(f"[DEV] Developer section visibility: {'shown' if request.enabled else 'hidden'}")
    return {
        "success": True,
        "dev_section_visible": dev_section_visible,
        "message": f"Developer section {'shown' if request.enabled else 'hidden'} in admin sidebar"
    }


@app.post("/dev/settings/fusion-method", dependencies=[Depends(verify_dev_session)])
async def set_fusion_method(request: FusionMethodRequest):
    """Set hybrid fusion method (linear or rrf)."""
    if request.method not in ("linear", "rrf"):
        raise HTTPException(status_code=400, detail="Invalid fusion method. Must be 'linear' or 'rrf'.")
    rrf_k_val = request.rrf_k if request.rrf_k is not None else rrf_k
    save_debug_settings(fusion_method_setting=request.method, rrf_k_setting=rrf_k_val)
    logger.info(f"[DEV] Fusion method set to: {fusion_method} (rrf_k={rrf_k})")
    return {
        "success": True,
        "fusion_method": fusion_method,
        "rrf_k": rrf_k,
        "message": f"Fusion method set to {fusion_method}"
    }


@app.post("/dev/settings/fusion-label-visible", dependencies=[Depends(verify_dev_session)])
async def toggle_fusion_label_visible(request: FusionLabelToggleRequest):
    """Toggle fusion mode label visibility in kiosk responses."""
    save_debug_settings(fusion_label_visible_setting=request.enabled)
    logger.info(f"[DEV] Fusion label visibility: {'shown' if request.enabled else 'hidden'}")
    return {
        "success": True,
        "fusion_label_visible": fusion_label_visible,
        "message": f"Fusion label {'shown' if request.enabled else 'hidden'} in responses"
    }


@app.post("/dev/settings/voice-advanced-visible", dependencies=[Depends(verify_dev_session)])
async def toggle_voice_advanced_visible(request: VoiceAdvancedToggleRequest):
    """Toggle voice advanced config visibility in admin voice page."""
    save_debug_settings(voice_advanced_visible_setting=request.enabled)
    logger.info(f"[DEV] Voice advanced config visibility: {'shown' if request.enabled else 'hidden'}")
    return {
        "success": True,
        "voice_advanced_visible": voice_advanced_visible,
        "message": f"Voice advanced config {'shown' if request.enabled else 'hidden'}"
    }


@app.get("/api/settings/dev-section-visible")
async def get_dev_section_visibility():
    """Public read-only endpoint: whether Developer section is visible in admin sidebar."""
    return {"dev_section_visible": dev_section_visible}


@app.get("/api/settings/voice-advanced-visible")
async def get_voice_advanced_visibility():
    """Public read-only endpoint: whether voice advanced config is visible."""
    return {"voice_advanced_visible": voice_advanced_visible}


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
    Get analytics for admin dashboard.

    Derives all metrics from conversations.jsonl (the unified source of truth).
    Legacy event-tracker metrics were frozen after Phase 44 introduced the
    response orchestrator, so they are no longer displayed.
    """
    total = 0
    feedback = {"liked": 0, "disliked": 0, "no_feedback": 0}

    log_path = LOG_DIR / "conversations.jsonl"
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        total += 1
                        fb = entry.get("feedback")
                        if fb is True:
                            feedback["liked"] += 1
                        elif fb is False:
                            feedback["disliked"] += 1
                        else:
                            feedback["no_feedback"] += 1
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    return {"total_conversations": total, "feedback": feedback}


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


@app.get("/admin/analytics/conversations", dependencies=[Depends(verify_admin_session)])
async def get_conversations(
    page: int = 1,
    per_page: int = 20,
    month: Optional[str] = None,
    search: Optional[str] = None,
    feedback: Optional[str] = None,
):
    """
    Paginated conversation log viewer for admin.

    Reads from the unified conversations.jsonl (newest-first).
    Supports optional filtering by calendar month (YYYY-MM), keyword search,
    and feedback status (liked / disliked / unrated).
    """
    per_page = max(1, min(per_page, 100))
    page = max(1, page)

    log_path = LOG_DIR / "conversations.jsonl"
    if not log_path.exists():
        return {
            "conversations": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0,
        }

    # Parse month filter
    filter_year: Optional[int] = None
    filter_month: Optional[int] = None
    if month:
        try:
            parts = month.split("-")
            filter_year, filter_month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass

    search_lower = search.lower().strip() if search else None
    feedback_filter = feedback.strip().lower() if feedback else None
    if feedback_filter not in ("liked", "disliked", "unrated"):
        feedback_filter = None

    # Read and filter entries (bounded by 2-month retention)
    entries: list = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Month filter
                if filter_year and filter_month:
                    ts_raw = entry.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw[:19])
                        if ts.year != filter_year or ts.month != filter_month:
                            continue
                    except ValueError:
                        continue

                # Keyword search
                if search_lower:
                    query_text  = (entry.get("query") or "").lower()
                    answer_text = (entry.get("answer") or "").lower()
                    if search_lower not in query_text and search_lower not in answer_text:
                        continue

                # Derive feedback status from inline field
                fb_val = entry.get("feedback")
                if fb_val is True:
                    fb_status = "liked"
                elif fb_val is False:
                    fb_status = "disliked"
                else:
                    fb_status = "unrated"

                # Feedback filter
                if feedback_filter and fb_status != feedback_filter:
                    continue

                entry["_feedback"] = fb_status
                entries.append(entry)

    except OSError as e:
        logger.error(f"[Conversations] Could not read conversations.jsonl: {e}")

    # Sort newest-first
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    total = len(entries)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    start = (page - 1) * per_page
    end = start + per_page
    page_entries = entries[start:end]

    conversations = []
    for e in page_entries:
        conversations.append({
            "query_id":  e.get("query_id", ""),
            "timestamp": e.get("timestamp", ""),
            "query":     e.get("query", ""),
            "answer":    e.get("answer", ""),
            "feedback":  e.get("_feedback", "unrated"),
        })

    return {
        "conversations": conversations,
        "total":         total,
        "page":          page,
        "per_page":      per_page,
        "total_pages":   total_pages,
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
        from WEB_APP.modules.voice.provider_registry import get_registry
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
        from WEB_APP.modules.voice.provider_registry import get_registry
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
        from WEB_APP.modules.voice.provider_registry import get_registry, VoiceSettings
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
            from WEB_APP.modules.voice_routes import reload_voice_services
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

@app.get("/admin/voice/usage", dependencies=[Depends(verify_admin_session)])
async def get_voice_usage():
    """
    Get STT usage statistics for Google Cloud STT.

    Phase 38: Returns current month's usage against the 60-minute free tier quota.
    Creates a fresh tracker each call so it reads the latest data from disk
    (the file is written by voice_routes when transcriptions occur).

    Returns:
        Usage statistics including used/remaining seconds and percentage
    """
    try:
        from WEB_APP.modules.voice.usage_tracker import STTUsageTracker
        tracker = STTUsageTracker(Path(__file__).parent / "data")
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
        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"Invalid JSON: {str(e)}"}

        # Structure checks
        if creds_data.get('type') != 'service_account':
            return {
                "valid": False,
                "error": "Not a valid service account JSON (missing 'type' field or wrong type)"
            }

        if 'project_id' not in creds_data:
            return {"valid": False, "error": "Missing 'project_id' field"}

        # Real authentication test: obtain an access token from Google's
        # auth servers using the service account credentials.  This validates
        # the private key and client_email without making an STT API call.
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request

            credentials = service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            import asyncio
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: credentials.refresh(Request())
            )

            return {
                "valid": True,
                "project_id": creds_data.get('project_id'),
                "client_email": creds_data.get('client_email', 'N/A')
            }
        except ImportError:
            # google-cloud-speech not installed — fall back to structure check
            return {
                "valid": True,
                "project_id": creds_data.get('project_id'),
                "client_email": creds_data.get('client_email', 'N/A'),
                "note": "Structure valid. Google Cloud SDK not installed for full verification."
            }
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"[ADMIN] Google credential verification failed: {error_msg}")
            return {
                "valid": False,
                "error": "Authentication failed. Service account credentials are invalid or lack permissions."
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

        # Real API validation: list models (lightweight, no quota consumed)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=request.api_key)
            client.models.list()
            return {
                "valid": True,
                "note": "API key verified successfully."
            }
        except ImportError:
            return {
                "valid": True,
                "note": "Format valid. OpenAI SDK not installed for full verification."
            }
        except Exception as e:
            # Any failure from the API call means the key is invalid or
            # unreachable.  Don't assume validity on network errors —
            # the user should retry when connectivity is restored.
            logger.warning(f"[ADMIN] OpenAI key verification failed: {e}")
            return {
                "valid": False,
                "error": "API key verification failed. Key may be invalid, expired, or the API is unreachable."
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
            from WEB_APP.modules.voice_routes import reload_voice_services
            from WEB_APP.modules.voice.provider_registry import get_registry
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

        # Update environment variable and reload LLM instances
        os.environ["OPENAI_API_KEY"] = request.api_key
        _reload_llm(request.api_key)
        logger.info("[ADMIN] OpenAI API key updated and LLM reloaded")

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

    result = save_debug_settings(debug_enabled=request.enabled)

    if result:
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
# PHASE 50: METADATA VISIBILITY ENDPOINTS
# ==============================================================================

@app.get("/api/settings")
async def get_display_settings():
    """
    Get display settings for chatbot UI (public endpoint).

    Phase 50: Returns metadata visibility setting for frontend rendering.
    """
    return {
        "metadata_visible": metadata_visible
    }


@app.get("/admin/metadata/status", dependencies=[Depends(verify_admin_session)])
async def get_metadata_status():
    """
    Get metadata visibility status.

    Phase 50: Returns whether response metadata (confidence, score, sources) is visible.
    """
    settings = load_debug_settings()
    return {
        "metadata_visible": settings.get("metadata_visible", True),
        "updated_at": settings.get("updated_at")
    }


class MetadataToggleRequest(BaseModel):
    """Request body for metadata visibility toggle."""
    enabled: bool


@app.post("/admin/metadata/toggle", dependencies=[Depends(verify_admin_session)])
async def toggle_metadata_visibility(request: MetadataToggleRequest):
    """
    Toggle metadata visibility in response bubbles.

    Phase 50: Enables/disables confidence, score, and sources display in chatbot responses.
    """
    global metadata_visible

    result = save_debug_settings(metadata_visible_setting=request.enabled)

    if result:
        logger.info(f"[ADMIN] Metadata visibility {'enabled' if request.enabled else 'disabled'}")
        return {
            "success": True,
            "metadata_visible": metadata_visible,
            "message": "Response metadata visible" if request.enabled else "Response metadata hidden"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to save metadata settings"
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


async def execute_single_test(question: Dict) -> Dict:
    """Execute a single test question against the streaming chat endpoint.

    Uses /chat/stream (the same endpoint as the chatbot UI) to ensure
    the test harness exercises the exact same processing pipeline.
    Parses SSE events and reconstructs a response dict matching ChatResponse.
    """
    session_id = f"test-harness-{uuid.uuid4()}"

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:8000/chat/stream",
                json={"message": question["question"], "session_id": session_id},
                timeout=60.0
            ) as sse_response:
                metadata = {}
                full_answer = ""
                complete_data = {}
                current_event = None

                async for line in sse_response.aiter_lines():
                    line = line.strip()
                    if not line:
                        current_event = None
                        continue
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            parsed = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if current_event == "metadata":
                            metadata = parsed
                        elif current_event == "token":
                            full_answer += parsed.get("content", "")
                        elif current_event == "complete":
                            complete_data = parsed
                        elif current_event == "error":
                            return {"error": parsed.get("message", "Stream error")}

                # Reconstruct response in ChatResponse-compatible format.
                # Normalize streaming debug_info field names to match
                # the DebugInfo model used by evaluate_test_result().
                debug_info = metadata.get("debug_info") or {}
                if debug_info:
                    # Map streaming field names → DebugInfo field names
                    if "extractor_name" in debug_info and "extractor_used" not in debug_info:
                        debug_info["extractor_used"] = debug_info["extractor_name"]
                    if "grounded" in debug_info and "grounding_passed" not in debug_info:
                        debug_info["grounding_passed"] = debug_info["grounded"]

                return {
                    "session_id": metadata.get("session_id", session_id),
                    "answer": full_answer,
                    "sources": metadata.get("sources", []),
                    "confidence_level": metadata.get("confidence_level", "N/A"),
                    "confidence_score": metadata.get("confidence_score", 0),
                    "grounding_mode": metadata.get("grounding_mode", "unknown"),
                    "rejected": complete_data.get("rejected", False),
                    "timestamp": datetime.now().isoformat(),
                    "mode": metadata.get("mode", "unknown"),
                    "extractor_used": metadata.get("extractor_used"),
                    "debug_info": debug_info,
                    "metadata_visible": metadata.get("metadata_visible", True),
                    "fusion_mode": metadata.get("fusion_mode"),
                    "fusion_label_visible": metadata.get("fusion_label_visible", False)
                }
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

    # Check for exact error response match
    answer_text = response.get("answer", "")
    ERROR_MESSAGE = "I apologize, but I encountered an error processing your question. Please try again."
    if answer_text.strip() == ERROR_MESSAGE:
        failures.append("System error response")

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

    # Parse timestamp for formatted date/time
    timestamp = results.get('timestamp', '')
    try:
        ts = datetime.fromisoformat(timestamp)
        test_date = ts.strftime('%Y-%m-%d')
        test_time = ts.strftime('%H:%M')
    except (ValueError, TypeError):
        test_date = 'Unknown'
        test_time = 'Unknown'

    summary = results["summary"]

    # Build text report
    lines = []
    lines.append("=" * 80)
    lines.append("TEST HARNESS RESULTS - CoCo RAG Chatbot")
    lines.append("=" * 80)
    lines.append(f"Test Run: {test_date}")
    lines.append(f"Time: {test_time}")
    lines.append(f"Total Test Cases: {summary['total']}")
    lines.append("")

    # Individual results
    for i, result in enumerate(results.get("results", []), 1):
        status = "PASS" if result["passed"] else "FAIL"
        lines.append(f"Question No.: {i} - {status}")
        lines.append(result["query"])

        response = result.get("response", {})
        answer = response.get("answer", "No response") if response else "No response received"
        lines.append("Response:")
        lines.append(answer)
        lines.append("-" * 40)

    # Summary section
    lines.append("")
    lines.append("=" * 80)
    lines.append("TEST SUMMARY")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Total Tests:  {summary['total']}")
    lines.append(f"Passed:       {summary['passed']}")
    lines.append(f"Failed:       {summary['failed']}")
    lines.append(f"Pass Rate:    {summary['pass_rate']}%")
    lines.append("")

    # Failed tests list
    failed_tests = [r for r in results.get("results", []) if not r["passed"]]
    if failed_tests:
        lines.append("FAILED TESTS:")
        lines.append("-" * 80)
        for i, result in enumerate(failed_tests, 1):
            lines.append(f"  {i}. {result['query']}")

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
# ADVERTISEMENT MANAGEMENT ENDPOINTS (PHASE 48)
# ==============================================================================

@app.get("/api/advertisements")
async def get_advertisements():
    """
    Get all active advertisements for the kiosk display.

    This is a public endpoint (no auth required) for the frontend slideshow.
    Supports both image and text advertisements (Phase 54).

    Returns:
        List of active advertisements with display data
    """
    ads = advertisement_manager.list_active()
    result = []
    for ad in ads:
        display_data = advertisement_manager.get_display_data(ad)
        result.append({
            "id": ad.id,
            "ad_type": ad.ad_type,
            "display_order": ad.display_order,
            **display_data  # Includes 'url' for images, 'content' for text
        })
    return {"advertisements": result}


@app.get("/admin/advertisements", dependencies=[Depends(verify_admin_session)])
async def admin_list_advertisements():
    """
    Get all advertisements for admin management.

    Returns:
        List of all advertisements with full metadata (supports image and text types)
    """
    ads = advertisement_manager.list_all()
    result = []
    for ad in ads:
        ad_data = {
            "id": ad.id,
            "ad_type": ad.ad_type,
            "uploaded_at": ad.uploaded_at,
            "status": ad.status,
            "display_order": ad.display_order
        }
        if ad.ad_type == "image":
            ad_data.update({
                "filename": ad.filename,
                "original_name": ad.original_name,
                "url": advertisement_manager.get_image_url(ad),
                "mime_type": ad.mime_type,
                "file_size": ad.file_size
            })
        else:  # text
            ad_data.update({
                "content": ad.content
            })
        result.append(ad_data)
    return {"advertisements": result}


@app.post("/admin/advertisements/upload", dependencies=[Depends(verify_admin_session)])
async def upload_advertisement(file: UploadFile = File(...)):
    """
    Upload a new advertisement image.

    Args:
        file: Image file (JPG, JPEG, PNG, max 5MB)

    Returns:
        The created advertisement data
    """
    # Read file content
    content = await file.read()

    try:
        ad = await advertisement_manager.upload(
            filename=file.filename,
            content_type=file.content_type,
            file_data=content
        )
        return {
            "status": "success",
            "message": f"Advertisement '{file.filename}' uploaded successfully",
            "advertisement": {
                "id": ad.id,
                "ad_type": "image",
                "filename": ad.filename,
                "original_name": ad.original_name,
                "url": advertisement_manager.get_image_url(ad),
                "uploaded_at": ad.uploaded_at,
                "display_order": ad.display_order
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/admin/advertisements/{ad_id}", dependencies=[Depends(verify_admin_session)])
async def delete_advertisement(ad_id: str):
    """
    Delete an advertisement.

    Args:
        ad_id: Advertisement ID

    Returns:
        Success message
    """
    if not advertisement_manager.delete(ad_id):
        raise HTTPException(status_code=404, detail=f"Advertisement '{ad_id}' not found")

    return {
        "status": "success",
        "message": "Advertisement deleted successfully",
        "id": ad_id
    }


class ReorderRequest(BaseModel):
    """Request model for reordering advertisements."""
    ad_ids: List[str]


@app.post("/admin/advertisements/reorder", dependencies=[Depends(verify_admin_session)])
async def reorder_advertisements(request: ReorderRequest):
    """
    Reorder advertisements.

    Args:
        request: List of advertisement IDs in new order

    Returns:
        Success message
    """
    if not advertisement_manager.reorder(request.ad_ids):
        raise HTTPException(status_code=400, detail="Failed to reorder advertisements")

    return {
        "status": "success",
        "message": f"Reordered {len(request.ad_ids)} advertisements"
    }


# ==============================================================================
# PHASE 54: TEXT ADVERTISEMENT ENDPOINTS
# ==============================================================================

class TextAdRequest(BaseModel):
    """Request model for creating/updating text advertisements."""
    content: str


class EnhanceTextRequest(BaseModel):
    """Request model for AI text enhancement."""
    content: str


@app.post("/admin/advertisements/text", dependencies=[Depends(verify_admin_session)])
async def create_text_advertisement(request: TextAdRequest):
    """
    Create a new text-based advertisement.

    Args:
        request: Text content for the advertisement

    Returns:
        The created advertisement data
    """
    try:
        ad = advertisement_manager.create_text_ad(request.content)
        return {
            "status": "success",
            "message": "Text advertisement created successfully",
            "advertisement": {
                "id": ad.id,
                "ad_type": "text",
                "content": ad.content,
                "uploaded_at": ad.uploaded_at,
                "display_order": ad.display_order
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/admin/advertisements/text/{ad_id}", dependencies=[Depends(verify_admin_session)])
async def update_text_advertisement(ad_id: str, request: TextAdRequest):
    """
    Update an existing text advertisement.

    Args:
        ad_id: Advertisement ID
        request: New text content

    Returns:
        The updated advertisement data
    """
    try:
        ad = advertisement_manager.update_text_ad(ad_id, request.content)
        if not ad:
            raise HTTPException(status_code=404, detail=f"Advertisement '{ad_id}' not found")
        return {
            "status": "success",
            "message": "Text advertisement updated successfully",
            "advertisement": {
                "id": ad.id,
                "ad_type": "text",
                "content": ad.content,
                "uploaded_at": ad.uploaded_at,
                "display_order": ad.display_order
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/advertisements/enhance", dependencies=[Depends(verify_admin_session)])
async def enhance_advertisement_text(request: EnhanceTextRequest):
    """
    Enhance advertisement text using AI.

    Takes raw text and returns an improved, more engaging version.
    Does NOT save the result - just returns the enhanced text for preview.

    Args:
        request: Text to enhance

    Returns:
        Enhanced text for preview
    """
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="Text content cannot be empty")

    content = request.content.strip()
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="Text too long for enhancement (max 2000 chars)")

    try:
        # Use the LLM to enhance the text
        enhancement_prompt = f"""You are an advertising copywriter for a college campus kiosk display.

Enhance the following advertisement text to be more engaging and professional.
Keep it concise (under 200 characters if possible) as it will be displayed on a kiosk screen.
Maintain the core message but make it more compelling.
Do not add quotation marks around the result.
Do not include any preamble or explanation - just return the enhanced text.

Original text:
{content}

Enhanced text:"""

        messages = [HumanMessage(content=enhancement_prompt)]
        response = llm.invoke(messages)
        enhanced_text = response.content.strip()

        # Clean up any surrounding quotes
        if enhanced_text.startswith('"') and enhanced_text.endswith('"'):
            enhanced_text = enhanced_text[1:-1]

        return {
            "status": "success",
            "original": content,
            "enhanced": enhanced_text
        }
    except Exception as e:
        logger.error(f"[ADS] AI enhancement failed: {e}")
        raise HTTPException(status_code=500, detail="AI enhancement failed. Please try again.")


# ==============================================================================
# PHASE 49: WELCOME MESSAGE ENDPOINTS
# ==============================================================================

@app.get("/api/welcome")
async def get_welcome_message():
    """
    Get welcome message for chatbot UI.

    This is a public endpoint (no auth required) for the frontend to display
    the welcome message when a new conversation starts.

    Returns:
        Welcome message text and image URL
    """
    config = load_welcome_config()
    return {
        "message": config["message"],
        "image_url": "/images/coco-name.jpg"
    }


@app.get("/admin/welcome", dependencies=[Depends(verify_admin_session)])
async def admin_get_welcome():
    """
    Get welcome message configuration for admin editing.

    Returns:
        Full welcome config including version and timestamp
    """
    return load_welcome_config()


class WelcomeMessageUpdate(BaseModel):
    """Request model for welcome message updates."""
    message: str


@app.post("/admin/welcome", dependencies=[Depends(verify_admin_session)])
async def admin_update_welcome(request: WelcomeMessageUpdate):
    """
    Update the welcome message.

    Args:
        request: New welcome message text

    Returns:
        Success status and updated config
    """
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    config = save_welcome_config(message)
    return {
        "status": "success",
        "message": "Welcome message updated",
        "data": config
    }


# ==============================================================================
# PHASE 56: TRIVIA, STUDY TIPS & QUOTES ENDPOINTS
# ==============================================================================

@app.get("/api/trivia/today")
async def get_trivia_today():
    """
    Get today's trivia and study tip.
    No LLM calls - returns pre-generated content.
    """
    content = trivia_manager.get_today_content()
    return content


@app.get("/api/trivia/quote")
async def get_random_quote():
    """
    Get a random quote from the stored 50.
    Called when user clicks "Draw Quote" button.
    """
    quote = trivia_manager.get_random_quote()
    return {"quote": quote}


@app.get("/api/trivia/status")
async def get_trivia_status():
    """Get content generation status."""
    status = trivia_manager.get_content_status()
    return status


@app.get("/admin/trivia/content", dependencies=[Depends(verify_admin_session)])
async def admin_get_trivia_content():
    """
    Get all generated content for admin view.
    Shows trivia, study tips, and quotes.
    """
    return {
        "status": trivia_manager.get_content_status(),
        "trivia": trivia_manager.get_all_trivia(),
        "study_tips": trivia_manager.get_all_study_tips(),
        "quotes": trivia_manager.get_all_quotes()
    }


@app.post("/admin/trivia/regenerate", dependencies=[Depends(verify_admin_session)])
async def admin_regenerate_trivia():
    """
    Force regeneration of monthly content.
    Admin-only endpoint for debugging/testing.
    """
    logger.info("[TRIVIA] Admin requested content regeneration")
    success = trivia_manager.initialize_trivia_content(force=True)
    if success:
        return {
            "status": "success",
            "message": "Content regenerated",
            "data": trivia_manager.get_content_status()
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to regenerate content. Check logs for details."
        )


# ==============================================================================
# FAQ ENDPOINTS
# ==============================================================================

class FAQCreate(BaseModel):
    """Request model for creating a FAQ."""
    question: str
    answer: str


class FAQUpdate(BaseModel):
    """Request model for updating a FAQ."""
    question: Optional[str] = None
    answer: Optional[str] = None
    status: Optional[str] = None


class FAQReorder(BaseModel):
    """Request model for reordering FAQs."""
    ordered_ids: List[str]


class FAQGenerateRequest(BaseModel):
    """Request model for Ask CoCo FAQ generation."""
    question: str


@app.get("/api/faqs")
async def get_faqs():
    """
    Get all active FAQs for kiosk display.

    Returns:
        List of FAQ items with config
    """
    return {
        "faqs": faq_manager.get_all(include_inactive=False),
        "config": faq_manager.get_config()
    }


@app.get("/admin/faqs")
async def admin_get_faqs(request: Request):
    """
    Get all FAQs for admin management.

    Returns:
        List of all FAQ items including inactive
    """
    validate_admin_session(request)
    return {
        "faqs": faq_manager.get_all(include_inactive=True),
        "config": faq_manager.get_config()
    }


@app.post("/admin/faqs")
async def admin_create_faq(request: Request, faq_data: FAQCreate):
    """
    Create a new FAQ item.

    Args:
        faq_data: Question and answer data

    Returns:
        Created FAQ item
    """
    validate_admin_session(request)
    try:
        faq = faq_manager.add(faq_data.question, faq_data.answer)
        return {"status": "success", "faq": faq}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/admin/faqs/{faq_id}")
async def admin_update_faq(request: Request, faq_id: str, faq_data: FAQUpdate):
    """
    Update an existing FAQ item.

    Args:
        faq_id: The FAQ ID to update
        faq_data: Updated data

    Returns:
        Updated FAQ item
    """
    validate_admin_session(request)
    try:
        faq = faq_manager.update(
            faq_id,
            question=faq_data.question,
            answer=faq_data.answer,
            status=faq_data.status
        )
        return {"status": "success", "faq": faq}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/admin/faqs/{faq_id}")
async def admin_delete_faq(request: Request, faq_id: str):
    """
    Delete a FAQ item.

    Args:
        faq_id: The FAQ ID to delete

    Returns:
        Success status
    """
    validate_admin_session(request)
    if not faq_manager.delete(faq_id):
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"status": "success", "message": "FAQ deleted"}


@app.post("/admin/faqs/reorder")
async def admin_reorder_faqs(request: Request, reorder_data: FAQReorder):
    """
    Reorder FAQ items.

    Args:
        reorder_data: List of FAQ IDs in desired order

    Returns:
        Updated list of FAQs
    """
    validate_admin_session(request)
    try:
        faqs = faq_manager.reorder(reorder_data.ordered_ids)
        return {"status": "success", "faqs": faqs}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/faqs/generate")
async def admin_generate_faq_answer(request: Request, gen_request: FAQGenerateRequest):
    """
    Generate a FAQ answer using the LLM (Ask CoCo).

    Args:
        gen_request: The question to generate an answer for

    Returns:
        Generated answer suggestion
    """
    validate_admin_session(request)

    if not gen_request.question or not gen_request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Use the response orchestrator to generate a FAQ-style answer
        # Note: process_query is synchronous, returns OrchestratedResponse dataclass
        result = response_orchestrator.process_query(
            query=gen_request.question.strip(),
            session_id="faq_generation",
            memory=None
        )

        # Extract the answer from the OrchestratedResponse
        answer = result.answer or ''

        # Clean up the answer for FAQ format (remove excessive formatting)
        if answer:
            # Remove markdown headers if present
            lines = answer.split('\n')
            cleaned_lines = [line for line in lines if not line.startswith('#')]
            answer = '\n'.join(cleaned_lines).strip()

        logger.info(f"[FAQ] Generated answer for question: {gen_request.question[:50]}... (confidence: {result.confidence_level})")

        return {
            "status": "success",
            "question": gen_request.question.strip(),
            "generated_answer": answer,
            "confidence": result.confidence_level or 'MEDIUM'
        }
    except Exception as e:
        logger.error(f"[FAQ] Error generating answer: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate answer: {str(e)}"
        )


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
# KIOSK CONTROL ENDPOINTS
# ==============================================================================

class KioskAuthRequest(BaseModel):
    """Kiosk admin authentication request."""
    password: str


@app.post("/admin/kiosk/auth")
async def kiosk_auth(data: KioskAuthRequest):
    """
    Validate kiosk admin password (one-time check, no session).
    Used by the kiosk overlay to verify admin identity before actions.
    """
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"status": "success"}


@app.post("/admin/kiosk/shutdown")
async def kiosk_shutdown(data: KioskAuthRequest):
    """
    Shutdown the Raspberry Pi. Requires admin password.
    Only executes on Linux (RPi). No-op on other platforms.
    """
    import platform
    import subprocess

    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    if platform.system() != "Linux":
        return {"status": "skipped", "message": "Shutdown only available on Raspberry Pi (Linux)."}

    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return {"status": "success", "message": "Shutdown command sent. The device will power off shortly."}
    except Exception as e:
        logger.error(f"[KIOSK] Shutdown failed: {e}")
        raise HTTPException(status_code=500, detail=f"Shutdown failed: {e}")


@app.post("/admin/kiosk/reboot")
async def kiosk_reboot(data: KioskAuthRequest):
    """
    Reboot the Raspberry Pi system. Requires admin password.
    Only executes on Linux (RPi). No-op on other platforms.
    """
    import platform
    import subprocess

    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    if platform.system() != "Linux":
        return {"status": "skipped", "message": "Reboot only available on Raspberry Pi (Linux)."}

    try:
        subprocess.Popen(["sudo", "reboot"])
        return {"status": "success", "message": "Reboot command sent. The device will restart shortly."}
    except Exception as e:
        logger.error(f"[KIOSK] Reboot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reboot failed: {e}")


@app.get("/admin/kiosk/wifi")
async def kiosk_wifi():
    """
    Get the currently connected WiFi SSID.
    Only works on Linux (RPi). Returns null SSID on other platforms.
    """
    import platform
    import subprocess

    if platform.system() != "Linux":
        return {"ssid": None, "message": "WiFi info only available on Raspberry Pi (Linux)."}

    try:
        result = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True, text=True, timeout=5
        )
        ssid = result.stdout.strip()
        if ssid:
            return {"ssid": ssid}
        else:
            return {"ssid": None, "message": "No WiFi connection detected"}
    except FileNotFoundError:
        # iwgetid not available, try nmcli
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("yes:"):
                    ssid = line.split(":", 1)[1]
                    return {"ssid": ssid}
            return {"ssid": None, "message": "No WiFi connection detected"}
        except Exception:
            return {"ssid": None, "message": "Unable to determine WiFi status"}
    except Exception as e:
        logger.error(f"[KIOSK] WiFi check failed: {e}")
        return {"ssid": None, "message": "Unable to determine WiFi status"}


class WifiConnectRequest(BaseModel):
    """WiFi connection request."""
    password: str
    ssid: str
    wifi_password: str = ""


@app.post("/admin/kiosk/wifi/scan")
async def kiosk_wifi_scan(data: KioskAuthRequest):
    """
    Scan for available WiFi networks using nmcli.
    Requires admin password. Only works on Linux (RPi).
    """
    import platform
    import subprocess

    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    if platform.system() != "Linux":
        return {"networks": [], "message": "WiFi scan only available on Raspberry Pi (Linux)."}

    try:
        # Step 1: Force a fresh WiFi scan on the radio hardware.
        # nmcli dev wifi rescan triggers an actual RF scan rather than
        # returning cached results.  We use sudo because the kiosk user
        # may lack direct device-control privileges.
        subprocess.run(
            ["sudo", "nmcli", "dev", "wifi", "rescan"],
            capture_output=True, text=True, timeout=10
        )

        # Step 2: Wait for the scan to complete.  The radio needs a few
        # seconds to discover nearby access points (especially newly
        # enabled hotspots).
        import asyncio
        await asyncio.sleep(3)

        # Step 3: Retrieve the (now-fresh) scan results.
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
            capture_output=True, text=True, timeout=10
        )

        networks = []
        seen = set()
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            # Split from right: SSID may contain colons, SIGNAL and SECURITY don't
            parts = line.rsplit(":", 2)
            if len(parts) < 3:
                continue
            ssid = parts[0].replace("\\:", ":").strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            signal = int(parts[1]) if parts[1].strip().isdigit() else 0
            security = parts[2].strip()
            networks.append({"ssid": ssid, "signal": signal, "security": security})

        networks.sort(key=lambda x: x["signal"], reverse=True)
        return {"networks": networks}

    except FileNotFoundError:
        return {"networks": [], "message": "nmcli not available on this system."}
    except subprocess.TimeoutExpired:
        return {"networks": [], "message": "WiFi scan timed out."}
    except Exception as e:
        logger.error(f"[KIOSK] WiFi scan failed: {e}")
        return {"networks": [], "message": f"Scan failed: {e}"}


@app.post("/admin/kiosk/wifi/connect")
async def kiosk_wifi_connect(data: WifiConnectRequest):
    """
    Connect to a WiFi network using nmcli connection add + up.

    Uses explicit 'connection add' with wifi-sec.key-mgmt and wifi-sec.psk
    instead of 'dev wifi connect', which fails on some NetworkManager versions
    with "802-11-wireless-security.key-mgmt: property is missing".

    Requires admin password. Only works on Linux (RPi).
    """
    import platform
    import subprocess

    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    if platform.system() != "Linux":
        return {"status": "skipped", "message": "WiFi connect only available on Raspberry Pi (Linux)."}

    # Validate SSID (IEEE 802.11: max 32 bytes)
    if not data.ssid or len(data.ssid) > 32:
        raise HTTPException(status_code=400, detail="Invalid SSID")

    try:
        # All nmcli connection commands use sudo because NetworkManager requires
        # elevated privileges for creating/deleting/activating system-wide connections.
        # A targeted sudoers rule in /etc/sudoers.d/coco-wifi restricts this
        # to only nmcli connection subcommands (see install_kiosk.sh).
        # All arguments are list items — no shell injection possible.

        # Step 1: Remove any existing connection profile for this SSID
        # (ignore errors — profile may not exist)
        subprocess.run(
            ["sudo", "nmcli", "connection", "delete", data.ssid],
            capture_output=True, text=True, timeout=10
        )

        # Step 2: Create a new connection profile with explicit security settings.
        if data.wifi_password:
            # WPA/WPA2 secured network: explicitly set key-mgmt and psk
            add_cmd = [
                "sudo", "nmcli", "connection", "add",
                "type", "wifi",
                "con-name", data.ssid,
                "ssid", data.ssid,
                "wifi-sec.key-mgmt", "wpa-psk",
                "wifi-sec.psk", data.wifi_password
            ]
        else:
            # Open network: no security settings
            add_cmd = [
                "sudo", "nmcli", "connection", "add",
                "type", "wifi",
                "con-name", data.ssid,
                "ssid", data.ssid
            ]

        add_result = subprocess.run(add_cmd, capture_output=True, text=True, timeout=15)
        if add_result.returncode != 0:
            error_msg = add_result.stderr.strip() or "Failed to create connection profile"
            logger.warning(f"[KIOSK] WiFi profile creation failed: {error_msg}")
            return {"status": "failed", "message": error_msg}

        # Step 3: Activate the connection
        up_result = subprocess.run(
            ["sudo", "nmcli", "connection", "up", data.ssid],
            capture_output=True, text=True, timeout=30
        )

        if up_result.returncode == 0:
            logger.info(f"[KIOSK] WiFi connected to: {data.ssid}")
            return {"status": "success", "message": f"Connected to {data.ssid}"}
        else:
            # Clean up the profile if activation failed
            subprocess.run(
                ["sudo", "nmcli", "connection", "delete", data.ssid],
                capture_output=True, text=True, timeout=10
            )
            error_msg = up_result.stderr.strip() or "Failed to connect"
            logger.warning(f"[KIOSK] WiFi connect failed: {error_msg}")
            return {"status": "failed", "message": error_msg}

    except subprocess.TimeoutExpired:
        return {"status": "failed", "message": "Connection attempt timed out."}
    except Exception as e:
        logger.error(f"[KIOSK] WiFi connect error: {e}")
        raise HTTPException(status_code=500, detail=f"WiFi connect failed: {e}")


# ==============================================================================
# MOUNT STATIC FILES
# ==============================================================================

# Serve static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

# Serve images from project root images directory (for logo, etc.)
app.mount("/images", StaticFiles(directory=PROJECT_ROOT / "static" / "images"), name="images")

# Serve advertisement images (Phase 48)
_ADS_DIR = PROJECT_ROOT / "data" / "advertisements"
_ADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/advertisements", StaticFiles(directory=_ADS_DIR), name="advertisements")


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

    # Run conversation log retention cleanup (keeps current + previous calendar month)
    try:
        query_logger.run_cleanup()
    except Exception as e:
        logger.warning(f"[Startup] Log retention cleanup failed (non-fatal): {e}")

    # Phase 32: Initialize voice services
    try:
        from WEB_APP.modules.voice.config import VOICE_CONFIG, is_voice_enabled, log_config_summary
        from WEB_APP.modules.voice import STTService, TTSService, VoiceOrchestrator
        from WEB_APP.modules.voice.provider_registry import ProviderRegistry

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
                    "metadata_visible": response.metadata_visible,
                    "fusion_mode": response.fusion_mode,
                    "fusion_label_visible": response.fusion_label_visible,
                    "timestamp": response.timestamp,
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

    # Phase 56: Initialize trivia content (lazy - only generates if month changed)
    try:
        if trivia_manager.initialize_trivia_content():
            status = trivia_manager.get_content_status()
            print(f"Trivia content: READY ({status['trivia_count']} trivia, {status['tips_count']} tips, {status['quotes_count']} quotes)")
        else:
            print("Trivia content: GENERATION PENDING (will generate on first access)")
    except Exception as e:
        print(f"Trivia content: INITIALIZATION FAILED ({e})")
        logger.exception("[TRIVIA] Failed to initialize trivia content")

    print(f"API ready at: http://localhost:8000")
    print(f"Kiosk interface at: http://localhost:8000/")
    print(f"Voice status at: http://localhost:8000/voice/status")
    print("="*80)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("Shutting down API...")


