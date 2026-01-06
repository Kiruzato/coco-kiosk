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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# ==============================================================================
# CONFIGURATION
# ==============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

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
    Handle a chat message.

    Args:
        request: Chat request with message and optional session_id

    Returns:
        Chat response with answer, sources, and confidence
    """
    # Get or create session
    session_id, session = get_or_create_session(request.session_id)
    memory = session["memory"]
    session["query_count"] += 1

    query = request.message.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Retrieve with similarity scores
    retrieval_results = doc_manager.vector_store.similarity_search_with_relevance_scores(
        query,
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
        system_template = """You are a campus information assistant for Springfield University. Provide accurate information ONLY from the verified campus documents.

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

    # Log the interaction
    query_id = query_logger.log_full_interaction(
        query=query,
        retrieved_chunks=retrieved_docs,
        similarity_scores=similarity_scores,
        answer=answer,
        confidence_level=confidence_level.value,
        confidence_metrics=confidence_metrics,
        session_id=session_id
    )

    # Store query_id in session for feedback
    if "last_query_id" not in session:
        session["last_query_ids"] = []
    session["last_query_ids"].append(query_id)

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=sources,
        confidence_level=confidence_level.value,
        confidence_score=round(confidence_metrics["confidence_score"], 1),
        rejected=rejected,
        timestamp=datetime.now().isoformat()
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
