"""
Trivia Manager Module
=====================
Phase 56: Engineering Trivia, Study Tips, and Quote System

Handles:
- Monthly content generation via LLM
- Lazy validation (only regenerate if month changed)
- Seeded randomness for monthly variation
- Storage and retrieval of trivia, tips, and quotes

Architecture:
- Separates generation, storage, and retrieval logic
- No LLM calls during display (pre-generated content)
- Testable with injected dates
"""

import json
import hashlib
import calendar
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
import os

# OpenAI client for content generation
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Storage path
DATA_DIR = Path(__file__).parent / "data"
TRIVIA_FILE = DATA_DIR / "trivia_content.json"

# Content generation settings
QUOTES_COUNT = 50
GENERATION_MODEL = "gpt-4o-mini"  # Cost-effective for content generation


# ============================================================================
# STORAGE LAYER
# ============================================================================

def load_trivia_content() -> Optional[Dict[str, Any]]:
    """Load stored trivia content from JSON file."""
    try:
        if TRIVIA_FILE.exists():
            with open(TRIVIA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[TRIVIA] Failed to load content: {e}")
    return None


def save_trivia_content(content: Dict[str, Any]) -> bool:
    """Save trivia content to JSON file."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRIVIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        logger.info(f"[TRIVIA] Content saved to {TRIVIA_FILE}")
        return True
    except Exception as e:
        logger.error(f"[TRIVIA] Failed to save content: {e}")
        return False


# ============================================================================
# VALIDATION LAYER
# ============================================================================

def get_month_seed(year: int, month: int) -> str:
    """
    Generate a deterministic seed for the given month.
    Used to encourage LLM variation month-to-month.
    """
    seed_string = f"coco-trivia-{year}-{month:02d}"
    return hashlib.md5(seed_string.encode()).hexdigest()[:8]


def needs_regeneration(test_date: Optional[date] = None) -> bool:
    """
    Check if content needs regeneration.
    Returns True if:
    - No content exists
    - Stored month/year differs from current month/year
    """
    current = test_date or date.today()
    content = load_trivia_content()

    if content is None:
        logger.info("[TRIVIA] No content found, regeneration needed")
        return True

    stored_month = content.get("month")
    stored_year = content.get("year")

    if stored_month != current.month or stored_year != current.year:
        logger.info(f"[TRIVIA] Month changed ({stored_year}-{stored_month} -> {current.year}-{current.month}), regeneration needed")
        return True

    logger.info(f"[TRIVIA] Content valid for {current.year}-{current.month}")
    return False


# ============================================================================
# GENERATION LAYER
# ============================================================================

def generate_monthly_content(test_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Generate trivia, study tips, and quotes for the entire month.
    Uses LLM with seeded randomness for variation.
    """
    if not OPENAI_AVAILABLE:
        logger.error("[TRIVIA] OpenAI not available for content generation")
        return None

    current = test_date or date.today()
    year = current.year
    month = current.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_name = calendar.month_name[month]
    seed = get_month_seed(year, month)

    logger.info(f"[TRIVIA] Generating content for {month_name} {year} (seed: {seed})")

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Generate trivia for each day
        trivia = _generate_daily_trivia(client, days_in_month, month_name, year, seed)
        if not trivia:
            return None

        # Generate study tips for each day
        study_tips = _generate_daily_study_tips(client, days_in_month, month_name, year, seed)
        if not study_tips:
            return None

        # Generate quotes
        quotes = _generate_quotes(client, month_name, year, seed)
        if not quotes:
            return None

        content = {
            "month": month,
            "year": year,
            "seed": seed,
            "generated_at": datetime.now().isoformat(),
            "days_in_month": days_in_month,
            "trivia": trivia,
            "study_tips": study_tips,
            "quotes": quotes
        }

        logger.info(f"[TRIVIA] Generated {len(trivia)} trivia, {len(study_tips)} tips, {len(quotes)} quotes")
        return content

    except Exception as e:
        logger.error(f"[TRIVIA] Content generation failed: {e}")
        return None


def _generate_daily_trivia(client, days: int, month_name: str, year: int, seed: str) -> Optional[Dict[str, str]]:
    """Generate engineering trivia for each day of the month."""
    prompt = f"""Generate {days} unique engineering trivia facts.

Requirements:
- One trivia fact per entry (numbered 1 to {days})
- Focus on engineering disciplines: civil, mechanical, electrical, computer, chemical
- Include facts about inventions, discoveries, famous engineers, engineering principles
- Keep each fact concise (1-2 sentences, max 150 characters)
- Make them interesting and educational for college students

IMPORTANT RESTRICTIONS:
- Do NOT include specific calendar dates in the trivia (e.g., "On February 1..." or "In March 1884...")
- Do NOT tie facts to specific days of the month
- Each trivia should be timeless and applicable any day
- Focus on the engineering fact itself, not when it happened

Good example: "The Eiffel Tower was designed by Gustave Eiffel and contains over 18,000 iron parts."
Bad example: "On February 1, 1884, the first volume of the Oxford English Dictionary was published."

Variation seed: {seed} (use this to ensure unique content each month)

Output format (JSON object):
{{
  "1": "Trivia fact...",
  "2": "Trivia fact...",
  ...
}}

Return ONLY the JSON object, no markdown formatting."""

    try:
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=4000
        )

        content = response.choices[0].message.content.strip()
        # Clean up potential markdown formatting
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"[TRIVIA] Failed to generate trivia: {e}")
        return None


def _generate_daily_study_tips(client, days: int, month_name: str, year: int, seed: str) -> Optional[Dict[str, str]]:
    """Generate study tips for each day of the month."""
    prompt = f"""Generate {days} unique study tips for engineering students in {month_name} {year}.

Requirements:
- One study tip per day (numbered 1 to {days})
- Cover topics: time management, exam preparation, note-taking, problem-solving, lab work
- Include tips for programming, mathematics, physics, technical writing
- Keep each tip concise (1-2 sentences, max 150 characters)
- Make them practical and actionable
- Variation seed: {seed} (use this to ensure unique content)

Output format (JSON object):
{{
  "1": "Study tip for day 1...",
  "2": "Study tip for day 2...",
  ...
}}

Return ONLY the JSON object, no markdown formatting."""

    try:
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=4000
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        return json.loads(content)
    except Exception as e:
        logger.error(f"[TRIVIA] Failed to generate study tips: {e}")
        return None


def _generate_quotes(client, month_name: str, year: int, seed: str) -> Optional[List[str]]:
    """Generate 50 engineering-related motivational quotes."""
    prompt = f"""Generate exactly {QUOTES_COUNT} unique engineering-related motivational quotes for {month_name} {year}.

Requirements:
- Mix of famous engineer quotes and original motivational statements
- Focus on innovation, perseverance, problem-solving, creativity
- Include quotes from diverse engineers (Tesla, Curie, Musk, etc.)
- Keep each quote concise (max 100 characters)
- Variation seed: {seed} (use this to ensure unique content)

Output format (JSON array):
[
  "Quote 1...",
  "Quote 2...",
  ...
]

Return ONLY the JSON array with exactly {QUOTES_COUNT} quotes, no markdown formatting."""

    try:
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=3000
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        quotes = json.loads(content)
        if len(quotes) < QUOTES_COUNT:
            logger.warning(f"[TRIVIA] Only generated {len(quotes)} quotes, expected {QUOTES_COUNT}")
        return quotes[:QUOTES_COUNT]  # Ensure exactly 50
    except Exception as e:
        logger.error(f"[TRIVIA] Failed to generate quotes: {e}")
        return None


# ============================================================================
# RETRIEVAL LAYER
# ============================================================================

def get_today_content(test_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Get today's trivia and study tip.
    Returns content for display, no LLM calls.
    """
    current = test_date or date.today()
    day_key = str(current.day)

    content = load_trivia_content()

    if content is None:
        return {
            "trivia": "Engineering trivia loading...",
            "study_tip": "Study tip loading...",
            "available": False
        }

    trivia = content.get("trivia", {}).get(day_key, "No trivia for today")
    study_tip = content.get("study_tips", {}).get(day_key, "No study tip for today")

    return {
        "trivia": trivia,
        "study_tip": study_tip,
        "day": current.day,
        "month": content.get("month"),
        "year": content.get("year"),
        "available": True
    }


def get_random_quote(test_date: Optional[date] = None) -> str:
    """
    Get a random quote from the stored 50.
    Uses day-based pseudo-randomness for reproducibility within a session.
    """
    import random

    content = load_trivia_content()

    if content is None or "quotes" not in content:
        return "Stay curious, keep building!"

    quotes = content.get("quotes", [])
    if not quotes:
        return "Engineering is the art of making dreams real."

    # Use current timestamp for true randomness on each draw
    random.seed()
    return random.choice(quotes)


def get_all_quotes() -> List[str]:
    """Get all 50 quotes for admin view."""
    content = load_trivia_content()
    if content is None:
        return []
    return content.get("quotes", [])


def get_all_trivia() -> Dict[str, str]:
    """Get all trivia for admin view."""
    content = load_trivia_content()
    if content is None:
        return {}
    return content.get("trivia", {})


def get_all_study_tips() -> Dict[str, str]:
    """Get all study tips for admin view."""
    content = load_trivia_content()
    if content is None:
        return {}
    return content.get("study_tips", {})


def get_content_status() -> Dict[str, Any]:
    """Get content generation status for admin view."""
    content = load_trivia_content()

    if content is None:
        return {
            "generated": False,
            "month": None,
            "year": None,
            "generated_at": None,
            "trivia_count": 0,
            "tips_count": 0,
            "quotes_count": 0
        }

    return {
        "generated": True,
        "month": content.get("month"),
        "year": content.get("year"),
        "seed": content.get("seed"),
        "generated_at": content.get("generated_at"),
        "days_in_month": content.get("days_in_month"),
        "trivia_count": len(content.get("trivia", {})),
        "tips_count": len(content.get("study_tips", {})),
        "quotes_count": len(content.get("quotes", []))
    }


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_trivia_content(test_date: Optional[date] = None, force: bool = False) -> bool:
    """
    Initialize trivia content on application startup.
    Only generates if needed (lazy validation).

    Args:
        test_date: Optional date for testing
        force: Force regeneration even if content exists

    Returns:
        True if content is available (existing or newly generated)
    """
    if force or needs_regeneration(test_date):
        logger.info("[TRIVIA] Generating new monthly content...")
        content = generate_monthly_content(test_date)
        if content:
            save_trivia_content(content)
            return True
        else:
            logger.error("[TRIVIA] Failed to generate content")
            return False
    else:
        logger.info("[TRIVIA] Using existing content")
        return True
