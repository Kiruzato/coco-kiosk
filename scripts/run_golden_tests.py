"""
Golden Test Regression Runner for CoCo RAG Chatbot
===================================================
Executes golden test cases and produces human-readable regression report.

Usage:
    python scripts/run_golden_tests.py
    python scripts/run_golden_tests.py --category synthetic_chunks
    python scripts/run_golden_tests.py --verbose

Output:
    reports/golden_test_results.txt
"""

import json
import requests
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Configuration
API_URL = "http://localhost:8000/chat"
TESTS_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\tests\golden_tests.json")
REPORT_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\reports\golden_test_results.txt")

# Results tracking
results = {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "tests": [],
    "by_category": {}
}

report_lines = []

def log(text="", also_print=True):
    """Add to report and optionally print."""
    report_lines.append(text)
    if also_print:
        print(text)

def send_query(message: str, session_id: str = None) -> Dict:
    """Send query to chatbot API."""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Connection failed - is the server running?"}
    except Exception as e:
        return {"error": str(e)}

def check_must_contain(answer: str, terms: List[str]) -> List[str]:
    """Check which required terms are missing from answer."""
    answer_lower = answer.lower()
    missing = []
    for term in terms:
        if term.lower() not in answer_lower:
            missing.append(term)
    return missing

def check_must_not_contain(answer: str, terms: List[str]) -> List[str]:
    """Check which forbidden terms appear in answer."""
    answer_lower = answer.lower()
    found = []
    for term in terms:
        if term.lower() in answer_lower:
            found.append(term)
    return found

def check_entity_count(answer: str, expected_count: int) -> bool:
    """Check if answer contains expected number of entities (by counting numbered items)."""
    import re
    # Count numbered list items (1. 2. 3. etc.)
    numbered = re.findall(r'^\d+\.', answer, re.MULTILINE)
    return len(numbered) >= expected_count

def evaluate_test(test_case: Dict, response: Dict, verbose: bool = False) -> Dict:
    """Evaluate a single test case against response."""
    result = {
        "id": test_case["id"],
        "name": test_case["name"],
        "category": test_case["category"],
        "query": test_case["query"],
        "passed": True,
        "failures": [],
        "response": {
            "mode": response.get("mode", "unknown"),
            "confidence": response.get("confidence_level", "N/A"),
            "grounding_mode": response.get("grounding_mode", "N/A"),
            "rejected": response.get("rejected", False),
            "answer": response.get("answer", "")
        }
    }

    expected = test_case.get("expected", {})
    answer = response.get("answer", "")

    # Check for API error
    if "error" in response:
        result["passed"] = False
        result["failures"].append(f"API Error: {response['error']}")
        return result

    # Check mode
    expected_modes = expected.get("mode", [])
    if expected_modes:
        actual_mode = response.get("mode", "unknown")
        if actual_mode not in expected_modes:
            result["passed"] = False
            result["failures"].append(f"Mode mismatch: expected {expected_modes}, got '{actual_mode}'")

    # Check must_contain
    must_contain = expected.get("must_contain", [])
    if must_contain:
        missing = check_must_contain(answer, must_contain)
        if missing:
            result["passed"] = False
            result["failures"].append(f"Missing required terms: {missing}")

    # Check must_not_contain
    must_not_contain = expected.get("must_not_contain", [])
    if must_not_contain:
        found = check_must_not_contain(answer, must_not_contain)
        if found:
            result["passed"] = False
            result["failures"].append(f"Found forbidden terms: {found}")

    # Check entity count
    entity_count = expected.get("entity_count")
    if entity_count:
        if not check_entity_count(answer, entity_count):
            result["passed"] = False
            result["failures"].append(f"Entity count mismatch: expected at least {entity_count}")

    # Check confidence level
    min_confidence = expected.get("min_confidence")
    if min_confidence:
        confidence_order = {"Low": 1, "Medium": 2, "High": 3}
        actual = response.get("confidence_level", "Low")
        if confidence_order.get(actual, 0) < confidence_order.get(min_confidence, 0):
            result["passed"] = False
            result["failures"].append(f"Confidence too low: expected >= {min_confidence}, got {actual}")

    # Check grounding mode
    expected_grounding = expected.get("grounding_mode")
    if expected_grounding:
        actual_grounding = response.get("grounding_mode", "unknown")
        if actual_grounding != expected_grounding:
            result["passed"] = False
            result["failures"].append(f"Grounding mode mismatch: expected '{expected_grounding}', got '{actual_grounding}'")

    # Check rejected flag
    if "rejected" in expected:
        if response.get("rejected", False) != expected["rejected"]:
            result["passed"] = False
            result["failures"].append(f"Rejected flag mismatch: expected {expected['rejected']}, got {response.get('rejected')}")

    # Check expected source chunks
    expected_chunks = expected.get("expected_source_chunks", [])
    if expected_chunks:
        actual_sources = response.get("sources", [])
        actual_chunk_ids = [s.get("chunk_id") for s in actual_sources]
        for expected_id in expected_chunks:
            if expected_id not in actual_chunk_ids:
                result["passed"] = False
                result["failures"].append(f"Expected chunk {expected_id} not in sources: {actual_chunk_ids}")

    return result

def run_tests(category_filter: str = None, verbose: bool = False):
    """Run all golden tests."""

    # Load test cases
    if not TESTS_PATH.exists():
        print(f"ERROR: Test file not found: {TESTS_PATH}")
        return False

    with open(TESTS_PATH, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    test_cases = test_data.get("test_cases", [])
    categories = test_data.get("categories", {})

    # Filter by category if specified
    if category_filter:
        test_cases = [t for t in test_cases if t.get("category") == category_filter]

    if not test_cases:
        print(f"No test cases found" + (f" for category '{category_filter}'" if category_filter else ""))
        return False

    # Header
    log("=" * 80)
    log("GOLDEN TEST REGRESSION REPORT - CoCo RAG Chatbot")
    log("=" * 80)
    log(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"API URL: {API_URL}")
    log(f"Total Test Cases: {len(test_cases)}")
    if category_filter:
        log(f"Category Filter: {category_filter}")
    log("")

    # Check server
    log("Checking server connectivity...")
    try:
        requests.get("http://localhost:8000/", timeout=5)
        log("Server is running.")
    except:
        log("ERROR: Server not running. Start with: python campus_rag_chatbot/app.py")
        return False

    log("")

    # Run tests by category
    current_category = None

    for test_case in test_cases:
        category = test_case.get("category", "unknown")

        # Print category header
        if category != current_category:
            current_category = category
            category_desc = categories.get(category, category)
            log("")
            log("-" * 80)
            log(f"CATEGORY: {category.upper()}")
            log(f"Description: {category_desc}")
            log("-" * 80)

            if category not in results["by_category"]:
                results["by_category"][category] = {"passed": 0, "failed": 0}

        # Run test
        test_id = test_case["id"]
        test_name = test_case["name"]
        query = test_case["query"]

        log("")
        log(f"[{test_id}] {test_name}")
        log(f"  Query: {query}")

        response = send_query(query)
        result = evaluate_test(test_case, response, verbose)

        results["tests"].append(result)

        if result["passed"]:
            results["passed"] += 1
            results["by_category"][category]["passed"] += 1
            log(f"  Status: PASS")
        else:
            results["failed"] += 1
            results["by_category"][category]["failed"] += 1
            log(f"  Status: FAIL")
            for failure in result["failures"]:
                log(f"    - {failure}")

        log(f"  Mode: {result['response']['mode']} | Confidence: {result['response']['confidence']} | Grounding: {result['response']['grounding_mode']}")

        if verbose:
            answer = result["response"]["answer"]
            preview = answer[:300] + "..." if len(answer) > 300 else answer
            log(f"  Answer: {preview}")

        # Show notes if present
        if "notes" in test_case:
            log(f"  Notes: {test_case['notes']}")

    # Summary
    log("")
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log("")

    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0

    log(f"Total Tests:  {total}")
    log(f"Passed:       {results['passed']}")
    log(f"Failed:       {results['failed']}")
    log(f"Pass Rate:    {pass_rate:.1f}%")
    log("")

    log("Results by Category:")
    log("-" * 40)
    for category, cat_results in results["by_category"].items():
        cat_total = cat_results["passed"] + cat_results["failed"]
        cat_rate = (cat_results["passed"] / cat_total * 100) if cat_total > 0 else 0
        status = "OK" if cat_results["failed"] == 0 else "FAIL"
        log(f"  {category:20} {cat_results['passed']:3}/{cat_total:3} ({cat_rate:5.1f}%) [{status}]")

    log("")

    # List failed tests
    if results["failed"] > 0:
        log("FAILED TESTS:")
        log("-" * 40)
        for test in results["tests"]:
            if not test["passed"]:
                log(f"  [{test['id']}] {test['name']}")
                log(f"      Query: {test['query']}")
                for failure in test["failures"]:
                    log(f"      Reason: {failure}")
        log("")

    log(f"Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 80)

    # Save report
    REPORT_PATH.parent.mkdir(exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"\nReport saved to: {REPORT_PATH}")

    # Also save JSON results
    json_path = REPORT_PATH.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": results["passed"],
                "failed": results["failed"],
                "pass_rate": pass_rate
            },
            "by_category": results["by_category"],
            "tests": results["tests"]
        }, f, indent=2)
    print(f"JSON results saved to: {json_path}")

    return results["failed"] == 0

def main():
    parser = argparse.ArgumentParser(description="Run CoCo golden tests")
    parser.add_argument("--category", "-c", help="Run only tests in this category")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full answers")
    parser.add_argument("--list", "-l", action="store_true", help="List available categories")

    args = parser.parse_args()

    if args.list:
        with open(TESTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("Available categories:")
        for cat, desc in data.get("categories", {}).items():
            count = len([t for t in data["test_cases"] if t.get("category") == cat])
            print(f"  {cat:20} ({count:2} tests) - {desc}")
        return

    success = run_tests(category_filter=args.category, verbose=args.verbose)
    exit(0 if success else 1)

if __name__ == "__main__":
    main()
