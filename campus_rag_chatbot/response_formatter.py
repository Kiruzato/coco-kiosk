"""
Response Formatter - Phase 17B
==============================
Transforms raw LLM answers into structured, kiosk-friendly formats.

Output Structure:
- Direct Answer (1-2 sentence summary)
- Key Details (bullet points)
- Notes/Conditions (optional)
- Sources citation
- Confidence disclaimer (for MEDIUM confidence)

This module is presentation-only and does not modify:
- Retrieval logic
- Routing logic
- Grounding validation
- Confidence thresholds
"""

import re
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Patterns that indicate rejection/clarification messages (skip formatting)
SKIP_FORMATTING_PATTERNS = [
    r"I couldn't find",
    r"I don't have",
    r"Could you clarify",
    r"Please choose",
    r"Which .* did you mean",
    r"I found multiple",
    r"\[RAG-Only Mode\]",
    r"please rephrase",
    r"I'm not sure",
]

# Keywords that indicate notes/conditions section
NOTE_KEYWORDS = [
    "note:", "notes:", "important:", "requirement:", "requirements:",
    "condition:", "conditions:", "must", "should", "need to", "required",
    "exception:", "exceptions:", "however,", "please note"
]

# Minimum answer length to apply full formatting
MIN_LENGTH_FOR_FORMATTING = 100


def should_skip_formatting(answer: str) -> bool:
    """
    Check if answer should skip formatting (rejections, clarifications).

    Args:
        answer: Raw answer text

    Returns:
        True if formatting should be skipped
    """
    answer_lower = answer.lower()

    for pattern in SKIP_FORMATTING_PATTERNS:
        if re.search(pattern, answer, re.IGNORECASE):
            return True

    # Skip very short answers
    if len(answer.strip()) < MIN_LENGTH_FOR_FORMATTING:
        return False  # Still format short answers, just simpler

    return False


def extract_sentences(text: str) -> List[str]:
    """
    Split text into sentences.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def extract_direct_answer(raw_answer: str) -> str:
    """
    Extract the first 1-2 sentences as the direct answer summary.

    Args:
        raw_answer: Full answer text

    Returns:
        Direct answer summary
    """
    sentences = extract_sentences(raw_answer)

    if not sentences:
        return raw_answer.strip()

    # Take first sentence, optionally second if first is very short
    direct = sentences[0]
    if len(sentences) > 1 and len(direct) < 80:
        direct = f"{sentences[0]} {sentences[1]}"

    return direct


def extract_key_details(raw_answer: str) -> List[str]:
    """
    Extract key facts/details as bullet points.

    Args:
        raw_answer: Full answer text

    Returns:
        List of key detail strings
    """
    sentences = extract_sentences(raw_answer)

    if len(sentences) <= 2:
        return []  # Not enough content for details

    # Skip first 1-2 sentences (used for direct answer)
    start_idx = 2 if len(sentences[0]) < 80 else 1

    details = []
    for sentence in sentences[start_idx:]:
        # Skip if it looks like a note/condition
        if any(kw in sentence.lower() for kw in NOTE_KEYWORDS):
            continue

        # Clean up the sentence for bullet format
        detail = sentence.strip()
        if detail and not detail.endswith('.'):
            detail += '.'

        if detail and len(detail) > 10:
            details.append(detail)

    # Limit to reasonable number of bullets
    return details[:5]


def extract_notes(raw_answer: str) -> List[str]:
    """
    Extract notes, conditions, or requirements.

    Args:
        raw_answer: Full answer text

    Returns:
        List of note strings
    """
    sentences = extract_sentences(raw_answer)
    notes = []

    for sentence in sentences:
        sentence_lower = sentence.lower()

        # Check if sentence contains note keywords
        if any(kw in sentence_lower for kw in NOTE_KEYWORDS):
            note = sentence.strip()
            if note and len(note) > 10:
                notes.append(note)

    return notes[:3]  # Limit notes


def format_sources(sources: List) -> str:
    """
    Format source citations.

    Args:
        sources: List of Source objects with document_name attribute

    Returns:
        Formatted sources string
    """
    if not sources:
        return ""

    # Get unique document names
    doc_names = []
    seen = set()
    for source in sources:
        name = getattr(source, 'document_name', str(source))
        if name not in seen:
            doc_names.append(name)
            seen.add(name)

    if not doc_names:
        return ""

    return f"*Sources: {', '.join(doc_names)}*"


def build_structured_answer(
    raw_answer: str,
    confidence_level: str,
    sources: List = None,
    mode: str = "campus"
) -> Optional[dict]:
    """
    Build structured answer object for frontend rendering - Phase 17B.1.

    Args:
        raw_answer: Raw answer text from LLM
        confidence_level: "High", "Medium", or "Low" (or ConfidenceLevel enum)
        sources: List of Source objects (optional)
        mode: "campus" or "general"

    Returns:
        dict with: direct_answer, key_details, notes, disclaimer
        Returns None if formatting should be skipped
    """
    if sources is None:
        sources = []

    # Convert enum to string if needed
    if hasattr(confidence_level, 'value'):
        confidence_level = confidence_level.value

    # Skip formatting for rejections/clarifications
    if should_skip_formatting(raw_answer):
        logger.debug("Skipping structured answer for rejection/clarification")
        return None

    # Extract components
    direct_answer = extract_direct_answer(raw_answer)
    key_details = extract_key_details(raw_answer)
    notes_list = extract_notes(raw_answer)

    # Combine notes into single string (if any)
    notes = ". ".join(notes_list) if notes_list else None

    # Add disclaimer for MEDIUM confidence
    disclaimer = None
    if confidence_level.lower() == "medium":
        disclaimer = "Some details may vary. Please verify with campus staff if needed."

    return {
        "direct_answer": direct_answer,
        "key_details": key_details,
        "notes": notes,
        "disclaimer": disclaimer
    }


def format_structured_answer(
    raw_answer: str,
    confidence_level: str,
    sources: List = None,
    mode: str = "campus"
) -> str:
    """
    Transform raw LLM answer into structured format (legacy text-based).

    Note: This function is kept for backward compatibility.
    New code should use build_structured_answer() for frontend rendering.

    Args:
        raw_answer: Raw answer text from LLM
        confidence_level: "High", "Medium", or "Low" (or ConfidenceLevel enum)
        sources: List of Source objects (optional)
        mode: "campus" or "general"

    Returns:
        Formatted answer with sections (Markdown-style)
    """
    if sources is None:
        sources = []

    # Convert enum to string if needed
    if hasattr(confidence_level, 'value'):
        confidence_level = confidence_level.value

    # Skip formatting for rejections/clarifications
    if should_skip_formatting(raw_answer):
        logger.debug("Skipping formatting for rejection/clarification")
        return raw_answer

    # Very short answers get minimal formatting
    if len(raw_answer.strip()) < MIN_LENGTH_FOR_FORMATTING:
        sections = [raw_answer.strip()]

        # Add sources if available
        sources_str = format_sources(sources)
        if sources_str:
            sections.append(f"---\n{sources_str}")

        # Add disclaimer for MEDIUM confidence
        if confidence_level.lower() == "medium":
            sections.append("_Some details may vary. Please verify with campus staff if needed._")

        return "\n\n".join(sections)

    # Build structured sections
    sections = []

    # 1. Direct Answer
    direct = extract_direct_answer(raw_answer)
    sections.append(f"**Direct Answer**\n{direct}")

    # 2. Key Details (bullets)
    details = extract_key_details(raw_answer)
    if details:
        bullets = "\n".join(f"- {d}" for d in details)
        sections.append(f"**Key Details**\n{bullets}")

    # 3. Notes (optional)
    notes = extract_notes(raw_answer)
    if notes:
        note_bullets = "\n".join(f"- {n}" for n in notes)
        sections.append(f"**Notes**\n{note_bullets}")

    # 4. Sources
    sources_str = format_sources(sources)
    if sources_str:
        sections.append(f"---\n{sources_str}")

    # 5. Confidence disclaimer (MEDIUM only)
    if confidence_level.lower() == "medium":
        sections.append("_Some details may vary. Please verify with campus staff if needed._")

    formatted = "\n\n".join(sections)
    logger.debug(f"Formatted answer: {len(raw_answer)} chars -> {len(formatted)} chars")

    return formatted
