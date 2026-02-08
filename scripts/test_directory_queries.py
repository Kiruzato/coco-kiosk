"""
Directory Query Test Suite for CoCo Chatbot
============================================
Tests all types of directory queries including:
- Basic "where is" queries
- Alias-based queries
- "How do I get to" queries
- "Location of" queries
- Floor/building queries
- Disambiguation handling
- Edge cases

Output: Human-readable .txt report
"""
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000/chat"
ENTITIES_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\data\directory_entities.json")
REPORT_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\reports\directory_query_test_results.txt")

# Test results tracking
results = {
    "passed": 0,
    "failed": 0,
    "tests": []
}

# Report content
report_lines = []

def log(text=""):
    """Print and add to report."""
    print(text)
    report_lines.append(text)

def send_query(message: str, session_id: str = None) -> dict:
    """Send a query to the chatbot API."""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e), "answer": f"ERROR: {e}"}

def run_test(test_name: str, query: str, expected_mode: str = None):
    """Run a single test and log results."""
    log(f"\n{'─' * 70}")
    log(f"TEST: {test_name}")
    log(f"{'─' * 70}")
    log(f"QUERY: {query}")
    log("")

    response = send_query(query)

    # Extract response details
    answer = response.get("answer", "No answer received")
    mode = response.get("mode", "unknown")
    confidence = response.get("confidence_level", "N/A")
    session_id = response.get("session_id", "N/A")
    rejected = response.get("rejected", False)

    log(f"RESPONSE:")
    log(f"  Mode: {mode}")
    log(f"  Confidence: {confidence}")
    log(f"  Rejected: {rejected}")
    log(f"")
    log(f"  Answer:")

    # Format answer with proper indentation
    for line in answer.split('\n'):
        log(f"    {line}")

    # Determine pass/fail
    if expected_mode:
        passed = mode in expected_mode.split('|')
        status = "PASS" if passed else "FAIL"
        log(f"")
        log(f"STATUS: {status} (expected mode: {expected_mode}, got: {mode})")
    else:
        passed = True
        status = "OBSERVED"
        log(f"")
        log(f"STATUS: {status}")

    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1

    results["tests"].append({
        "name": test_name,
        "query": query,
        "answer": answer,
        "mode": mode,
        "passed": passed
    })

    return response

def run_followup_test(test_name: str, query: str, session_id: str):
    """Run a follow-up test with session context."""
    log(f"\n{'─' * 70}")
    log(f"FOLLOW-UP TEST: {test_name}")
    log(f"{'─' * 70}")
    log(f"QUERY: {query}")
    log(f"SESSION: {session_id[:20]}...")
    log("")

    response = send_query(query, session_id)

    answer = response.get("answer", "No answer received")
    mode = response.get("mode", "unknown")
    confidence = response.get("confidence_level", "N/A")

    log(f"RESPONSE:")
    log(f"  Mode: {mode}")
    log(f"  Confidence: {confidence}")
    log(f"")
    log(f"  Answer:")
    for line in answer.split('\n'):
        log(f"    {line}")

    log(f"")
    log(f"STATUS: OBSERVED")

    results["passed"] += 1
    results["tests"].append({
        "name": test_name,
        "query": query,
        "answer": answer,
        "mode": mode,
        "passed": True
    })

    return response

def load_entities():
    """Load directory entities for dynamic test generation."""
    if not ENTITIES_PATH.exists():
        return []
    with open(ENTITIES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [e for e in data.get('entities', []) if e.get('status') == 'active']

def run_tests():
    """Run all directory query tests."""
    log("=" * 70)
    log("DIRECTORY QUERY TEST SUITE - CoCo Chatbot")
    log("=" * 70)
    log(f"API URL: {API_URL}")
    log(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load entities for dynamic tests
    entities = load_entities()
    log(f"Directory Entities Loaded: {len(entities)}")

    if len(entities) == 0:
        log("")
        log("WARNING: No directory entities found!")
        log("Upload directory entities first for comprehensive testing.")

    # =========================================================================
    # SECTION 1: Query Pattern Recognition
    # =========================================================================
    log("\n")
    log("=" * 70)
    log("SECTION 1: QUERY PATTERN RECOGNITION")
    log("=" * 70)
    log("Testing if the system recognizes various directory query patterns.")

    pattern_tests = [
        ("Where is pattern", "Where is the library?"),
        ("How do I get to pattern", "How do I get to the gym?"),
        ("Location of pattern", "Location of the cafeteria"),
        ("Find pattern", "Find the registrar office"),
        ("Looking for pattern", "I'm looking for the clinic"),
        ("Which floor pattern", "Which floor is the dean's office?"),
        ("What building pattern", "What building is the library in?"),
        ("Directions pattern", "Can you give me directions to the chapel?"),
    ]

    for test_name, query in pattern_tests:
        run_test(test_name, query, expected_mode="directory|clarification")

    # =========================================================================
    # SECTION 2: Canonical Name Queries
    # =========================================================================
    if entities:
        log("\n")
        log("=" * 70)
        log("SECTION 2: CANONICAL NAME QUERIES")
        log("=" * 70)
        log("Testing queries using official entity names.")

        for entity in entities[:5]:
            name = entity.get('canonical_name', '')
            building = entity.get('building', 'N/A')
            floor = entity.get('floor', 'N/A')
            room = entity.get('room', 'N/A')

            log(f"\n  Entity: {name}")
            log(f"  Expected Location: {building}, {floor}, Room {room}")

            run_test(f"Canonical: {name}", f"Where is {name}?", expected_mode="directory|clarification")

    # =========================================================================
    # SECTION 3: Alias-Based Queries
    # =========================================================================
    if entities:
        log("\n")
        log("=" * 70)
        log("SECTION 3: ALIAS-BASED QUERIES")
        log("=" * 70)
        log("Testing queries using entity aliases (alternative names).")

        entities_with_aliases = [e for e in entities if e.get('aliases')]

        for entity in entities_with_aliases[:5]:
            name = entity.get('canonical_name', '')
            aliases = entity.get('aliases', [])

            # Handle aliases as string or list
            if isinstance(aliases, str):
                alias_list = [a.strip() for a in aliases.split(',')]
            else:
                alias_list = aliases

            if not alias_list or not alias_list[0]:
                continue

            alias = alias_list[0].strip()

            log(f"\n  Canonical Name: {name}")
            log(f"  Testing Alias: {alias}")
            log(f"  All Aliases: {', '.join(alias_list)}")

            run_test(f"Alias: '{alias}'", f"Where is the {alias}?", expected_mode="directory|clarification")

    # =========================================================================
    # SECTION 4: Different Query Phrasings
    # =========================================================================
    if entities:
        log("\n")
        log("=" * 70)
        log("SECTION 4: DIFFERENT QUERY PHRASINGS")
        log("=" * 70)
        log("Testing the same location with different question styles.")

        entity = entities[0]
        name = entity.get('canonical_name', '')

        phrasings = [
            f"Where is {name}?",
            f"Where can I find {name}?",
            f"How do I get to {name}?",
            f"I need to go to {name}",
            f"Location of {name}",
            f"Can you tell me where {name} is?",
        ]

        for i, query in enumerate(phrasings, 1):
            run_test(f"Phrasing {i}: {name}", query, expected_mode="directory|clarification")

    # =========================================================================
    # SECTION 5: Follow-up Queries
    # =========================================================================
    if entities:
        log("\n")
        log("=" * 70)
        log("SECTION 5: FOLLOW-UP QUERIES (CONTEXT)")
        log("=" * 70)
        log("Testing context-aware follow-up questions.")

        entity = entities[0]
        name = entity.get('canonical_name', '')

        log(f"\n  Initial query about: {name}")
        initial_response = run_test("Initial Query", f"Where is {name}?")
        session_id = initial_response.get("session_id", "")

        if session_id:
            followups = [
                "What floor is it on?",
                "What building?",
                "Are there any landmarks nearby?",
                "What's the room number?",
            ]

            for followup in followups:
                run_followup_test(f"Follow-up", followup, session_id)

    # =========================================================================
    # SECTION 6: Building Queries
    # =========================================================================
    if entities:
        log("\n")
        log("=" * 70)
        log("SECTION 6: BUILDING-BASED QUERIES")
        log("=" * 70)
        log("Testing queries about buildings.")

        buildings = list(set(e.get('building', '') for e in entities if e.get('building')))[:3]

        for building in buildings:
            run_test(f"Building: {building}", f"Where is {building}?")

    # =========================================================================
    # SECTION 7: Edge Cases
    # =========================================================================
    log("\n")
    log("=" * 70)
    log("SECTION 7: EDGE CASES")
    log("=" * 70)
    log("Testing edge cases and unusual inputs.")

    edge_cases = [
        ("Non-existent location", "Where is the swimming pool?"),
        ("Typo in query", "Where is the libary?"),
        ("All caps", "WHERE IS THE LIBRARY?"),
        ("All lowercase", "where is the library"),
        ("Very short query", "library location"),
        ("Vague query", "Where do I pay?"),
        ("Multiple locations", "Where are the restrooms?"),
    ]

    for test_name, query in edge_cases:
        run_test(test_name, query)

    # =========================================================================
    # Summary
    # =========================================================================
    log("\n")
    log("=" * 70)
    log("TEST SUMMARY")
    log("=" * 70)
    log(f"Total Tests: {results['passed'] + results['failed']}")
    log(f"Passed: {results['passed']}")
    log(f"Failed: {results['failed']}")
    log("")

    if results['failed'] > 0:
        log("FAILED TESTS:")
        for test in results['tests']:
            if not test['passed']:
                log(f"  - {test['name']}")
                log(f"    Query: {test['query']}")
                log(f"    Mode: {test['mode']}")
        log("")

    log(f"Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    # Save report
    REPORT_PATH.parent.mkdir(exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"\nReport saved to: {REPORT_PATH}")

    return results['failed'] == 0

if __name__ == "__main__":
    import sys

    # Check if server is running
    try:
        requests.get("http://localhost:8000/", timeout=5)
    except:
        print("ERROR: Server not running. Start the server first:")
        print("  python campus_rag_chatbot/app.py")
        sys.exit(1)

    success = run_tests()
    sys.exit(0 if success else 1)
