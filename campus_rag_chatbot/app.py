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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Header, Depends, Request, Response

# Phase 14.1: Set up logging for clarification flow debugging
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
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
from entity_resolver import extract_subject, resolve_entity, format_entity_response  # Phase 9: Entity resolution
from event_tracker import EventTracker, EventType  # Phase 16: Observability
from retrieval_validator import (  # Phase 17A: Hybrid retrieval & grounding
    extract_query_terms,
    compute_keyword_scores,
    combine_hybrid_scores,
    validate_grounding,
    get_grounding_refusal_message
)
from response_formatter import format_structured_answer, build_structured_answer  # Phase 17B/17B.1

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

PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"
LOG_DIR = PROJECT_ROOT / "logs"
FEEDBACK_LOG_PATH = LOG_DIR / "feedback.jsonl"

# API settings
RETRIEVAL_TOP_K = 4
RELEVANCE_SCORE_THRESHOLD = 0.5
MEMORY_WINDOW_SIZE = 5
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.MEDIUM
MIN_CONFIDENCE_DIRECTORY = ConfidenceLevel.HIGH  # Phase 8: Stricter for location queries

# Phase 17A: Hybrid retrieval settings
HYBRID_VECTOR_WEIGHT = 0.7       # Weight for vector similarity score
HYBRID_KEYWORD_WEIGHT = 0.3      # Weight for BM25 keyword score
MIN_GROUNDING_TERMS = 1          # Minimum query terms required in chunks

# Session settings (chat sessions)
SESSION_TIMEOUT_MINUTES = 30
sessions: Dict[str, Dict] = {}  # In-memory session storage

# Admin session settings
ADMIN_SESSION_DURATION = timedelta(hours=8)
admin_sessions: Dict[str, datetime] = {}  # {session_token: expiry_datetime}

# Phase 17A.1: Developer RAG-only mode (in-memory, not persisted)
rag_only_mode: bool = False

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

# Initialize LLM
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0,
    openai_api_key=OPENAI_API_KEY
)

# Initialize query logger
query_logger = QueryLogger(log_dir=LOG_DIR)

# Initialize event tracker for observability (Phase 16)
event_tracker = EventTracker(log_dir=LOG_DIR)

# Initialize entity registry for directory queries (Phase 9)
ENTITY_REGISTRY_PATH = PROJECT_ROOT / "data" / "directory_entities.json"
entity_registry = EntityRegistry(str(ENTITY_REGISTRY_PATH))

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
    key_details: List[str] = []
    notes: Optional[str] = None
    disclaimer: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    answer: str  # Keep for backward compatibility
    structured_answer: Optional[StructuredAnswer] = None  # Phase 17B.1: Structured format
    sources: List[Source]
    confidence_level: str
    confidence_score: float
    rejected: bool
    timestamp: str
    mode: str  # "campus" | "general" | "clarification"


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
# ENTITY MANAGEMENT MODELS - Phase 10
# ==============================================================================

class EntityCreate(BaseModel):
    """Request model for creating a new directory entity."""
    entity_id: str
    canonical_name: str
    aliases: List[str]
    building: str
    floor: str
    room: Optional[str] = None
    campus: str = "Main Campus"
    department: Optional[str] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None


class EntityUpdate(BaseModel):
    """Request model for updating an existing directory entity."""
    canonical_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    room: Optional[str] = None
    campus: Optional[str] = None
    department: Optional[str] = None
    landmarks: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


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

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[],
        confidence_level="Medium",
        confidence_score=50.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification"
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

    # Retrieve with similarity scores
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        normalized_query,
        k=RETRIEVAL_TOP_K,
        score_threshold=RELEVANCE_SCORE_THRESHOLD
    )

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
    hybrid_results, hybrid_details = combine_hybrid_scores(
        retrieval_results,
        keyword_scores,
        vector_weight=HYBRID_VECTOR_WEIGHT,
        keyword_weight=HYBRID_KEYWORD_WEIGHT
    )

    # Validate grounding: ensure query terms appear in retrieved chunks
    grounding_result = validate_grounding(
        query_terms,
        hybrid_results,
        min_term_matches=MIN_GROUNDING_TERMS
    )

    # Compute confidence
    similarity_scores = [float(score) for doc, score in hybrid_results]
    confidence_level, confidence_metrics = compute_confidence_score(
        similarity_scores=similarity_scores,
        min_chunks_retrieved=1
    )

    return {
        "is_grounded": grounding_result.is_grounded if query_terms else True,
        "retrieval_results": hybrid_results,
        "grounding_result": grounding_result,
        "confidence_level": confidence_level,
        "confidence_score": confidence_metrics.get("confidence_score", 0.0),
        "query_terms": query_terms
    }


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
    # Phase 17A.2: Use pre-computed results if provided
    if precomputed_retrieval:
        retrieval_results = precomputed_retrieval["retrieval_results"]
        query_terms = precomputed_retrieval["query_terms"]
        grounding_result = precomputed_retrieval["grounding_result"]
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
        hybrid_results, hybrid_details = combine_hybrid_scores(
            retrieval_results,
            keyword_scores,
            vector_weight=HYBRID_VECTOR_WEIGHT,
            keyword_weight=HYBRID_KEYWORD_WEIGHT
        )

        # Validate grounding: ensure query terms appear in retrieved chunks
        grounding_result = validate_grounding(
            query_terms,
            hybrid_results,
            min_term_matches=MIN_GROUNDING_TERMS
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

            return ChatResponse(
                session_id=session_id,
                answer=get_grounding_refusal_message(grounding_result.topic),
                sources=[],
                confidence_level="LOW",
                confidence_score=0.0,
                rejected=True,
                timestamp=datetime.now().isoformat(),
                mode="campus"
            )

        # Use hybrid-ranked results for downstream processing
        retrieval_results = hybrid_results
        # =========================================================================

    retrieved_docs = [doc for doc, score in retrieval_results]
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
        # Generate answer
        system_template = """You are a campus information assistant for Columban College, Inc. Provide accurate information ONLY from the verified campus documents.

CRITICAL RULES:
1. ONLY answer using the provided context
2. If context doesn't contain the answer, say: "I don't have verified campus information to answer that question."
3. NEVER guess or make up information
4. ALWAYS cite sources by mentioning document name and section
5. Use conversation history to understand follow-up questions

Context from campus documents:
{context}"""

        human_template = "{question}"

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ]

        qa_prompt = ChatPromptTemplate.from_messages(messages)

        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=doc_manager.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "k": RETRIEVAL_TOP_K,
                    "score_threshold": RELEVANCE_SCORE_THRESHOLD
                }
            ),
            memory=memory,
            return_source_documents=True,
            combine_docs_chain_kwargs={"prompt": qa_prompt},
            verbose=False
        )

        result = qa_chain.invoke({"question": query})
        answer = result['answer']
        source_docs = result.get('source_documents', [])
        rejected = False

        # Extract sources
        sources = []
        seen = set()
        for doc in source_docs:
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
            # Keep plain answer as direct_answer for backward compatibility
            answer = structured_data.get("direct_answer", answer)

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        structured_answer=structured_answer,
        sources=sources,
        confidence_level=confidence_level.value,
        confidence_score=round(confidence_metrics["confidence_score"], 1),
        rejected=rejected,
        timestamp=datetime.now().isoformat(),
        mode="campus"
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
    response = llm.invoke(general_prompt)
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

    return ChatResponse(
        session_id=session_id,
        answer=answer_with_label,
        structured_answer=structured_answer,
        sources=[],
        confidence_level="N/A",
        confidence_score=0.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="general"
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

    return ChatResponse(
        session_id=session_id,
        answer=clarification,
        sources=[],
        confidence_level="N/A",
        confidence_score=0.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification"
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

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[],
        confidence_level="Medium",
        confidence_score=50.0,
        rejected=False,
        timestamp=datetime.now().isoformat(),
        mode="clarification"
    )


def handle_disambiguation_selection(
    selection: str,
    session: Dict,
    session_id: str
) -> Optional[ChatResponse]:
    """
    Handle user's selection from disambiguation options (Phase 14).

    Returns ChatResponse if selection is valid, None otherwise.
    """
    context = session["conversation_context"]
    candidates = context.get("disambiguation_candidates", [])

    if not candidates:
        return None

    # Phase 14.1: Log selection attempt
    logger.info(f"[CLARIFICATION] Selection attempt: '{selection}' from candidates: {candidates}")

    selected_entity = None
    selection_lower = selection.lower().strip()

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
        for key, idx in num_map.items():
            if key in selection_lower.split():  # Match whole words only
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
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=[],
            confidence_level="High",
            confidence_score=98.0,
            rejected=False,
            timestamp=datetime.now().isoformat(),
            mode="directory"
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

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=[],  # No RAG sources - entity-based answer
            confidence_level="High",
            confidence_score=98.0,
            rejected=False,
            timestamp=datetime.now().isoformat(),
            mode="directory"
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
        # Generate answer with strict directory-focused prompt
        system_template = """You are a campus directory assistant for Columban College, Inc. helping visitors find locations on campus.

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
{context}"""

        human_template = "{question}"

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(human_template)
        ]

        qa_prompt = ChatPromptTemplate.from_messages(messages)

        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=doc_manager.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "k": RETRIEVAL_TOP_K,
                    "score_threshold": RELEVANCE_SCORE_THRESHOLD
                }
            ),
            memory=memory,
            return_source_documents=True,
            combine_docs_chain_kwargs={"prompt": qa_prompt},
            verbose=False
        )

        result = qa_chain.invoke({"question": query})
        answer = result['answer']
        source_docs = result.get('source_documents', [])
        rejected = False

        # Extract sources
        sources = []
        seen = set()
        for doc in source_docs:
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
            candidates = context.get("disambiguation_candidates", [])
            options = []
            for i, eid in enumerate(candidates[:4], 1):
                entity = entity_registry.get_by_id(eid)
                if entity:
                    options.append(f"{i}. {entity.canonical_name}")

            return ChatResponse(
                session_id=session_id,
                answer=f"I didn't quite catch that. Please reply with just a number:\n\n" + "\n".join(options),
                sources=[],
                confidence_level="Medium",
                confidence_score=50.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="clarification"
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
            sources = context.get("doc_clarification_sources", [])
            options = []
            for i, source in enumerate(sources[:4], 1):
                display_name = os.path.basename(source).replace('.txt', '').replace('_', ' ').title()
                options.append(f"{i}. {display_name}")

            return ChatResponse(
                session_id=session_id,
                answer=f"Please select a document or say 'summary' for a general answer:\n\n" + "\n".join(options),
                sources=[],
                confidence_level="Medium",
                confidence_score=50.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="clarification"
            )

    # === PHASE 13: CHECK FOR FOLLOW-UP QUERY WITH CONTEXT ===
    if context.get("last_entity_id") and is_followup_query(query):
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

            return ChatResponse(
                session_id=session_id,
                answer=answer,
                sources=[],
                confidence_level="High",
                confidence_score=98.0,
                rejected=False,
                timestamp=datetime.now().isoformat(),
                mode="directory"
            )

    # === PHASE 8: CHECK FOR DIRECTORY QUERY FIRST ===
    # Directory queries get stricter handling (HIGH confidence required)
    if is_directory_query(query):
        intent_metadata = {
            "intent": "directory",
            "reasoning": "Location/directory question detected via pattern matching",
            "raw_classification": "DIRECTORY",
            "query_length": len(query)
        }
        return await handle_directory_query(query, session_id, memory, intent_metadata, session)

    # === PHASE 17A.2: RETRIEVAL-FIRST ROUTING ===
    # Attempt document retrieval FIRST before deciding whether to use general AI
    retrieval_result = attempt_document_retrieval(query)

    # Log retrieval attempt
    event_tracker.track(
        EventType.ROUTING_DOCUMENT_ATTEMPTED,
        session_id=session_id,
        grounded=retrieval_result["is_grounded"],
        confidence=retrieval_result["confidence_score"],
        rag_only_mode=rag_only_mode
    )

    # Check if retrieval succeeded (grounded AND sufficient confidence)
    retrieval_succeeded = (
        retrieval_result["is_grounded"] and
        should_answer_confidently(retrieval_result["confidence_level"], MIN_CONFIDENCE_TO_ANSWER)
    )

    if retrieval_succeeded:
        # Retrieval succeeded - use RAG answer
        event_tracker.track(EventType.ROUTING_DOCUMENT_SUCCESS, session_id=session_id)
        intent_metadata = {
            "intent": "campus",
            "reasoning": "Retrieval-first routing: document retrieval succeeded",
            "raw_classification": "CAMPUS",
            "query_length": len(query)
        }
        return await handle_campus_query(
            query, session_id, memory, intent_metadata, session,
            precomputed_retrieval=retrieval_result
        )
    else:
        # Retrieval failed - decide fallback
        if rag_only_mode:
            # RAG-only mode: refuse instead of falling back to general AI
            grounding_result = retrieval_result.get("grounding_result")
            topic = grounding_result.topic if grounding_result else "your question"

            event_tracker.track(
                EventType.ANSWER_REFUSED,
                session_id=session_id,
                reason="retrieval_failed_rag_only",
                confidence=retrieval_result["confidence_score"]
            )

            return ChatResponse(
                session_id=session_id,
                answer=f"[RAG-Only Mode] I couldn't find relevant campus information about {topic}. Please try rephrasing your question or ask about a different topic.",
                sources=[],
                confidence_level="LOW",
                confidence_score=0.0,
                rejected=True,
                timestamp=datetime.now().isoformat(),
                mode="rag_only"
            )
        else:
            # Normal mode: fall back to general AI
            event_tracker.track(
                EventType.ROUTING_GENERAL_FALLBACK,
                session_id=session_id,
                confidence=retrieval_result["confidence_score"],
                grounded=retrieval_result["is_grounded"]
            )
            intent_metadata = {
                "intent": "general",
                "reasoning": "Retrieval-first routing: document retrieval failed, falling back to general AI",
                "raw_classification": "GENERAL_FALLBACK",
                "query_length": len(query)
            }
            return await handle_general_query(query, session_id, memory, intent_metadata)


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
# ADMIN ENTITY ENDPOINTS - Phase 10
# ==============================================================================

@app.get("/admin/entities", dependencies=[Depends(verify_admin_session)])
async def list_entities():
    """
    List all directory entities.

    Returns:
        List of entities with metadata including status
    """
    from dataclasses import asdict

    entities = []
    for entity in entity_registry.get_all_entities():
        entity_dict = asdict(entity)
        entities.append(entity_dict)

    # Sort by entity_id for consistent ordering
    entities.sort(key=lambda x: x['entity_id'])

    return {
        "entities": entities,
        "total": len(entities),
        "active": len([e for e in entities if e.get('status', 'active') == 'active'])
    }


# ==============================================================================
# ENTITY CSV IMPORT/EXPORT - Phase 10 Extension
# Note: These routes MUST be defined before the {entity_id} route
# ==============================================================================

@app.get("/admin/entities/export", dependencies=[Depends(verify_admin_session)])
async def export_entities():
    """
    Export all directory entities to CSV format.

    Returns:
        CSV file download with all entities
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    headers = [
        'entity_id', 'canonical_name', 'aliases', 'building', 'floor',
        'room', 'campus', 'department', 'landmarks', 'description', 'status', 'last_updated'
    ]
    writer.writerow(headers)

    # Write entity rows
    for entity in sorted(entity_registry.get_all_entities(), key=lambda e: e.entity_id):
        # Join aliases with semicolon
        aliases_str = ';'.join(entity.aliases) if entity.aliases else ''

        row = [
            entity.entity_id,
            entity.canonical_name,
            aliases_str,
            entity.building,
            entity.floor,
            entity.room or '',
            entity.campus,
            entity.department or '',
            entity.landmarks or '',
            entity.description or '',
            entity.status,
            entity.last_updated or ''
        ]
        writer.writerow(row)

    # Prepare response
    output.seek(0)
    filename = f"directory_entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/admin/entities/import", dependencies=[Depends(verify_admin_session)])
async def import_entities(file: UploadFile = File(...)):
    """
    Import directory entities from CSV file.

    CSV must have columns: entity_id, canonical_name, aliases, building, floor,
    room, landmarks, description, status

    Import rules:
    - If entity_id exists → update entity
    - If entity_id is new → create entity
    - If status is 'inactive' → soft delete
    - Changes applied atomically (all-or-nothing)

    Args:
        file: CSV file upload

    Returns:
        Import result with stats
    """
    import csv
    import io

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read file content
        content = await file.read()
        text = content.decode('utf-8-sig')  # Handle BOM from Excel

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))
        entities_data = list(reader)

        if not entities_data:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Perform bulk import
        success, message, stats = entity_registry.bulk_import(entities_data)

        if not success:
            return {
                "status": "error",
                "message": message,
                "stats": stats
            }

        return {
            "status": "success",
            "message": message,
            "stats": stats
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")


@app.get("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
async def get_entity(entity_id: str):
    """
    Get a single directory entity by ID.

    Args:
        entity_id: Entity identifier

    Returns:
        Entity data

    Raises:
        404: Entity not found
    """
    from dataclasses import asdict

    entity = entity_registry.get_by_id(entity_id.upper())
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return {
        "entity": asdict(entity)
    }


@app.post("/admin/entities", dependencies=[Depends(verify_admin_session)])
async def create_entity(entity_data: EntityCreate):
    """
    Create a new directory entity.

    Args:
        entity_data: Entity creation data

    Returns:
        Success message with created entity

    Raises:
        400: Validation error or duplicate ID
    """
    from dataclasses import asdict

    success, message = entity_registry.add_entity(
        entity_id=entity_data.entity_id,
        canonical_name=entity_data.canonical_name,
        aliases=entity_data.aliases,
        building=entity_data.building,
        floor=entity_data.floor,
        room=entity_data.room,
        campus=entity_data.campus,
        department=entity_data.department,
        landmarks=entity_data.landmarks,
        description=entity_data.description
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Get the created entity to return
    created_entity = entity_registry.get_by_id(entity_data.entity_id.upper())

    return {
        "status": "success",
        "message": message,
        "entity": asdict(created_entity) if created_entity else None
    }


@app.put("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
async def update_entity(entity_id: str, entity_data: EntityUpdate):
    """
    Update an existing directory entity.

    Args:
        entity_id: Entity identifier
        entity_data: Fields to update (only non-None values)

    Returns:
        Success message with updated entity

    Raises:
        400: Validation error
        404: Entity not found
    """
    from dataclasses import asdict

    # Check if entity exists
    existing = entity_registry.get_by_id(entity_id.upper())
    if not existing:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    # Build update kwargs from non-None fields
    update_kwargs = {}
    if entity_data.canonical_name is not None:
        update_kwargs['canonical_name'] = entity_data.canonical_name
    if entity_data.aliases is not None:
        update_kwargs['aliases'] = entity_data.aliases
    if entity_data.building is not None:
        update_kwargs['building'] = entity_data.building
    if entity_data.floor is not None:
        update_kwargs['floor'] = entity_data.floor
    if entity_data.room is not None:
        update_kwargs['room'] = entity_data.room
    if entity_data.campus is not None:
        update_kwargs['campus'] = entity_data.campus
    if entity_data.department is not None:
        update_kwargs['department'] = entity_data.department
    if entity_data.landmarks is not None:
        update_kwargs['landmarks'] = entity_data.landmarks
    if entity_data.description is not None:
        update_kwargs['description'] = entity_data.description
    if entity_data.status is not None:
        update_kwargs['status'] = entity_data.status

    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    success, message = entity_registry.update_entity(entity_id, **update_kwargs)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Get the updated entity to return
    updated_entity = entity_registry.get_by_id(entity_id.upper())

    return {
        "status": "success",
        "message": message,
        "entity": asdict(updated_entity) if updated_entity else None
    }


@app.delete("/admin/entities/{entity_id}", dependencies=[Depends(verify_admin_session)])
async def delete_entity(entity_id: str, hard: bool = False):
    """
    Delete a directory entity (soft or hard delete).

    Soft delete (default): Sets status to 'inactive', entity remains in storage.
    Hard delete: Permanently removes entity from storage (use with caution).

    Args:
        entity_id: Entity identifier
        hard: If True, permanently remove entity

    Returns:
        Success message

    Raises:
        404: Entity not found
    """
    # Check if entity exists
    existing = entity_registry.get_by_id(entity_id.upper())
    if not existing:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    success, message = entity_registry.delete_entity(entity_id, hard=hard)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "status": "success",
        "message": message,
        "entity_id": entity_id.upper(),
        "delete_type": "hard" if hard else "soft"
    }


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


# ==============================================================================
# STARTUP/SHUTDOWN
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("="*80)
    print("Campus Information Kiosk API - Phase 5")
    print("="*80)
    print(f"Documents loaded: {len(doc_manager.list_documents())}")
    print(f"API ready at: http://localhost:8000")
    print(f"Kiosk interface at: http://localhost:8000/")
    print("="*80)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("Shutting down API...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
