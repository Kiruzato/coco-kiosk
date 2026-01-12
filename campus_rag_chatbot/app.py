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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Header, Depends
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

# ==============================================================================
# CONFIGURATION
# ==============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
if not ADMIN_API_KEY:
    raise ValueError("ADMIN_API_KEY environment variable not set. Please add it to .env file.")

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

# Session settings
SESSION_TIMEOUT_MINUTES = 30
sessions: Dict[str, Dict] = {}  # In-memory session storage

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


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    answer: str
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
        "query_count": 0
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
# ADMIN AUTHENTICATION
# ==============================================================================

async def verify_admin_api_key(x_api_key: str = Header(None)):
    """
    Verify admin API key for protected endpoints.

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
# QUERY HANDLERS - Phase 6
# ==============================================================================

async def handle_campus_query(
    query: str,
    session_id: str,
    memory: ConversationBufferWindowMemory,
    intent_metadata: Dict
) -> ChatResponse:
    """
    Handle campus query using existing RAG pipeline.

    This function implements the original campus RAG logic with:
    - Vector retrieval
    - Confidence scoring
    - Grounding validation
    - Source citation
    """
    # Normalize query for consistent retrieval (case-insensitive matching)
    normalized_query = normalize_text(query)

    # Retrieve with similarity scores using normalized query
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        normalized_query,
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

    # Check if we should answer (grounding validation)
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

    return ChatResponse(
        session_id=session_id,
        answer=answer,
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

    # Add transparency label
    answer_with_label = f"{answer}\n\n[Based on general AI knowledge]"

    # Log general interaction
    query_id = query_logger.log_general_interaction(
        query=query,
        answer=answer,
        session_id=session_id,
        intent=intent_metadata["intent"],
        mode_used="general"
    )

    return ChatResponse(
        session_id=session_id,
        answer=answer_with_label,
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
# DIRECTORY QUERY HANDLER - Phase 8
# ==============================================================================

async def handle_directory_query(
    query: str,
    session_id: str,
    memory: ConversationBufferWindowMemory,
    intent_metadata: Dict
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

    # === PHASE 8: CHECK FOR DIRECTORY QUERY FIRST ===
    # Directory queries get stricter handling (HIGH confidence required)
    if is_directory_query(query):
        intent_metadata = {
            "intent": "directory",
            "reasoning": "Location/directory question detected via pattern matching",
            "raw_classification": "DIRECTORY",
            "query_length": len(query)
        }
        return await handle_directory_query(query, session_id, memory, intent_metadata)

    # === PHASE 6: INTENT CLASSIFICATION ===
    intent, intent_metadata = classify_intent(query=query, llm=llm)

    # === PHASE 6: ROUTE BASED ON INTENT ===
    if intent == QueryIntent.GENERAL:
        return await handle_general_query(query, session_id, memory, intent_metadata)
    elif intent == QueryIntent.AMBIGUOUS:
        return await handle_ambiguous_query(query, session_id, intent_metadata)
    else:  # QueryIntent.CAMPUS
        return await handle_campus_query(query, session_id, memory, intent_metadata)


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

@app.post("/admin/upload", dependencies=[Depends(verify_admin_api_key)])
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


@app.get("/admin/documents", dependencies=[Depends(verify_admin_api_key)])
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


@app.delete("/admin/documents/{document_id}", dependencies=[Depends(verify_admin_api_key)])
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
