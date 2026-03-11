"""
Office Contact Extractor - Phase 31
====================================

Deterministic extraction of office/location contact information from retrieved context.

Note: Personal contact information (phone numbers, emails) are intentionally not
stored in the system (privacy by design). This extractor focuses on:
- Office names and their physical locations
- Department/building information
- Staff names and roles (public directory info)

No LLM usage - pure regex-based pattern matching.

Functions:
- is_contact_query(): Intent detection (rule-based)
- extract_contacts_from_text(): Extract office/location entries
- format_contact_list(): Format extracted contacts into canonical response
"""

import re
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Intent detection patterns
CONTACT_TRIGGERS = [
    'contact', 'phone', 'email', 'reach', 'call',
    'number', 'address', 'located', 'location',
    'how to contact', 'who to contact', 'where is'
]

OFFICE_MARKERS = [
    'office', 'department', 'center', 'unit', 'services',
    'registrar', 'cashier', 'clinic', 'library', 'guidance'
]


def is_contact_query(query: str) -> bool:
    """
    Detect if query is asking about contact information.

    Returns True for: "How do I contact the registrar?", "Where is the clinic?"
    Returns False for: "What is a contact?", "Contact lens"

    Args:
        query: User query string

    Returns:
        True if contact query, False otherwise
    """
    query_lower = query.lower()

    # Must have contact trigger AND office marker
    has_trigger = any(t in query_lower for t in CONTACT_TRIGGERS)
    has_marker = any(m in query_lower for m in OFFICE_MARKERS)

    # Exclude definitional queries
    definitional_patterns = ['what is a', 'define', 'meaning of']
    is_definitional = any(p in query_lower for p in definitional_patterns)

    # Also accept direct "contact X" patterns
    contact_pattern = bool(re.search(r'contact\s+(?:the\s+)?[a-z]+', query_lower))

    return (has_trigger and has_marker and not is_definitional) or contact_pattern


def extract_contacts_from_text(text: str) -> List[Dict[str, Optional[str]]]:
    """
    Extract office/location contact entries from text.

    Pattern detection:
    - Office names (Registrar's Office, Student Affairs Office, etc.)
    - Location info (building, floor, room)
    - Staff names and roles
    - Department info

    Note: Does NOT extract personal phone/email (privacy by design)

    Args:
        text: Context text from retrieval

    Returns:
        List of contact dicts with:
        - office: Office name
        - building: Building name (if present)
        - floor: Floor info (if present)
        - room: Room number (if present)
        - department: Department name (if present)
        - staff: Staff name (if present)
        - role: Staff role (if present)
    """
    contacts = []
    seen_offices = set()  # Deduplicate

    # Split into lines
    lines = text.split('\n')

    current_contact = {}

    for line in lines:
        line = line.strip()
        if not line:
            if current_contact and current_contact.get('office'):
                _add_contact_if_unique(contacts, current_contact, seen_offices)
            current_contact = {}
            continue

        # Extract office name
        office = _extract_office_name(line)
        if office:
            if current_contact.get('office') and current_contact.get('office') != office:
                _add_contact_if_unique(contacts, current_contact, seen_offices)
                current_contact = {}
            current_contact['office'] = office

        # Extract location info
        location = _extract_location(line)
        if location:
            current_contact.update(location)

        # Extract staff info
        staff = _extract_staff(line)
        if staff:
            current_contact.update(staff)

        # Extract department
        department = _extract_department(line)
        if department:
            current_contact['department'] = department

    # Don't forget last contact
    if current_contact and current_contact.get('office'):
        _add_contact_if_unique(contacts, current_contact, seen_offices)

    logger.info(f"Extracted {len(contacts)} contacts from text")

    return contacts


def _extract_office_name(text: str) -> Optional[str]:
    """Extract office name from text."""
    # Common office patterns
    office_patterns = [
        r"((?:Registrar(?:'s)?|Cashier(?:'s)?|Treasurer(?:'s)?|Dean(?:'s)?|"
        r"Student\s+Affairs?|Guidance(?:\s+and\s+Testing)?|Health\s+Services?|"
        r"Information\s+Technology|Alumni|Admission(?:s)?|Library|Clinic|"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:'s\s+)?(?:Office|Center|Unit|Services?))",

        r"(Office\s+of\s+(?:the\s+)?[A-Z][a-zA-Z\s]+)",

        r"((?:CBA|CCS|CON|CASEd|COE|CHTM)\s+Office)",
    ]

    for pattern in office_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _normalize_office_name(match.group(1))

    return None


def _normalize_office_name(name: str) -> str:
    """Normalize office name casing and format."""
    # Title case, but preserve acronyms
    words = name.split()
    normalized = []
    for word in words:
        if word.upper() in ['CBA', 'CCS', 'CON', 'COE', 'CASED', 'CHTM', 'IT', 'HR']:
            normalized.append(word.upper())
        elif word.lower() in ['of', 'the', 'and', 'for']:
            normalized.append(word.lower())
        else:
            normalized.append(word.capitalize())
    return ' '.join(normalized)


def _extract_location(text: str) -> Dict[str, str]:
    """Extract location details from text."""
    location = {}

    # Building pattern
    building_match = re.search(
        r'(?:Building|Bldg\.?)\s*:?\s*([A-Z][A-Za-z\s]+(?:Building)?)',
        text, re.IGNORECASE
    )
    if building_match:
        location['building'] = building_match.group(1).strip()

    # Also match "A Building", "St. Augustine Building", etc.
    building_match2 = re.search(
        r'((?:St\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Building)',
        text
    )
    if building_match2 and 'building' not in location:
        location['building'] = building_match2.group(1).strip()

    # Floor pattern
    floor_match = re.search(
        r'(\d+(?:st|nd|rd|th)|Ground|First|Second|Third|Fourth|Fifth)\s+Floor',
        text, re.IGNORECASE
    )
    if floor_match:
        location['floor'] = floor_match.group(0)

    # Room pattern
    room_match = re.search(
        r'(?:Room|Rm\.?)\s*:?\s*([A-Z]?\d+(?:-[A-Z]?\d+)?)',
        text, re.IGNORECASE
    )
    if room_match:
        location['room'] = room_match.group(1)

    # Also match standalone room codes like "A101", "B205"
    room_match2 = re.search(r'\b([A-Z]\d{3}(?:-[A-Z]?\d{3})?)\b', text)
    if room_match2 and 'room' not in location:
        location['room'] = room_match2.group(1)

    return location


def _extract_staff(text: str) -> Dict[str, str]:
    """Extract staff name and role from text."""
    staff = {}

    # Staff name pattern (with title)
    name_match = re.search(
        r'((?:Dr\.|Engr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
        text
    )
    if name_match:
        staff['staff'] = name_match.group(1)

    # Role pattern
    role_patterns = [
        r'(Director|Dean|Head|Coordinator|Officer|Manager|Supervisor)',
        r'(OIC|Officer-in-Charge)',
    ]
    for pattern in role_patterns:
        role_match = re.search(pattern, text, re.IGNORECASE)
        if role_match:
            staff['role'] = role_match.group(1)
            break

    return staff


def _extract_department(text: str) -> Optional[str]:
    """Extract department name from text."""
    dept_patterns = [
        r'(College\s+of\s+[A-Za-z\s&]+)',
        r'(Department\s+of\s+[A-Za-z\s]+)',
        r'(Basic\s+Education\s+Department)',
        r'(Student\s+Affairs)',
    ]

    for pattern in dept_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _add_contact_if_unique(contacts: List[Dict], contact: Dict, seen: set):
    """Add contact if not duplicate."""
    key = contact.get('office', '').lower()
    if key and key not in seen:
        seen.add(key)
        contacts.append(contact.copy())


def format_contact_list(contacts: List[Dict[str, Optional[str]]]) -> str:
    """
    Format extracted contacts into canonical response string.

    Output format:
        Contact Information:

        1. Registrar's Office
           Location: A Building, Ground Floor, Room A101
           Department: College Department

    Args:
        contacts: List of contact dicts from extract_contacts_from_text()

    Returns:
        Formatted string ready for user display
    """
    if not contacts:
        return ""

    lines = ["Contact Information:\n"]

    for i, contact in enumerate(contacts, 1):
        office = contact.get('office', 'Office')
        building = contact.get('building')
        floor = contact.get('floor')
        room = contact.get('room')
        department = contact.get('department')
        staff = contact.get('staff')
        role = contact.get('role')

        lines.append(f"{i}. {office}")

        # Build location string
        location_parts = []
        if building:
            location_parts.append(building)
        if floor:
            location_parts.append(floor)
        if room:
            location_parts.append(f"Room {room}")

        if location_parts:
            lines.append(f"   Location: {', '.join(location_parts)}")

        if department:
            lines.append(f"   Department: {department}")

        if staff and role:
            lines.append(f"   Contact: {staff} ({role})")
        elif staff:
            lines.append(f"   Contact: {staff}")

        lines.append("")  # Blank line between contacts

    # Add privacy note
    lines.append("Note: For specific phone numbers or email addresses, please visit the office directly or check the official school website.")

    return '\n'.join(lines).strip()
