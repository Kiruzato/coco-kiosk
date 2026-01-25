"""
Document-Only Acceptance Test Runner
=====================================
Reads questions from generated_questions.txt, sends them to the CoCo chatbot API,
and saves structured results for QA evaluation.

Usage:
    1. Start the app: cd campus_rag_chatbot && python app.py
    2. Run this script: python document_test_runner.py

Output:
    - document_test_results.json (structured results)
    - Console summary statistics
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
BASE_URL = "http://localhost:8000"
QUESTIONS_FILE = "generated_questions.txt"
RESULTS_FILE = "document_test_results.json"
DELAY_BETWEEN_REQUESTS = 0.5  # seconds


def load_questions(filepath: str) -> List[str]:
    """Load questions from file, stripping numbering and empty lines."""
    questions = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Remove numbering like "1. " or "42. "
            if line[0].isdigit():
                parts = line.split('. ', 1)
                if len(parts) == 2:
                    line = parts[1]
            if line and line.endswith('?'):
                questions.append(line)
    return questions


def send_query(message: str, session_id: Optional[str] = None) -> Dict:
    """Send a query to the /chat endpoint."""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "error": str(e),
            "session_id": session_id,
            "answer": f"ERROR: {e}",
            "sources": [],
            "confidence_level": "N/A",
            "confidence_score": 0,
            "rejected": True,
            "mode": "error",
            "timestamp": datetime.now().isoformat()
        }


def reset_session(session_id: str) -> bool:
    """Reset the session via POST /reset."""
    try:
        response = requests.post(
            f"{BASE_URL}/reset",
            json={"session_id": session_id},
            timeout=10
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def check_server() -> bool:
    """Check if the server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def run_tests():
    """Run all document tests and collect results."""
    print("=" * 60)
    print("DOCUMENT-ONLY ACCEPTANCE TEST RUNNER")
    print("=" * 60)
    print()

    # Check server
    print("Checking server status...")
    if not check_server():
        print("ERROR: Server not running at", BASE_URL)
        print("Start the app first: cd campus_rag_chatbot && python app.py")
        return

    print("Server is running.")
    print()

    # Load questions
    questions_path = Path(QUESTIONS_FILE)
    if not questions_path.exists():
        print(f"ERROR: Questions file not found: {QUESTIONS_FILE}")
        return

    questions = load_questions(QUESTIONS_FILE)
    print(f"Loaded {len(questions)} questions from {QUESTIONS_FILE}")
    print()

    # Run tests
    results = []
    session_id = None
    errors = 0

    print("Running tests...")
    print("-" * 60)

    for i, question in enumerate(questions, 1):
        # Progress indicator
        print(f"[{i}/{len(questions)}] {question[:50]}{'...' if len(question) > 50 else ''}")

        # Send query
        response = send_query(question, session_id)

        # Preserve session
        if "session_id" in response:
            session_id = response["session_id"]

        # Check for errors
        if "error" in response:
            errors += 1

        # Collect result
        result = {
            "query": question,
            "answer": response.get("answer", ""),
            "sources": response.get("sources", []),
            "confidence_level": response.get("confidence_level", "N/A"),
            "confidence_score": response.get("confidence_score", 0),
            "rejected": response.get("rejected", False),
            "mode": response.get("mode", "unknown"),
            "timestamp": response.get("timestamp", datetime.now().isoformat())
        }
        results.append(result)

        # Delay between requests
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print("-" * 60)
    print()

    # Reset session
    if session_id:
        print("Resetting session...")
        if reset_session(session_id):
            print("Session reset successfully.")
        else:
            print("Warning: Failed to reset session.")
        print()

    # Save results
    output = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "questions_file": QUESTIONS_FILE,
            "total_questions": len(questions),
            "base_url": BASE_URL
        },
        "results": results
    }

    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {RESULTS_FILE}")
    print()

    # Calculate statistics
    total = len(results)
    rejected_count = sum(1 for r in results if r["rejected"])
    citation_count = sum(1 for r in results if len(r["sources"]) > 0)

    confidence_dist = {"High": 0, "Medium": 0, "Low": 0, "N/A": 0}
    for r in results:
        level = r["confidence_level"]
        if level in confidence_dist:
            confidence_dist[level] += 1
        else:
            confidence_dist["N/A"] += 1

    mode_dist = {}
    for r in results:
        mode = r["mode"]
        mode_dist[mode] = mode_dist.get(mode, 0) + 1

    # Print summary
    print("=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    print()
    print(f"Total queries:        {total}")
    print(f"Rejection count:      {rejected_count} ({100*rejected_count/total:.1f}%)")
    print(f"Citation presence:    {citation_count} ({100*citation_count/total:.1f}%)")
    print(f"Errors:               {errors}")
    print()
    print("Confidence Distribution:")
    for level, count in confidence_dist.items():
        if count > 0:
            print(f"  {level}: {count} ({100*count/total:.1f}%)")
    print()
    print("Mode Distribution:")
    for mode, count in mode_dist.items():
        print(f"  {mode}: {count} ({100*count/total:.1f}%)")
    print()
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
