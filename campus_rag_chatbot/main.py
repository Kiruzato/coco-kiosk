"""
Campus RAG Chatbot - Phase 4
==============================
This script demonstrates the RAG system with confidence scoring and evaluation.

Phase 4 Features:
1. Confidence scoring (High/Medium/Low)
2. Retrieval quality metrics logging
3. Answer grounding validation
4. Structured JSON logging
5. Offline evaluation utilities

Previous Features:
- Document management system (PDF, DOCX, TXT)
- Multi-document retrieval
- Conversation memory
- Hallucination guardrails
"""

import os
from pathlib import Path
from typing import Dict, Tuple, List
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory

# Import Phase 3 modules
from document_manager import DocumentManager

# Import Phase 4 modules
from confidence_scorer import (
    compute_confidence_score,
    ConfidenceLevel,
    should_answer_confidently,
    format_confidence_display,
    analyze_retrieval_quality
)
from query_logger import QueryLogger


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it before running.")

# Paths
PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"
LOG_DIR = PROJECT_ROOT / "logs"

# Conversation memory settings
MEMORY_WINDOW_SIZE = 5

# Retrieval settings
RETRIEVAL_TOP_K = 4
RELEVANCE_SCORE_THRESHOLD = 0.5

# Phase 4: Confidence settings
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.MEDIUM  # Don't answer LOW confidence queries


# ==============================================================================
# QUESTION ASKING WITH CONFIDENCE SCORING - Phase 4
# ==============================================================================

def ask_question_with_confidence(
    document_manager: DocumentManager,
    query: str,
    llm: ChatOpenAI,
    memory: ConversationBufferWindowMemory,
    logger: QueryLogger,
    turn_number: int = 1,
    session_id: str = "default"
) -> Dict:
    """
    Ask a question with confidence scoring and grounding validation.

    Phase 4 enhancements:
    - Compute confidence scores from retrieval
    - Validate answer grounding
    - Log structured data (query, retrieval, response)
    - Refuse to answer if confidence is too low

    Args:
        document_manager: DocumentManager with loaded vector store
        query: User's question
        llm: Language model
        memory: Conversation memory
        logger: QueryLogger for structured logging
        turn_number: Conversation turn number
        session_id: Session identifier

    Returns:
        Dictionary with answer, confidence, and metadata
    """
    print(f"\n{'='*80}")
    print(f"Turn {turn_number}")
    print(f"{'='*80}")
    print(f"User: {query}")
    print("-" * 80)

    # Phase 4: Retrieve with similarity scores
    retrieval_results = document_manager.vector_store.similarity_search_with_relevance_scores(
        query,
        k=RETRIEVAL_TOP_K,
        score_threshold=RELEVANCE_SCORE_THRESHOLD
    )

    # Separate docs and scores
    retrieved_docs = [doc for doc, score in retrieval_results]
    similarity_scores = [score for doc, score in retrieval_results]

    # Phase 4: Compute confidence score
    confidence_level, confidence_metrics = compute_confidence_score(
        similarity_scores=similarity_scores,
        min_chunks_retrieved=1
    )

    # Phase 4: Analyze retrieval quality
    retrieval_analysis = analyze_retrieval_quality(
        query=query,
        retrieved_chunks=retrieved_docs,
        similarity_scores=similarity_scores
    )

    # Phase 4: Check if we should answer (grounding validation)
    if not should_answer_confidently(confidence_level, MIN_CONFIDENCE_TO_ANSWER):
        # LOW confidence - refuse to answer
        answer = "I don't have verified campus information to answer that question confidently. The retrieved information has low relevance to your query."

        print(f"Assistant: {answer}\n")
        print(format_confidence_display(confidence_level, confidence_metrics, show_details=True))
        print("\n⚠ Answer rejected due to low confidence (grounding validation failed)")
        print("-" * 80)

        # Phase 4: Log the interaction
        logger.log_full_interaction(
            query=query,
            retrieved_chunks=retrieved_docs,
            similarity_scores=similarity_scores,
            answer=answer,
            confidence_level=confidence_level.value,
            confidence_metrics=confidence_metrics,
            session_id=session_id,
            retrieval_params={
                "top_k": RETRIEVAL_TOP_K,
                "score_threshold": RELEVANCE_SCORE_THRESHOLD
            }
        )

        return {
            "query": query,
            "answer": answer,
            "confidence_level": confidence_level,
            "confidence_metrics": confidence_metrics,
            "sources": [],
            "rejected": True
        }

    # HIGH or MEDIUM confidence - generate answer
    # Create temporary QA chain for this query
    system_template = """You are a campus information assistant for Columban College, Inc. Your role is to provide accurate information ONLY from the verified campus documents.

CRITICAL RULES:
1. ONLY answer questions using the provided context below
2. If the context does not contain the answer, you MUST respond: "I don't have verified campus information to answer that question."
3. NEVER guess, infer, or make up information
4. ALWAYS cite your sources by mentioning the document name and section
5. If information comes from multiple documents, clearly distinguish between sources
6. Use conversation history to understand follow-up questions and pronouns

When answering:
- Start with the specific document and section (e.g., "According to the Library Hours and Services section in campus_info.txt...")
- If multiple documents are relevant, list each source separately
- Be concise but complete

Context from campus documents:
{context}

Remember: If the answer is not in the context above, say you don't have that information. Never make assumptions."""

    human_template = "{question}"

    messages = [
        SystemMessagePromptTemplate.from_template(system_template),
        HumanMessagePromptTemplate.from_template(human_template)
    ]

    qa_prompt = ChatPromptTemplate.from_messages(messages)

    # Create QA chain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=document_manager.vector_store.as_retriever(
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

    # Get answer
    result = qa_chain.invoke({"question": query})
    answer = result['answer']
    source_docs = result.get('source_documents', [])

    # Display answer
    print(f"Assistant: {answer}\n")

    # Phase 4: Display confidence information
    print(format_confidence_display(confidence_level, confidence_metrics, show_details=True))
    print()

    # Display sources with Phase 4 enhanced metadata
    if source_docs:
        print("Sources Used:")

        # Group by document
        sources_by_doc = {}
        for doc in source_docs:
            doc_name = doc.metadata.get('document_name', doc.metadata.get('source', 'Unknown'))
            if doc_name not in sources_by_doc:
                sources_by_doc[doc_name] = []
            sources_by_doc[doc_name].append(doc)

        # Display grouped sources
        for doc_name, docs in sources_by_doc.items():
            print(f"\n  From {doc_name}:")
            for doc in docs:
                section = doc.metadata.get('section', 'Unknown')
                chunk_id = doc.metadata.get('chunk_id', '?')
                print(f"    - Section: {section} (Chunk {chunk_id})")

    # Phase 4: Display retrieval quality analysis
    if retrieval_analysis.get("quality") in ["FAIR", "POOR"]:
        print(f"\n⚠ Retrieval Quality: {retrieval_analysis['quality']}")
        if retrieval_analysis.get("issues"):
            print(f"  Issues: {', '.join(retrieval_analysis['issues'])}")

    print("-" * 80)

    # Phase 4: Log the interaction
    logger.log_full_interaction(
        query=query,
        retrieved_chunks=retrieved_docs,
        similarity_scores=similarity_scores,
        answer=answer,
        confidence_level=confidence_level.value,
        confidence_metrics=confidence_metrics,
        session_id=session_id,
        retrieval_params={
            "top_k": RETRIEVAL_TOP_K,
            "score_threshold": RELEVANCE_SCORE_THRESHOLD
        }
    )

    return {
        "query": query,
        "answer": answer,
        "confidence_level": confidence_level,
        "confidence_metrics": confidence_metrics,
        "sources": list(sources_by_doc.keys()) if source_docs else [],
        "rejected": False
    }


# ==============================================================================
# EXAMPLE CONVERSATION
# ==============================================================================

def run_example_conversation(
    document_manager: DocumentManager,
    llm: ChatOpenAI,
    memory: ConversationBufferWindowMemory,
    logger: QueryLogger
):
    """
    Run example conversation with Phase 4 confidence scoring.

    Args:
        document_manager: DocumentManager instance
        llm: Language model
        memory: Conversation memory
        logger: QueryLogger
    """
    print("\n" + "="*80)
    print("CONVERSATION EXAMPLE WITH CONFIDENCE SCORING (Phase 4)")
    print("="*80)

    # Test queries with varying confidence levels
    conversation = [
        "What are the library hours?",  # Should be HIGH confidence
        "How much does parking cost?",  # Should be HIGH/MEDIUM confidence
        "What is the weather like today?",  # Should be LOW confidence (rejected)
        "What IT services are available?",  # Should be HIGH/MEDIUM confidence
        "Tell me about student employment opportunities",  # Should be MEDIUM confidence
    ]

    results = []
    for i, question in enumerate(conversation, 1):
        result = ask_question_with_confidence(
            document_manager=document_manager,
            query=question,
            llm=llm,
            memory=memory,
            logger=logger,
            turn_number=i,
            session_id="demo_session"
        )
        results.append(result)
        print()

    # Summary
    print("\n" + "="*80)
    print("CONVERSATION SUMMARY")
    print("="*80)
    high_count = sum(1 for r in results if r["confidence_level"] == ConfidenceLevel.HIGH)
    medium_count = sum(1 for r in results if r["confidence_level"] == ConfidenceLevel.MEDIUM)
    low_count = sum(1 for r in results if r["confidence_level"] == ConfidenceLevel.LOW)
    rejected_count = sum(1 for r in results if r.get("rejected", False))

    print(f"Total Questions: {len(results)}")
    print(f"High Confidence: {high_count}")
    print(f"Medium Confidence: {medium_count}")
    print(f"Low Confidence: {low_count}")
    print(f"Rejected (Low Confidence): {rejected_count}")
    print("="*80)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """
    Main function for Phase 4 RAG system.
    """
    print("=" * 80)
    print("Campus Information RAG Chatbot - Phase 4")
    print("Features: Confidence Scoring, Grounding Validation, Structured Logging")
    print("=" * 80)
    print()

    # Initialize document manager
    print("Initializing document manager...")
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )

    # Load vector store
    vector_store = doc_manager.load_vector_store()

    if vector_store is None:
        print("\n" + "="*80)
        print("NO DOCUMENTS FOUND")
        print("="*80)
        print("\nPlease ingest documents first:")
        print("  python admin.py ingest data/")
        print("="*80)
        return

    # Display document statistics
    documents = doc_manager.list_documents()
    print(f"Loaded vector store with {len(documents)} document(s)")
    print()

    # Initialize LLM
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0,
        openai_api_key=OPENAI_API_KEY
    )

    # Initialize conversation memory
    memory = ConversationBufferWindowMemory(
        k=MEMORY_WINDOW_SIZE,
        memory_key="chat_history",
        return_messages=True,
        output_key="answer"
    )

    # Phase 4: Initialize query logger
    logger = QueryLogger(log_dir=LOG_DIR)
    print(f"Query logger initialized. Logs saved to: {LOG_DIR}")
    print()

    print("="*80)
    print("PHASE 4 CONFIGURATION")
    print("="*80)
    print(f"Retrieval: top_k={RETRIEVAL_TOP_K}, threshold={RELEVANCE_SCORE_THRESHOLD}")
    print(f"Minimum Confidence: {MIN_CONFIDENCE_TO_ANSWER.value}")
    print(f"Conversation Memory: {MEMORY_WINDOW_SIZE} turns")
    print("="*80)

    # Run example conversation
    run_example_conversation(doc_manager, llm, memory, logger)

    print("\n" + "="*80)
    print("Phase 4 Demo Complete!")
    print("="*80)
    print("\nKey Phase 4 Features Demonstrated:")
    print("  ✓ Confidence scoring (High/Medium/Low)")
    print("  ✓ Grounding validation (reject low confidence)")
    print("  ✓ Retrieval quality metrics")
    print("  ✓ Structured JSON logging")
    print()
    print("Log Files:")
    print(f"  Queries:    {LOG_DIR / 'queries.jsonl'}")
    print(f"  Retrievals: {LOG_DIR / 'retrievals.jsonl'}")
    print(f"  Responses:  {LOG_DIR / 'responses.jsonl'}")
    print()
    print("Evaluation Tools:")
    print("  python -c \"from query_logger import print_log_summary; print_log_summary()\"")
    print("  python evaluate_demo.py  # Run evaluation examples")
    print("="*80)


if __name__ == "__main__":
    main()
