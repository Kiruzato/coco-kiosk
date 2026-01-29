"""
Dean Entity Extractor - Phase 18.2
===================================

Deterministic extraction of dean entries from retrieved context.

No LLM usage - pure regex-based pattern matching.

Functions:
- is_dean_enumeration_query(): Intent detection (rule-based)
- extract_deans_from_text(): Extract dean entities from text
- format_dean_list(): Format extracted deans into canonical response
"""

import re
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def is_dean_enumeration_query(query: str) -> bool:
    """
    Detect if query is requesting dean enumeration.
    
    Rule-based detection (no ML):
    - Contains enumeration trigger: "who are", "list", "show", "all"
    - Contains entity type: "dean" or "deans"
    
    Examples:
        >>> is_dean_enumeration_query("who are the deans")
        True
        >>> is_dean_enumeration_query("list all deans")
        True
        >>> is_dean_enumeration_query("who is the dean of CASEd")
        False
    
    Args:
        query: User query string
    
    Returns:
        True if dean enumeration query, False otherwise
    """
    query_lower = query.lower()
    
    # Enumeration triggers
    enumeration_triggers = [
        'who are',
        'list',
        'show',
        'all'
    ]
    
    # Entity type
    has_dean = 'dean' in query_lower
    
    # Trigger + entity = enumeration intent
    has_trigger = any(trigger in query_lower for trigger in enumeration_triggers)
    
    return has_trigger and has_dean


def extract_deans_from_text(text: str) -> List[Dict[str, str]]:
    """
    Deterministically extract dean entries from text.
    
    No LLM usage - pure regex-based extraction.
    
    Pattern detection:
    - Person title (Dr., Engr., Arch., Prof., Mr., Ms., Mrs.)
    - Full name (capitalized words)
    - Optional: "Dean" or "Dean," marker
    - Optional: College/department info
    
    Features:
    - Deduplication by name
    - Preserves document order
    - Normalizes whitespace
    - Handles various formatting patterns
    
    Examples:
        text = '''
        Dr. ERIC A. MATRIANO (College of Business & Accountancy)
        Engr. NOEL H. YAP (College of Computer Studies)
        '''
        
        deans = extract_deans_from_text(text)
        # [
        #   {'full_name': 'Dr. Eric A. Matriano', ...},
        #   {'full_name': 'Engr. Noel H. Yap', ...}
        # ]
    
    Args:
        text: Context text (typically from synthetic chunk)
    
    Returns:
        List of dean dicts with:
        - full_name: Complete name with title
        - title: Academic title (Dr., Engr., etc.)
        - college: Department/college if present
        - raw_line: Original line for debugging
    """
    deans = []
    seen_names = set()  # For deduplication
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines or very short lines
        if not line or len(line) < 10:
            continue
        
        # Skip section headers (all caps, short)
        if line.upper() == line and len(line) < 30 and line.replace(' ', '').isalpha():
            continue
        
        # Check if line contains person title (required for dean entry)
        if not re.search(r'(Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)', line, re.IGNORECASE):
            continue
        
        # Extract dean entry
        dean = _parse_dean_line(line)
        
        if dean:
            # Deduplicate by normalized name
            name_key = dean['full_name'].lower()
            if name_key not in seen_names:
                seen_names.add(name_key)
                dean['raw_line'] = line
                deans.append(dean)
    
    logger.info(f"Extracted {len(deans)} deans from text")
    
    return deans


def _parse_dean_line(line: str) -> Dict[str, str]:
    """
    Parse a single line to extract dean information.
    
    Handles multiple formats:
    - "Dr. ERIC A. MATRIANO (College of Business & Accountancy)"
    - "DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd"
    - "Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)"
    
    Args:
        line: Single line of text
    
    Returns:
        Dict with full_name, title, college, or None if not a valid dean entry
    """
    # Extract title
    title_pattern = r'^((?:Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)(?:\s+(?:Engr\.|Dr\.))?)\s+'
    title_match = re.match(title_pattern, line, re.IGNORECASE)
    
    if not title_match:
        return None
    
    title = title_match.group(1)
    remaining = line[title_match.end():]
    
    # Find where the name ends by looking for delimiters
    # Delimiters: "(", "Dean", "—", "-"
    name_end_patterns = [
        r'\(',  # Opening parenthesis
        r'\s+Dean[,\s]',  # "Dean," or "Dean "
        r'\s+[-—]\s+',  # Hyphen or em-dash with spaces
    ]
    
    # Find the earliest delimiter
    name_end_pos = len(remaining)
    for pattern in name_end_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            name_end_pos = min(name_end_pos, match.start())
    
    # Extract name portion (everything before delimiter)
    name = remaining[:name_end_pos].strip()
    remaining = remaining[name_end_pos:].strip()
    
    # Validate name
    if not name or len(name) < 2:
        return None
    
    # Normalize title casing
    title_normalized = _normalize_title(title)
    
    # Combine title + name
    full_name = f"{title_normalized} {name}"
    
    # Normalize name casing (Title Case)
    full_name = _normalize_name_casing(full_name)
    
    # Extract college info from remaining text
    college = _parse_college_info(remaining)
    
    return {
        'full_name': full_name,
        'title': title_normalized,
        'college': college
    }


def _normalize_title(title: str) -> str:
    """
    Normalize title casing.
    
    Examples:
        "DR." → "Dr."
        "ENGR." → "Engr."
        "dr. engr." → "Dr. Engr."
    """
    title_map = {
        'dr.': 'Dr.',
        'engr.': 'Engr.',
        'arch.': 'Arch.',
        'prof.': 'Prof.',
        'mr.': 'Mr.',
        'ms.': 'Ms.',
        'mrs.': 'Mrs.'
    }
    
    parts = title.lower().split()
    normalized_parts = [title_map.get(part, part.capitalize()) for part in parts]
    return ' '.join(normalized_parts)


def _normalize_name_casing(full_name: str) -> str:
    """
    Normalize name casing to Title Case.
    
    Examples:
        "Dr. ERIC A. MATRIANO" → "Dr. Eric A. Matriano"
        "ENGR. NOEL H. YAP" → "Engr. Noel H. Yap"
    
    Preserves:
        - Initials (single letter + period)
        - Title prefixes (Dr., Engr., etc.)
    """
    words = full_name.split()
    normalized = []
    
    for word in words:
        # Keep titles as-is (already normalized)
        if word in ['Dr.', 'Engr.', 'Arch.', 'Prof.', 'Mr.', 'Ms.', 'Mrs.']:
            normalized.append(word)
        # Keep single-letter initials as-is
        elif len(word) <= 2 and word.endswith('.'):
            normalized.append(word.upper())
        # Title case for names
        else:
            normalized.append(word.capitalize())
    
    return ' '.join(normalized)


def _parse_college_info(info: str) -> str:
    """
    Extract clean college name from remaining line text.
    
    Examples:
        "(College of Business & Accountancy)" → "College of Business & Accountancy"
        "Dean, CASEd" → "CASEd"
        "Dean, College of Nursing & Asst. SAO Director" → "College of Nursing"
        "(College of Computer Studies)" → "College of Computer Studies"
    
    Args:
        info: Remaining text after name
    
    Returns:
        Clean college name, or empty string if not found
    """
    if not info:
        return ""
    
    # Remove "Dean," or "Dean" prefix
    info = re.sub(r'^(?:Dean,?\s*|[-—]\s*Dean,?\s*)', '', info, flags=re.IGNORECASE).strip()
    
    # Remove parentheses
    info = re.sub(r'[()]', '', info)
    
    # Extract "College of X" or "School of X" pattern
    college_match = re.match(r'((?:College|School)\s+of\s+[A-Za-z& ]+)', info, re.IGNORECASE)
    if college_match:
        college = college_match.group(1).strip()
        # Remove trailing fluff like "& Asst" or "& Asst."
        college = re.sub(r'\s*&\s*Asst\.?.*$', '', college)
        return college.strip()
    
    # If no "College of", extract department abbreviation or first part
    # Example: "CASEd" or "College of Nursing"
    parts = re.split(r'[,&]', info)
    if parts:
        college = parts[0].strip()
        # Remove trailing junk like "Asst. SAO Director"
        college = re.sub(r'\s+(?:Asst\.|Director|Dean).*$', '', college, flags=re.IGNORECASE)
        return college.strip()
    
    return ""


def format_dean_list(deans: List[Dict[str, str]]) -> str:
    """
    Format extracted deans into canonical response string.
    
    Output format:
        The deans are:
        
        1. Dr. Christine Gil O. Almazan — Dean, CASEd
        2. Dr. Leilani E. Capili — Dean, College of Nursing
        ...
    
    Args:
        deans: List of dean dicts from extract_deans_from_text()
    
    Returns:
        Formatted string ready for user display
    """
    if not deans:
        return "No deans found in the retrieved information."
    
    lines = ["The deans are:\n"]
    
    for i, dean in enumerate(deans, 1):
        full_name = dean['full_name']
        college = dean.get('college', '')
        
        if college:
            line = f"{i}. {full_name} — Dean, {college}"
        else:
            line = f"{i}. {full_name} — Dean"
        
        lines.append(line)
    
    return '\n'.join(lines)
