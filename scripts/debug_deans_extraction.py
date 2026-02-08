"""Debug script to trace dean extraction step by step."""

import sys
sys.path.insert(0, r'C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot')

import re

# Sample context from the server (what the extractor actually receives)
# NOTE: Server context is all lowercase!
sample_context = """the school motto we are christs not our own. attributes of a columban college graduate christian character

dr. christine gil o. almazan dean, cased dr. leilani e. capili dean, college of nursing & asst. sao director dr. eric a. matriano (college of business & accountancy) engr. noel h. yap (college of computer studies) arch. corazon z. gonzales (college of architecture) dr. engr. vivian e. gutierrez (college of engineering) directors & research proponents ms. frances aletheia c. meneses ms. jan
"""

def debug_extraction(text):
    """Trace through extraction step by step."""
    print("="*80)
    print("DEAN EXTRACTION DEBUG")
    print("="*80)

    print("\n[STEP 1] Original text:")
    print(repr(text[:200]) + "...")

    # Remove chunk markers
    text = re.sub(r'\[chunk[^\]]*\]', ' ', text)
    print("\n[STEP 2] After removing chunk markers:")
    print(repr(text[:200]) + "...")

    # Split on newlines first
    lines = text.split('\n')
    print(f"\n[STEP 3] After newline split: {len(lines)} lines")
    for i, line in enumerate(lines):
        if line.strip():
            print(f"  Line {i}: {repr(line[:100])}")

    # Check for lines with titles
    lines_with_titles = [l for l in lines if re.search(r'(Dr\.|Engr\.|Arch\.)', l, re.IGNORECASE)]
    print(f"\n[STEP 4] Lines with titles: {len(lines_with_titles)}")

    # If few lines with titles, do title split
    if len(lines_with_titles) <= 2:
        print("\n[STEP 5] Doing title pattern split...")
        title_pattern = r'(?=(?:dr\.|engr\.|arch\.|prof\.|mr\.|ms\.|mrs\.)\s+[a-z])'
        lines = re.split(title_pattern, text, flags=re.IGNORECASE)
        print(f"  After title split: {len(lines)} segments")
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                print(f"  Segment {i}: {repr(line[:80])}")

    # Now process each line
    print("\n[STEP 6] Processing each line...")
    deans = []
    seen_names = set()

    for idx, line in enumerate(lines):
        line = line.strip()

        # Skip empty/short
        if not line or len(line) < 10:
            print(f"  [{idx}] SKIP: too short ({len(line)} chars)")
            continue

        # Skip section headers
        if line.upper() == line and len(line) < 30 and line.replace(' ', '').isalpha():
            print(f"  [{idx}] SKIP: section header")
            continue

        # Check for title
        title_match = re.search(r'(Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)', line, re.IGNORECASE)
        if not title_match:
            print(f"  [{idx}] SKIP: no title found in '{line[:50]}'")
            continue

        print(f"  [{idx}] TITLE FOUND: '{title_match.group(1)}' in '{line[:60]}'")

        # Try to parse the line
        dean = parse_dean_line_debug(line, idx)

        if dean:
            # Check dean entry filter
            line_lower = line.lower()
            is_dean_entry = (
                'dean' in line_lower or
                'college of' in line_lower or
                '(college' in line_lower
            )
            print(f"    -> Dean entry check: dean={('dean' in line_lower)}, college of={('college of' in line_lower)}, (college={('(college' in line_lower)}")

            if not is_dean_entry:
                print(f"    -> FILTERED: not a dean entry")
                continue

            # Dedup check
            name_key = dean['full_name'].lower()
            if name_key in seen_names:
                print(f"    -> FILTERED: duplicate name")
                continue

            seen_names.add(name_key)
            deans.append(dean)
            print(f"    -> ADDED: {dean['full_name']}")
        else:
            print(f"    -> PARSE FAILED")

    print(f"\n[RESULT] Extracted {len(deans)} deans:")
    for i, d in enumerate(deans, 1):
        print(f"  {i}. {d['full_name']} ({d.get('college', 'N/A')})")

    return deans


def parse_dean_line_debug(line, idx):
    """Parse with debug output."""
    # Title pattern
    title_pattern = r'^((?:Dr\.|Engr\.|Arch\.|Prof\.|Mr\.|Ms\.|Mrs\.)(?:\s+(?:Engr\.|Dr\.))?)\s+'
    title_match = re.match(title_pattern, line, re.IGNORECASE)

    if not title_match:
        print(f"    -> Title pattern did not match at start of line")
        print(f"       Pattern: {title_pattern}")
        print(f"       Line starts with: {repr(line[:20])}")
        return None

    title = title_match.group(1)
    remaining = line[title_match.end():]
    print(f"    -> Matched title: '{title}', remaining: '{remaining[:50]}'")

    # Find name end
    name_end_patterns = [
        r'\(',
        r'\s+Dean[,\s]',
        r'\s+[-—]\s+',
    ]

    name_end_pos = len(remaining)
    for pattern in name_end_patterns:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            name_end_pos = min(name_end_pos, match.start())
            print(f"    -> Name end pattern '{pattern}' matched at pos {match.start()}")

    name = remaining[:name_end_pos].strip()
    remaining = remaining[name_end_pos:].strip()
    print(f"    -> Name: '{name}', after name: '{remaining[:40]}'")

    # Truncate at next title
    next_title = re.search(r'\b(?:dr\.|engr\.|arch\.|prof\.|mr\.|ms\.|mrs\.)\s+[a-z]', remaining, re.IGNORECASE)
    if next_title:
        remaining = remaining[:next_title.start()].strip()
        print(f"    -> Truncated at next title, remaining: '{remaining}'")

    if not name or len(name) < 2:
        print(f"    -> Name too short: '{name}'")
        return None

    # Normalize
    title_normalized = normalize_title(title)
    full_name = f"{title_normalized} {name}"
    full_name = normalize_name_casing(full_name)

    # Parse college
    college = parse_college_info(remaining)

    return {
        'full_name': full_name,
        'title': title_normalized,
        'college': college
    }


def normalize_title(title):
    title_map = {
        'dr.': 'Dr.', 'engr.': 'Engr.', 'arch.': 'Arch.',
        'prof.': 'Prof.', 'mr.': 'Mr.', 'ms.': 'Ms.', 'mrs.': 'Mrs.'
    }
    parts = title.lower().split()
    return ' '.join(title_map.get(p, p.capitalize()) for p in parts)


def normalize_name_casing(full_name):
    words = full_name.split()
    normalized = []
    for word in words:
        if word in ['Dr.', 'Engr.', 'Arch.', 'Prof.', 'Mr.', 'Ms.', 'Mrs.']:
            normalized.append(word)
        elif len(word) <= 2 and word.endswith('.'):
            normalized.append(word.upper())
        else:
            normalized.append(word.capitalize())
    return ' '.join(normalized)


def parse_college_info(info):
    if not info:
        return ""
    info = re.sub(r'^(?:Dean,?\s*|[-—]\s*Dean,?\s*)', '', info, flags=re.IGNORECASE).strip()
    info = re.sub(r'[()]', '', info)
    college_match = re.match(r'((?:College|School)\s+of\s+[A-Za-z& ]+)', info, re.IGNORECASE)
    if college_match:
        college = college_match.group(1).strip()
        college = re.sub(r'\s*&\s*Asst\.?.*$', '', college)
        return college.strip()
    parts = re.split(r'[,&]', info)
    if parts:
        college = parts[0].strip()
        college = re.sub(r'\s+(?:Asst\.|Director|Dean).*$', '', college, flags=re.IGNORECASE)
        return college.strip()
    return ""


if __name__ == "__main__":
    deans = debug_extraction(sample_context)
