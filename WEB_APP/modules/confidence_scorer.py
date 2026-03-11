"""
Confidence Scoring Module - Phase 4
====================================
This module computes confidence scores for chatbot responses based on
retrieval quality metrics.

Confidence is determined by:
1. Average similarity score of retrieved chunks
2. Number of relevant chunks retrieved
3. Score distribution (variance)

Output: High / Medium / Low confidence levels
"""

from typing import List, Dict, Tuple
from enum import Enum
import statistics


class ConfidenceLevel(Enum):
    """Confidence level enumeration."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# ==============================================================================
# CONFIDENCE THRESHOLDS
# ==============================================================================

# Similarity score thresholds (0.0 - 1.0)
HIGH_SIMILARITY_THRESHOLD = 0.75    # Scores >= 0.75 indicate high relevance
MEDIUM_SIMILARITY_THRESHOLD = 0.55  # Scores >= 0.55 indicate medium relevance

# Minimum number of chunks for confident answer
MIN_CHUNKS_HIGH_CONFIDENCE = 2
MIN_CHUNKS_MEDIUM_CONFIDENCE = 1

# Score variance threshold (lower = more consistent)
MAX_VARIANCE_HIGH_CONFIDENCE = 0.05


# ==============================================================================
# CONFIDENCE SCORING FUNCTIONS
# ==============================================================================

def compute_confidence_score(
    similarity_scores: List[float],
    min_chunks_retrieved: int = 1
) -> Tuple[ConfidenceLevel, Dict[str, float]]:
    """
    Compute confidence level based on retrieval quality metrics.

    Args:
        similarity_scores: List of similarity scores from retrieval (0.0-1.0)
        min_chunks_retrieved: Minimum number of chunks for valid answer

    Returns:
        Tuple of (ConfidenceLevel, metrics_dict)

        metrics_dict contains:
            - avg_similarity: Average similarity score
            - max_similarity: Best similarity score
            - min_similarity: Worst similarity score
            - num_chunks: Number of chunks retrieved
            - score_variance: Variance in scores
            - confidence_score: Numerical confidence (0-100)
    """
    # Handle edge cases
    if not similarity_scores:
        return ConfidenceLevel.LOW, {
            "avg_similarity": 0.0,
            "max_similarity": 0.0,
            "min_similarity": 0.0,
            "num_chunks": 0,
            "score_variance": 0.0,
            "confidence_score": 0.0,
            "reason": "No chunks retrieved"
        }

    # Calculate metrics
    num_chunks = len(similarity_scores)
    avg_similarity = statistics.mean(similarity_scores)
    max_similarity = max(similarity_scores)
    min_similarity = min(similarity_scores)

    # Calculate variance (measure of consistency)
    if len(similarity_scores) > 1:
        score_variance = statistics.variance(similarity_scores)
    else:
        score_variance = 0.0

    # Build metrics dictionary
    metrics = {
        "avg_similarity": round(avg_similarity, 3),
        "max_similarity": round(max_similarity, 3),
        "min_similarity": round(min_similarity, 3),
        "num_chunks": num_chunks,
        "score_variance": round(score_variance, 3),
    }

    # Determine confidence level
    confidence_level, confidence_score, reason = _classify_confidence(
        avg_similarity=avg_similarity,
        max_similarity=max_similarity,
        num_chunks=num_chunks,
        score_variance=score_variance,
        min_chunks_retrieved=min_chunks_retrieved
    )

    # Add confidence score and reason to metrics
    metrics["confidence_score"] = confidence_score
    metrics["reason"] = reason

    return confidence_level, metrics


def _classify_confidence(
    avg_similarity: float,
    max_similarity: float,
    num_chunks: int,
    score_variance: float,
    min_chunks_retrieved: int
) -> Tuple[ConfidenceLevel, float, str]:
    """
    Classify confidence level based on metrics.

    Args:
        avg_similarity: Average similarity score
        max_similarity: Maximum similarity score
        num_chunks: Number of retrieved chunks
        score_variance: Variance in similarity scores
        min_chunks_retrieved: Minimum chunks required

    Returns:
        Tuple of (ConfidenceLevel, numerical_score, reason)
    """
    # Check if insufficient chunks retrieved
    if num_chunks < min_chunks_retrieved:
        return ConfidenceLevel.LOW, 20.0, f"Insufficient chunks ({num_chunks} < {min_chunks_retrieved})"

    # HIGH CONFIDENCE criteria:
    # - High average similarity (>= 0.75)
    # - Multiple relevant chunks (>= 2)
    # - Low variance (scores are consistent)
    # - At least one very relevant chunk (>= 0.80)
    if (avg_similarity >= HIGH_SIMILARITY_THRESHOLD and
        num_chunks >= MIN_CHUNKS_HIGH_CONFIDENCE and
        score_variance <= MAX_VARIANCE_HIGH_CONFIDENCE and
        max_similarity >= 0.80):

        confidence_score = min(95.0, 70 + (avg_similarity * 30))
        return ConfidenceLevel.HIGH, confidence_score, "Strong relevance with consistent scores"

    # MEDIUM CONFIDENCE criteria:
    # - Moderate average similarity (>= 0.55)
    # - At least one relevant chunk
    # - OR high max similarity even if average is lower
    if (avg_similarity >= MEDIUM_SIMILARITY_THRESHOLD and
        num_chunks >= MIN_CHUNKS_MEDIUM_CONFIDENCE):

        confidence_score = min(75.0, 40 + (avg_similarity * 50))
        return ConfidenceLevel.MEDIUM, confidence_score, "Moderate relevance"

    # Alternative MEDIUM: High max score but lower average
    if max_similarity >= HIGH_SIMILARITY_THRESHOLD and num_chunks >= 1:
        confidence_score = min(70.0, 30 + (max_similarity * 50))
        return ConfidenceLevel.MEDIUM, confidence_score, "One highly relevant chunk found"

    # LOW CONFIDENCE: Everything else
    confidence_score = max(10.0, avg_similarity * 40)
    return ConfidenceLevel.LOW, confidence_score, "Low relevance scores"


def should_answer_confidently(
    confidence_level: ConfidenceLevel,
    min_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
) -> bool:
    """
    Determine if the system should provide an answer based on confidence.

    Args:
        confidence_level: Computed confidence level
        min_confidence: Minimum required confidence level

    Returns:
        True if should answer, False if should reject
    """
    confidence_order = {
        ConfidenceLevel.LOW: 0,
        ConfidenceLevel.MEDIUM: 1,
        ConfidenceLevel.HIGH: 2
    }

    return confidence_order[confidence_level] >= confidence_order[min_confidence]


def format_confidence_display(
    confidence_level: ConfidenceLevel,
    metrics: Dict[str, float],
    show_details: bool = True
) -> str:
    """
    Format confidence information for display.

    Args:
        confidence_level: Computed confidence level
        metrics: Metrics dictionary from compute_confidence_score()
        show_details: Whether to show detailed metrics

    Returns:
        Formatted confidence string
    """
    output = f"Confidence: {confidence_level.value}"

    if show_details:
        output += f" ({metrics['confidence_score']:.0f}/100)"
        output += f"\n  - Average Similarity: {metrics['avg_similarity']:.2f}"
        output += f"\n  - Chunks Retrieved: {metrics['num_chunks']}"
        output += f"\n  - Reason: {metrics['reason']}"

    return output


# ==============================================================================
# RETRIEVAL QUALITY ANALYSIS
# ==============================================================================

def analyze_retrieval_quality(
    query: str,
    retrieved_chunks: List[Dict],
    similarity_scores: List[float]
) -> Dict:
    """
    Analyze the quality of retrieval for a given query.

    Args:
        query: User query string
        retrieved_chunks: List of retrieved chunk dictionaries
        similarity_scores: List of similarity scores

    Returns:
        Analysis dictionary with quality metrics
    """
    if not retrieved_chunks or not similarity_scores:
        return {
            "query": query,
            "num_chunks": 0,
            "quality": "POOR",
            "issues": ["No chunks retrieved"],
            "recommendations": ["Adjust relevance threshold", "Add more documents"]
        }

    # Calculate metrics
    num_chunks = len(retrieved_chunks)
    avg_score = statistics.mean(similarity_scores)
    max_score = max(similarity_scores)
    min_score = min(similarity_scores)

    # Determine quality
    issues = []
    recommendations = []

    if num_chunks < 2:
        issues.append("Only one chunk retrieved")
        recommendations.append("Consider lowering relevance threshold")

    if avg_score < 0.6:
        issues.append("Low average similarity")
        recommendations.append("Query may be out of scope for knowledge base")

    if len(similarity_scores) > 1:
        score_variance = statistics.variance(similarity_scores)
        if score_variance > 0.1:
            issues.append("High variance in scores")
            recommendations.append("Retrieval may be unfocused")

    # Classify overall quality
    if avg_score >= 0.75 and num_chunks >= 2:
        quality = "EXCELLENT"
    elif avg_score >= 0.6 and num_chunks >= 1:
        quality = "GOOD"
    elif avg_score >= 0.5:
        quality = "FAIR"
    else:
        quality = "POOR"

    return {
        "query": query,
        "num_chunks": num_chunks,
        "avg_similarity": round(avg_score, 3),
        "max_similarity": round(max_score, 3),
        "min_similarity": round(min_score, 3),
        "quality": quality,
        "issues": issues if issues else ["None"],
        "recommendations": recommendations if recommendations else ["None"]
    }


# ==============================================================================
# CHUNK RELEVANCE SCORING
# ==============================================================================

def score_chunk_relevance(similarity_score: float) -> str:
    """
    Convert similarity score to human-readable relevance level.

    Args:
        similarity_score: Similarity score (0.0-1.0)

    Returns:
        Relevance level string
    """
    if similarity_score >= 0.85:
        return "Highly Relevant"
    elif similarity_score >= 0.70:
        return "Relevant"
    elif similarity_score >= 0.55:
        return "Somewhat Relevant"
    elif similarity_score >= 0.40:
        return "Marginally Relevant"
    else:
        return "Low Relevance"


def get_confidence_thresholds() -> Dict[str, float]:
    """
    Get current confidence scoring thresholds.

    Returns:
        Dictionary of threshold values
    """
    return {
        "high_similarity_threshold": HIGH_SIMILARITY_THRESHOLD,
        "medium_similarity_threshold": MEDIUM_SIMILARITY_THRESHOLD,
        "min_chunks_high_confidence": MIN_CHUNKS_HIGH_CONFIDENCE,
        "min_chunks_medium_confidence": MIN_CHUNKS_MEDIUM_CONFIDENCE,
        "max_variance_high_confidence": MAX_VARIANCE_HIGH_CONFIDENCE
    }
