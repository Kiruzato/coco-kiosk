"""
Query Logger - Phase 4
=======================
This module provides structured logging for RAG queries, retrievals, and responses.

Logs are stored in JSON format for easy analysis and replay.
"""

import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Default log directory
DEFAULT_LOG_DIR = Path(__file__).parent / "logs"

# Log file names
QUERY_LOG_FILE = "queries.jsonl"        # JSON Lines format
RETRIEVAL_LOG_FILE = "retrievals.jsonl"
RESPONSE_LOG_FILE = "responses.jsonl"

# Configure Python logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# QUERY LOGGER CLASS
# ==============================================================================

class QueryLogger:
    """
    Structured logger for RAG system queries and responses.

    Logs are stored in JSON Lines format (.jsonl) for easy parsing.
    Each log entry is a complete JSON object on a single line.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize the query logger.

        Args:
            log_dir: Directory to store log files (creates if doesn't exist)
        """
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log file paths
        self.query_log_path = self.log_dir / QUERY_LOG_FILE
        self.retrieval_log_path = self.log_dir / RETRIEVAL_LOG_FILE
        self.response_log_path = self.log_dir / RESPONSE_LOG_FILE

        logger.info(f"QueryLogger initialized. Logs will be saved to: {self.log_dir}")

    def log_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Log a user query.

        Args:
            query: User query string
            session_id: Optional session identifier
            metadata: Optional additional metadata

        Returns:
            Query ID (timestamp-based)
        """
        query_id = self._generate_id()
        timestamp = datetime.now().isoformat()

        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp,
            "session_id": session_id,
            "query": query,
            "metadata": metadata or {}
        }

        self._append_to_log(self.query_log_path, log_entry)
        logger.info(f"Logged query: {query_id}")

        return query_id

    def log_retrieval(
        self,
        query_id: str,
        query: str,
        retrieved_chunks: List[Dict],
        similarity_scores: List[float],
        retrieval_params: Optional[Dict] = None
    ):
        """
        Log retrieval results for a query.

        Args:
            query_id: Query identifier
            query: User query string
            retrieved_chunks: List of retrieved chunk dictionaries
            similarity_scores: List of similarity scores (parallel to chunks)
            retrieval_params: Optional retrieval parameters (k, threshold, etc.)
        """
        timestamp = datetime.now().isoformat()

        # Extract chunk metadata for logging
        chunk_metadata = []
        for i, (chunk, score) in enumerate(zip(retrieved_chunks, similarity_scores)):
            chunk_info = {
                "rank": i + 1,
                "similarity_score": round(float(score), 4),
                "document_name": chunk.metadata.get("document_name", "Unknown"),
                "document_id": chunk.metadata.get("document_id", "Unknown"),
                "chunk_id": chunk.metadata.get("chunk_id", "Unknown"),
                "section": chunk.metadata.get("section", "Unknown"),
                "file_type": chunk.metadata.get("file_type", "Unknown"),
                "preview": chunk.page_content[:100]
            }
            chunk_metadata.append(chunk_info)

        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp,
            "query": query,
            "num_chunks_retrieved": len(retrieved_chunks),
            "retrieval_params": retrieval_params or {},
            "similarity_scores": [round(float(s), 4) for s in similarity_scores],
            "avg_similarity": round(float(sum(similarity_scores) / len(similarity_scores)), 4) if similarity_scores else 0.0,
            "max_similarity": round(float(max(similarity_scores)), 4) if similarity_scores else 0.0,
            "min_similarity": round(float(min(similarity_scores)), 4) if similarity_scores else 0.0,
            "chunks": chunk_metadata
        }

        self._append_to_log(self.retrieval_log_path, log_entry)
        logger.info(f"Logged retrieval for query: {query_id} ({len(retrieved_chunks)} chunks)")

    def log_response(
        self,
        query_id: str,
        query: str,
        answer: str,
        confidence_level: str,
        confidence_metrics: Dict,
        sources_used: List[str],
        generation_params: Optional[Dict] = None,
        intent: Optional[str] = None,
        mode_used: Optional[str] = None
    ):
        """
        Log the final response to a query.

        Args:
            query_id: Query identifier
            query: User query string
            answer: Generated answer
            confidence_level: Confidence level (High/Medium/Low)
            confidence_metrics: Confidence computation metrics
            sources_used: List of source document names
            generation_params: Optional LLM generation parameters
        """
        timestamp = datetime.now().isoformat()

        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp,
            "query": query,
            "answer": answer,
            "confidence_level": confidence_level,
            "confidence_metrics": confidence_metrics,
            "sources_used": sources_used,
            "answer_length": len(answer),
            "generation_params": generation_params or {},
            "intent": intent,
            "mode_used": mode_used,
            "retrieval_performed": True
        }

        self._append_to_log(self.response_log_path, log_entry)
        logger.info(f"Logged response for query: {query_id} (confidence: {confidence_level})")

    def log_full_interaction(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        similarity_scores: List[float],
        answer: str,
        confidence_level: str,
        confidence_metrics: Dict,
        session_id: Optional[str] = None,
        retrieval_params: Optional[Dict] = None,
        generation_params: Optional[Dict] = None,
        intent: Optional[str] = None,
        mode_used: Optional[str] = None
    ) -> str:
        """
        Log a complete query-retrieval-response interaction.

        This is a convenience method that logs all three stages.

        Args:
            query: User query
            retrieved_chunks: Retrieved chunks
            similarity_scores: Similarity scores
            answer: Generated answer
            confidence_level: Confidence level
            confidence_metrics: Confidence metrics
            session_id: Optional session ID
            retrieval_params: Retrieval parameters
            generation_params: Generation parameters

        Returns:
            Query ID
        """
        # Log query
        query_id = self.log_query(query, session_id=session_id)

        # Log retrieval
        self.log_retrieval(
            query_id=query_id,
            query=query,
            retrieved_chunks=retrieved_chunks,
            similarity_scores=similarity_scores,
            retrieval_params=retrieval_params
        )

        # Extract source names
        sources_used = list(set([
            chunk.metadata.get("document_name", "Unknown")
            for chunk in retrieved_chunks
        ]))

        # Log response
        self.log_response(
            query_id=query_id,
            query=query,
            answer=answer,
            confidence_level=confidence_level,
            confidence_metrics=confidence_metrics,
            sources_used=sources_used,
            generation_params=generation_params,
            intent=intent,
            mode_used=mode_used
        )

        return query_id

    def log_general_interaction(
        self,
        query: str,
        answer: str,
        session_id: Optional[str] = None,
        intent: Optional[str] = None,
        mode_used: str = "general"
    ) -> str:
        """
        Log a general knowledge interaction (no retrieval).

        Args:
            query: User query
            answer: Generated answer
            session_id: Optional session identifier
            intent: Classified intent
            mode_used: Mode used (should be "general")

        Returns:
            Query ID
        """
        query_id = self.log_query(query, session_id=session_id)
        timestamp = datetime.now().isoformat()

        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp,
            "query": query,
            "answer": answer,
            "intent": intent,
            "mode_used": mode_used,
            "retrieval_performed": False,
            "answer_length": len(answer)
        }

        self._append_to_log(self.response_log_path, log_entry)
        logger.info(f"Logged general knowledge query: {query_id}")

        return query_id

    def log_ambiguous_interaction(
        self,
        query: str,
        clarification: str,
        session_id: Optional[str] = None,
        intent: Optional[str] = None
    ) -> str:
        """
        Log an ambiguous query interaction.

        Args:
            query: User query
            clarification: Clarification message shown to user
            session_id: Optional session identifier
            intent: Classified intent (should be "ambiguous")

        Returns:
            Query ID
        """
        query_id = self.log_query(query, session_id=session_id)
        timestamp = datetime.now().isoformat()

        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp,
            "query": query,
            "clarification": clarification,
            "intent": intent,
            "mode_used": "clarification",
            "retrieval_performed": False
        }

        self._append_to_log(self.response_log_path, log_entry)
        logger.info(f"Logged ambiguous query: {query_id}")

        return query_id

    def _append_to_log(self, log_path: Path, entry: Dict):
        """
        Append a log entry to a JSON Lines file.

        Args:
            log_path: Path to log file
            entry: Dictionary to log
        """
        def convert_to_json_serializable(obj):
            """Convert numpy types to Python types for JSON serialization."""
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=convert_to_json_serializable) + '\n')

    def _generate_id(self) -> str:
        """
        Generate a unique query ID based on timestamp.

        Returns:
            Unique identifier string
        """
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


# ==============================================================================
# LOG READING AND ANALYSIS
# ==============================================================================

class LogReader:
    """
    Reader for structured log files.

    Provides methods to load and analyze logged queries.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize the log reader.

        Args:
            log_dir: Directory containing log files
        """
        self.log_dir = log_dir or DEFAULT_LOG_DIR

    def read_queries(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Read query logs.

        Args:
            limit: Maximum number of entries to read (None = all)

        Returns:
            List of query log entries
        """
        return self._read_jsonl(self.log_dir / QUERY_LOG_FILE, limit)

    def read_retrievals(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Read retrieval logs.

        Args:
            limit: Maximum number of entries to read

        Returns:
            List of retrieval log entries
        """
        return self._read_jsonl(self.log_dir / RETRIEVAL_LOG_FILE, limit)

    def read_responses(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Read response logs.

        Args:
            limit: Maximum number of entries to read

        Returns:
            List of response log entries
        """
        return self._read_jsonl(self.log_dir / RESPONSE_LOG_FILE, limit)

    def get_interaction_by_id(self, query_id: str) -> Dict:
        """
        Get a complete interaction by query ID.

        Args:
            query_id: Query identifier

        Returns:
            Dictionary with query, retrieval, and response data
        """
        queries = self.read_queries()
        retrievals = self.read_retrievals()
        responses = self.read_responses()

        query = next((q for q in queries if q["query_id"] == query_id), None)
        retrieval = next((r for r in retrievals if r["query_id"] == query_id), None)
        response = next((r for r in responses if r["query_id"] == query_id), None)

        return {
            "query_id": query_id,
            "query": query,
            "retrieval": retrieval,
            "response": response
        }

    def get_recent_interactions(self, limit: int = 10) -> List[Dict]:
        """
        Get the most recent complete interactions.

        Args:
            limit: Number of interactions to retrieve

        Returns:
            List of interaction dictionaries
        """
        responses = self.read_responses(limit=limit)

        interactions = []
        for response in responses:
            query_id = response["query_id"]
            interaction = self.get_interaction_by_id(query_id)
            interactions.append(interaction)

        return interactions

    def get_low_confidence_queries(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get queries that resulted in low confidence responses.

        Args:
            limit: Maximum number to return

        Returns:
            List of low confidence interactions
        """
        responses = self.read_responses()
        low_conf = [r for r in responses if r.get("confidence_level") == "Low"]

        if limit:
            low_conf = low_conf[:limit]

        return low_conf

    def get_retrieval_stats(self) -> Dict:
        """
        Compute statistics across all retrievals.

        Returns:
            Dictionary with retrieval statistics
        """
        retrievals = self.read_retrievals()

        if not retrievals:
            return {"error": "No retrievals logged"}

        total = len(retrievals)
        avg_chunks = sum(r["num_chunks_retrieved"] for r in retrievals) / total
        avg_similarity = sum(r["avg_similarity"] for r in retrievals) / total

        return {
            "total_retrievals": total,
            "avg_chunks_per_query": round(avg_chunks, 2),
            "avg_similarity_score": round(avg_similarity, 3),
            "max_chunks_retrieved": max(r["num_chunks_retrieved"] for r in retrievals),
            "min_chunks_retrieved": min(r["num_chunks_retrieved"] for r in retrievals)
        }

    def _read_jsonl(self, file_path: Path, limit: Optional[int] = None) -> List[Dict]:
        """
        Read a JSON Lines file.

        Args:
            file_path: Path to JSONL file
            limit: Maximum number of lines to read

        Returns:
            List of parsed JSON objects
        """
        if not file_path.exists():
            logger.warning(f"Log file not found: {file_path}")
            return []

        entries = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse line {i+1} in {file_path}")

        return entries


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def print_log_summary(log_dir: Optional[Path] = None):
    """
    Print a summary of logged data.

    Args:
        log_dir: Log directory path
    """
    reader = LogReader(log_dir)

    queries = reader.read_queries()
    retrievals = reader.read_retrievals()
    responses = reader.read_responses()

    print("="*80)
    print("LOG SUMMARY")
    print("="*80)
    print(f"Total Queries:    {len(queries)}")
    print(f"Total Retrievals: {len(retrievals)}")
    print(f"Total Responses:  {len(responses)}")
    print()

    if responses:
        confidence_counts = {}
        for r in responses:
            conf = r.get("confidence_level", "Unknown")
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        print("Confidence Distribution:")
        for conf, count in sorted(confidence_counts.items()):
            print(f"  {conf}: {count}")
        print()

    stats = reader.get_retrieval_stats()
    if "error" not in stats:
        print("Retrieval Statistics:")
        print(f"  Avg Chunks per Query: {stats['avg_chunks_per_query']}")
        print(f"  Avg Similarity Score: {stats['avg_similarity_score']}")
    print("="*80)
