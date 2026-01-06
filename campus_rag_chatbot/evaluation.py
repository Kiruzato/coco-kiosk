"""
Offline Evaluation Utilities - Phase 4
=======================================
This module provides utilities for replaying queries and comparing retrieval
parameters offline.

Functions:
- Replay logged queries
- Compare responses with different retrieval parameters (top-k, threshold)
- Analyze retrieval quality across parameter variations
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from tabulate import tabulate

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory

from document_manager import DocumentManager
from query_logger import LogReader
from confidence_scorer import compute_confidence_score, ConfidenceLevel


# ==============================================================================
# CONFIGURATION
# ==============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"


# ==============================================================================
# QUERY REPLAY
# ==============================================================================

def replay_query(
    query: str,
    document_manager: DocumentManager,
    top_k: int = 4,
    score_threshold: float = 0.5,
    verbose: bool = True
) -> Dict:
    """
    Replay a single query with specified retrieval parameters.

    Args:
        query: User query string
        document_manager: Initialized DocumentManager with vector store
        top_k: Number of chunks to retrieve
        score_threshold: Minimum similarity threshold
        verbose: Whether to print details

    Returns:
        Dictionary with retrieval results and confidence metrics
    """
    if document_manager.vector_store is None:
        raise ValueError("Vector store not loaded")

    # Perform retrieval with similarity scores
    retriever = document_manager.vector_store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": top_k,
            "score_threshold": score_threshold
        }
    )

    # Get relevant documents with scores
    docs_and_scores = document_manager.vector_store.similarity_search_with_relevance_scores(
        query,
        k=top_k,
        score_threshold=score_threshold
    )

    # Separate docs and scores
    docs = [doc for doc, score in docs_and_scores]
    scores = [score for doc, score in docs_and_scores]

    # Compute confidence
    confidence_level, metrics = compute_confidence_score(scores)

    result = {
        "query": query,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "num_chunks_retrieved": len(docs),
        "similarity_scores": scores,
        "confidence_level": confidence_level.value,
        "confidence_metrics": metrics,
        "retrieved_docs": docs
    }

    if verbose:
        print(f"\nQuery: {query}")
        print(f"Parameters: top_k={top_k}, threshold={score_threshold}")
        print(f"Retrieved: {len(docs)} chunks")
        print(f"Confidence: {confidence_level.value} ({metrics['confidence_score']:.1f}/100)")
        print(f"Avg Similarity: {metrics['avg_similarity']:.3f}")
        print()

    return result


def replay_logged_queries(
    limit: int = 5,
    log_dir: Optional[Path] = None,
    top_k: int = 4,
    score_threshold: float = 0.5
) -> List[Dict]:
    """
    Replay recent logged queries with specified parameters.

    Args:
        limit: Number of queries to replay
        log_dir: Log directory (uses default if None)
        top_k: Number of chunks to retrieve
        score_threshold: Minimum similarity threshold

    Returns:
        List of replay results
    """
    # Load logs
    reader = LogReader(log_dir)
    responses = reader.read_responses(limit=limit)

    if not responses:
        print("No logged queries found.")
        return []

    # Initialize document manager
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    doc_manager.load_vector_store()

    print("="*80)
    print(f"REPLAYING {len(responses)} LOGGED QUERIES")
    print("="*80)

    results = []
    for i, response in enumerate(responses, 1):
        query = response["query"]
        print(f"\n[{i}/{len(responses)}] Replaying: {query[:60]}...")

        result = replay_query(
            query=query,
            document_manager=doc_manager,
            top_k=top_k,
            score_threshold=score_threshold,
            verbose=False
        )

        # Compare with original
        original_conf = response.get("confidence_level", "Unknown")
        new_conf = result["confidence_level"]

        print(f"  Original Confidence: {original_conf}")
        print(f"  New Confidence:      {new_conf}")
        print(f"  Chunks Retrieved:    {result['num_chunks_retrieved']}")

        results.append(result)

    return results


# ==============================================================================
# PARAMETER COMPARISON
# ==============================================================================

def compare_retrieval_parameters(
    query: str,
    top_k_values: List[int] = [2, 4, 6],
    threshold_values: List[float] = [0.4, 0.5, 0.6],
    document_manager: Optional[DocumentManager] = None
) -> List[Dict]:
    """
    Compare retrieval results across different parameter combinations.

    Args:
        query: User query to test
        top_k_values: List of top_k values to test
        threshold_values: List of threshold values to test
        document_manager: DocumentManager instance (creates one if None)

    Returns:
        List of results for each parameter combination
    """
    # Initialize document manager if not provided
    if document_manager is None:
        document_manager = DocumentManager(
            registry_path=REGISTRY_PATH,
            vector_store_path=VECTOR_STORE_PATH
        )
        document_manager.load_vector_store()

    print("="*80)
    print("PARAMETER COMPARISON")
    print("="*80)
    print(f"Query: {query}")
    print(f"Testing {len(top_k_values)} top_k values × {len(threshold_values)} thresholds")
    print("="*80)

    results = []

    for top_k in top_k_values:
        for threshold in threshold_values:
            result = replay_query(
                query=query,
                document_manager=document_manager,
                top_k=top_k,
                score_threshold=threshold,
                verbose=False
            )
            results.append(result)

    # Display comparison table
    table_data = []
    for result in results:
        table_data.append([
            result["top_k"],
            result["score_threshold"],
            result["num_chunks_retrieved"],
            f"{result['confidence_metrics']['avg_similarity']:.3f}",
            result["confidence_level"],
            f"{result['confidence_metrics']['confidence_score']:.0f}"
        ])

    headers = ["top_k", "threshold", "chunks", "avg_sim", "confidence", "score"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
    print()

    # Find best configuration
    best = max(results, key=lambda r: r["confidence_metrics"]["confidence_score"])
    print("Best Configuration:")
    print(f"  top_k={best['top_k']}, threshold={best['score_threshold']}")
    print(f"  Confidence: {best['confidence_level']} ({best['confidence_metrics']['confidence_score']:.0f}/100)")
    print("="*80)

    return results


def analyze_parameter_impact(
    queries: List[str],
    parameter_name: str = "top_k",
    parameter_values: List = [2, 4, 6, 8]
) -> Dict:
    """
    Analyze the impact of a single parameter across multiple queries.

    Args:
        queries: List of queries to test
        parameter_name: Parameter to vary ("top_k" or "threshold")
        parameter_values: Values to test

    Returns:
        Analysis results dictionary
    """
    # Initialize document manager
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    doc_manager.load_vector_store()

    print("="*80)
    print(f"PARAMETER IMPACT ANALYSIS: {parameter_name}")
    print("="*80)

    results_by_value = {val: [] for val in parameter_values}

    for query in queries:
        print(f"\nTesting: {query[:60]}...")

        for value in parameter_values:
            # Set parameters
            if parameter_name == "top_k":
                top_k = value
                threshold = 0.5
            else:  # threshold
                top_k = 4
                threshold = value

            result = replay_query(
                query=query,
                document_manager=doc_manager,
                top_k=top_k,
                score_threshold=threshold,
                verbose=False
            )

            results_by_value[value].append(result)

    # Compute averages
    print("\n" + "="*80)
    print("AVERAGE METRICS BY PARAMETER VALUE")
    print("="*80)

    table_data = []
    for value in parameter_values:
        results = results_by_value[value]

        avg_chunks = sum(r["num_chunks_retrieved"] for r in results) / len(results)
        avg_similarity = sum(r["confidence_metrics"]["avg_similarity"] for r in results) / len(results)
        avg_conf_score = sum(r["confidence_metrics"]["confidence_score"] for r in results) / len(results)

        # Count confidence levels
        high_count = sum(1 for r in results if r["confidence_level"] == "High")
        medium_count = sum(1 for r in results if r["confidence_level"] == "Medium")
        low_count = sum(1 for r in results if r["confidence_level"] == "Low")

        table_data.append([
            value,
            f"{avg_chunks:.1f}",
            f"{avg_similarity:.3f}",
            f"{avg_conf_score:.0f}",
            f"{high_count}",
            f"{medium_count}",
            f"{low_count}"
        ])

    headers = [parameter_name, "avg_chunks", "avg_sim", "avg_score", "high", "med", "low"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print("="*80)

    return {
        "parameter_name": parameter_name,
        "parameter_values": parameter_values,
        "results_by_value": results_by_value
    }


# ==============================================================================
# BATCH EVALUATION
# ==============================================================================

def batch_evaluate(
    queries: List[str],
    top_k: int = 4,
    score_threshold: float = 0.5,
    show_details: bool = False
) -> Dict:
    """
    Evaluate a batch of queries and compute aggregate statistics.

    Args:
        queries: List of queries to evaluate
        top_k: Number of chunks to retrieve
        score_threshold: Similarity threshold
        show_details: Whether to print details for each query

    Returns:
        Dictionary with evaluation results
    """
    # Initialize document manager
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    doc_manager.load_vector_store()

    print("="*80)
    print(f"BATCH EVALUATION ({len(queries)} queries)")
    print("="*80)
    print(f"Parameters: top_k={top_k}, threshold={score_threshold}")
    print()

    results = []
    for i, query in enumerate(queries, 1):
        if show_details:
            print(f"[{i}/{len(queries)}] {query}")

        result = replay_query(
            query=query,
            document_manager=doc_manager,
            top_k=top_k,
            score_threshold=score_threshold,
            verbose=show_details
        )
        results.append(result)

    # Compute statistics
    total = len(results)
    avg_chunks = sum(r["num_chunks_retrieved"] for r in results) / total
    avg_similarity = sum(r["confidence_metrics"]["avg_similarity"] for r in results) / total
    avg_conf_score = sum(r["confidence_metrics"]["confidence_score"] for r in results) / total

    high_count = sum(1 for r in results if r["confidence_level"] == "High")
    medium_count = sum(1 for r in results if r["confidence_level"] == "Medium")
    low_count = sum(1 for r in results if r["confidence_level"] == "Low")

    print("\n" + "="*80)
    print("BATCH EVALUATION RESULTS")
    print("="*80)
    print(f"Total Queries:        {total}")
    print(f"Avg Chunks Retrieved: {avg_chunks:.2f}")
    print(f"Avg Similarity:       {avg_similarity:.3f}")
    print(f"Avg Confidence Score: {avg_conf_score:.1f}/100")
    print()
    print("Confidence Distribution:")
    print(f"  High:   {high_count} ({high_count/total*100:.1f}%)")
    print(f"  Medium: {medium_count} ({medium_count/total*100:.1f}%)")
    print(f"  Low:    {low_count} ({low_count/total*100:.1f}%)")
    print("="*80)

    return {
        "total_queries": total,
        "avg_chunks": avg_chunks,
        "avg_similarity": avg_similarity,
        "avg_confidence_score": avg_conf_score,
        "high_confidence": high_count,
        "medium_confidence": medium_count,
        "low_confidence": low_count,
        "results": results
    }


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def quick_test(query: str, show_chunks: bool = False):
    """
    Quick test of a single query with default parameters.

    Args:
        query: Query string
        show_chunks: Whether to display retrieved chunks
    """
    doc_manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    doc_manager.load_vector_store()

    result = replay_query(query, doc_manager, verbose=True)

    if show_chunks and result["retrieved_docs"]:
        print("Retrieved Chunks:")
        for i, doc in enumerate(result["retrieved_docs"], 1):
            print(f"\n[{i}] Score: {result['similarity_scores'][i-1]:.3f}")
            print(f"    Source: {doc.metadata.get('document_name', 'Unknown')}")
            print(f"    Section: {doc.metadata.get('section', 'Unknown')}")
            print(f"    Preview: {doc.page_content[:150]}...")
