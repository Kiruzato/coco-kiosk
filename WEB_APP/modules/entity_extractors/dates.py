"""
Event Dates and Times Extractor - Phase 31
==========================================

Deterministic extraction of event dates, times, and schedules from retrieved context.

No LLM usage - pure regex-based pattern matching.

Functions:
- is_event_date_query(): Intent detection (rule-based)
- extract_events_from_text(): Extract event entries with dates/times
- format_event_list(): Format extracted events into canonical response
"""

import re
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Month names for pattern matching
MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
]
MONTHS_ABBREV = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

# Intent detection patterns
EVENT_TRIGGERS = [
    'when is', 'when are', 'what date', 'what time',
    'schedule', 'scheduled', 'upcoming', 'event', 'events',
    'webinar', 'seminar', 'meeting', 'activity', 'activities'
]

DATE_MARKERS = ['date', 'time', 'when', 'schedule']


def is_event_date_query(query: str) -> bool:
    """
    Detect if query is asking about event dates or schedules.

    Returns True for: "When is the webinar?", "What's the schedule?"
    Returns False for: "What is a date?", "How to schedule an appointment?"

    Args:
        query: User query string

    Returns:
        True if event date query, False otherwise
    """
    query_lower = query.lower()

    # Must have event trigger
    has_trigger = any(t in query_lower for t in EVENT_TRIGGERS)

    # Exclude definitional or procedural queries
    definitional_patterns = ['what is a', 'what are', 'define', 'meaning of', 'how to']
    is_definitional = any(p in query_lower for p in definitional_patterns)

    # Also accept if directly asking about dates/times
    has_date_marker = any(m in query_lower for m in DATE_MARKERS)

    return has_trigger and not is_definitional


def extract_events_from_text(text: str) -> List[Dict[str, Optional[str]]]:
    """
    Extract event entries with dates and times from text.

    Pattern detection:
    - Date formats: "January 30, 2026", "Jan 30, 2026", "01/30/2026"
    - Time formats: "9:00 AM", "9:00 am", "9:00AM"
    - Event names from context

    Args:
        text: Context text from retrieval

    Returns:
        List of event dicts with:
        - name: Event name/title
        - date: Extracted date string
        - time: Extracted time string (if present)
        - platform: Platform info (if present)
        - raw_text: Original text segment
    """
    events = []
    seen_dates = set()  # Deduplicate by date

    # Split text into logical segments
    lines = text.split('\n')

    # Build context window - collect multi-line event blocks
    current_event = {}

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            # Empty line might signal end of event block
            if current_event and current_event.get('date'):
                _add_event_if_unique(events, current_event, seen_dates)
            current_event = {}
            continue

        # Try to extract date from line
        date_match = _extract_date(line)
        if date_match:
            # Found a date - start or update event
            if current_event.get('date') and current_event.get('date') != date_match:
                # New date found, save previous event first
                _add_event_if_unique(events, current_event, seen_dates)
                current_event = {}
            current_event['date'] = date_match
            current_event['raw_text'] = current_event.get('raw_text', '') + ' ' + line

        # Try to extract time from line
        time_match = _extract_time(line)
        if time_match:
            current_event['time'] = time_match
            current_event['raw_text'] = current_event.get('raw_text', '') + ' ' + line

        # Try to extract platform from line
        platform_match = _extract_platform(line)
        if platform_match:
            current_event['platform'] = platform_match

        # Try to extract event name from line
        name_match = _extract_event_name(line)
        if name_match and not current_event.get('name'):
            current_event['name'] = name_match
            current_event['raw_text'] = current_event.get('raw_text', '') + ' ' + line

        # Look for theme/topic in line
        if 'theme' in line.lower() or 'topic' in line.lower():
            theme = _extract_theme(line)
            if theme:
                current_event['theme'] = theme

    # Don't forget the last event
    if current_event and current_event.get('date'):
        _add_event_if_unique(events, current_event, seen_dates)

    # Also try single-line extraction for inline date mentions
    full_text = ' '.join(lines)
    inline_events = _extract_inline_events(full_text)
    for event in inline_events:
        _add_event_if_unique(events, event, seen_dates)

    logger.info(f"Extracted {len(events)} events from text")

    return events


def _extract_date(text: str) -> Optional[str]:
    """Extract date from text in various formats."""
    text_lower = text.lower()

    # Pattern 1: "January 30, 2026" or "January 30 2026"
    month_pattern = '|'.join(MONTHS)
    match = re.search(
        rf'({month_pattern})\s+(\d{{1,2}}),?\s+(\d{{4}})',
        text_lower
    )
    if match:
        month = match.group(1).capitalize()
        day = match.group(2)
        year = match.group(3)
        return f"{month} {day}, {year}"

    # Pattern 2: "Jan 30, 2026" (abbreviated)
    abbrev_pattern = '|'.join(MONTHS_ABBREV)
    match = re.search(
        rf'({abbrev_pattern})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})',
        text_lower
    )
    if match:
        month_abbrev = match.group(1)
        month_idx = MONTHS_ABBREV.index(month_abbrev[:3])
        month = MONTHS[month_idx].capitalize()
        day = match.group(2)
        year = match.group(3)
        return f"{month} {day}, {year}"

    # Pattern 3: "01/30/2026" or "01-30-2026" (MM/DD/YYYY)
    match = re.search(r'(\d{2})[/\-](\d{2})[/\-](\d{4})', text)
    if match:
        month_num = int(match.group(1))
        day = match.group(2)
        year = match.group(3)
        if 1 <= month_num <= 12:
            month = MONTHS[month_num - 1].capitalize()
            return f"{month} {day}, {year}"

    # Pattern 4: Labeled date "Date: January 30, 2026"
    match = re.search(r'date\s*:\s*(.+)', text_lower)
    if match:
        return _extract_date(match.group(1))

    return None


def _extract_time(text: str) -> Optional[str]:
    """Extract time from text."""
    # Pattern: "9:00 AM", "9:00AM", "9:00 am"
    match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)', text)
    if match:
        hour = match.group(1)
        minute = match.group(2)
        period = match.group(3).upper()
        return f"{hour}:{minute} {period}"

    # Labeled time "Time: 9:00 AM"
    match = re.search(r'time\s*:\s*(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)', text, re.IGNORECASE)
    if match:
        hour = match.group(1)
        minute = match.group(2)
        period = match.group(3).upper()
        return f"{hour}:{minute} {period}"

    return None


def _extract_platform(text: str) -> Optional[str]:
    """Extract platform/location from text."""
    text_lower = text.lower()

    platforms = []

    if 'zoom' in text_lower:
        platforms.append('Zoom')
    if 'facebook' in text_lower or 'fb' in text_lower:
        platforms.append('Facebook Live')
    if 'google meet' in text_lower:
        platforms.append('Google Meet')
    if 'teams' in text_lower:
        platforms.append('Microsoft Teams')

    # Labeled platform "Platform: Zoom"
    match = re.search(r'platform\s*:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    if platforms:
        return ' and '.join(platforms)

    return None


def _extract_event_name(text: str) -> Optional[str]:
    """Extract event name/title from text."""
    # Look for quoted text (often event titles)
    match = re.search(r'"([^"]+)"', text)
    if match:
        return match.group(1)

    # Look for text after common event indicators
    event_indicators = ['webinar', 'seminar', 'workshop', 'conference', 'meeting']
    for indicator in event_indicators:
        if indicator in text.lower():
            # Return the line as event context
            return text.strip()[:100]  # Limit length

    return None


def _extract_theme(text: str) -> Optional[str]:
    """Extract theme/topic from text."""
    # Pattern: "theme: X" or "with the theme: X"
    match = re.search(r'theme\s*:\s*["\']?([^"\'\n]+)["\']?', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def _extract_inline_events(text: str) -> List[Dict]:
    """Extract events mentioned inline in text."""
    events = []

    # Pattern: "on January 30, 2026" often indicates an event date
    month_pattern = '|'.join(MONTHS)
    matches = re.finditer(
        rf'(?:on|for|scheduled\s+for)\s+({month_pattern})\s+(\d{{1,2}}),?\s+(\d{{4}})',
        text.lower()
    )

    for match in matches:
        month = match.group(1).capitalize()
        day = match.group(2)
        year = match.group(3)
        date = f"{month} {day}, {year}"

        # Get surrounding context for event name
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 50)
        context = text[start:end]

        events.append({
            'date': date,
            'raw_text': context,
            'name': _extract_event_name(context)
        })

    return events


def _add_event_if_unique(events: List[Dict], event: Dict, seen_dates: set):
    """Add event to list if not duplicate."""
    date_key = event.get('date', '')
    if date_key and date_key not in seen_dates:
        seen_dates.add(date_key)
        events.append(event.copy())


def format_event_list(events: List[Dict[str, Optional[str]]]) -> str:
    """
    Format extracted events into canonical response string.

    Output format:
        Upcoming events:

        1. [Event Name]
           Date: January 30, 2026
           Time: 9:00 AM
           Platform: Zoom and Facebook Live

    Args:
        events: List of event dicts from extract_events_from_text()

    Returns:
        Formatted string ready for user display
    """
    if not events:
        return ""

    lines = ["Here are the upcoming events:\n"]

    for i, event in enumerate(events, 1):
        name = event.get('name', 'Event')
        date = event.get('date', 'TBD')
        time = event.get('time')
        platform = event.get('platform')
        theme = event.get('theme')

        if theme:
            lines.append(f"{i}. {name}")
            lines.append(f"   Theme: \"{theme}\"")
        else:
            lines.append(f"{i}. {name}")

        lines.append(f"   Date: {date}")

        if time:
            lines.append(f"   Time: {time}")

        if platform:
            lines.append(f"   Platform: {platform}")

        lines.append("")  # Blank line between events

    return '\n'.join(lines).strip()
