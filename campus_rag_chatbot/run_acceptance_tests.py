"""
Real-World Acceptance Tests for Phase 16
Tests against the 2022 Student Manual PDF (416 chunks)
"""

import requests
import json
import time
from typing import Dict, List

BASE_URL = "http://localhost:8000"
SESSION_ID = None

def chat(message: str) -> Dict:
    """Send a chat message and return the response."""
    global SESSION_ID

    payload = {"message": message}
    if SESSION_ID:
        payload["session_id"] = SESSION_ID

    response = requests.post(f"{BASE_URL}/chat", json=payload)
    result = response.json()

    # Store session ID for follow-up queries
    if "session_id" in result:
        SESSION_ID = result["session_id"]

    return result

def reset_session():
    """Reset the session for fresh testing."""
    global SESSION_ID
    if SESSION_ID:
        requests.post(f"{BASE_URL}/reset", json={"session_id": SESSION_ID})
    SESSION_ID = None

def format_result(query: str, result: Dict) -> Dict:
    """Format result for reporting."""
    return {
        "query": query,
        "answer_excerpt": result.get("answer", "")[:200] + "..." if len(result.get("answer", "")) > 200 else result.get("answer", ""),
        "confidence": result.get("confidence_level", "N/A"),
        "confidence_score": result.get("confidence_score", "N/A"),
        "rejected": result.get("rejected", False),
        "mode": result.get("mode", "N/A"),
        "has_sources": len(result.get("sources", [])) > 0,
        "num_sources": len(result.get("sources", [])),
        "clarification_needed": "clarification" in result.get("answer", "").lower() or "which" in result.get("answer", "").lower()[:100],
    }

def run_tests():
    """Run all acceptance tests."""
    results = []

    print("=" * 70)
    print("REAL-WORLD ACCEPTANCE TESTS - 2022 Student Manual")
    print("=" * 70)
    print()

    # =========================================================================
    # TEST 1: Broad document questions
    # =========================================================================
    print("TEST 1: Broad Document Questions")
    print("-" * 40)

    reset_session()

    queries_broad = [
        "What is this student manual about?",
        "What are the main policies covered in the manual?",
        "What services does the college offer to students?",
    ]

    for q in queries_broad:
        result = chat(q)
        formatted = format_result(q, result)
        results.append({"category": "Broad", **formatted})
        print(f"Q: {q}")
        print(f"   Confidence: {formatted['confidence']} | Rejected: {formatted['rejected']} | Mode: {formatted['mode']}")
        print()

    # =========================================================================
    # TEST 2: Specific questions
    # =========================================================================
    print("\nTEST 2: Specific Questions")
    print("-" * 40)

    reset_session()

    queries_specific = [
        "What is the grading system used?",
        "What are the requirements for graduation?",
        "What is the dress code policy?",
        "What are the library rules?",
    ]

    for q in queries_specific:
        result = chat(q)
        formatted = format_result(q, result)
        results.append({"category": "Specific", **formatted})
        print(f"Q: {q}")
        print(f"   Confidence: {formatted['confidence']} | Rejected: {formatted['rejected']} | Mode: {formatted['mode']}")
        print()

    # =========================================================================
    # TEST 3: Ambiguous questions
    # =========================================================================
    print("\nTEST 3: Ambiguous Questions")
    print("-" * 40)

    reset_session()

    queries_ambiguous = [
        "What are the rules?",
        "Tell me about the fees",
        "What happens if I'm late?",
    ]

    for q in queries_ambiguous:
        result = chat(q)
        formatted = format_result(q, result)
        results.append({"category": "Ambiguous", **formatted})
        print(f"Q: {q}")
        print(f"   Confidence: {formatted['confidence']} | Rejected: {formatted['rejected']} | Clarification: {formatted['clarification_needed']}")
        print()

    # =========================================================================
    # TEST 4: Follow-up questions (memory test)
    # =========================================================================
    print("\nTEST 4: Follow-up Questions (Memory Test)")
    print("-" * 40)

    reset_session()

    # Initial question
    result1 = chat("What are the academic requirements?")
    formatted1 = format_result("What are the academic requirements?", result1)
    results.append({"category": "Memory-Initial", **formatted1})
    print(f"Q1: What are the academic requirements?")
    print(f"    Confidence: {formatted1['confidence']}")

    # Follow-up
    result2 = chat("Can you explain more about that?")
    formatted2 = format_result("Can you explain more about that?", result2)
    results.append({"category": "Memory-Followup", **formatted2})
    print(f"Q2: Can you explain more about that?")
    print(f"    Confidence: {formatted2['confidence']} | Uses context: {not formatted2['rejected']}")

    # Another follow-up
    result3 = chat("What about the grading?")
    formatted3 = format_result("What about the grading?", result3)
    results.append({"category": "Memory-Followup", **formatted3})
    print(f"Q3: What about the grading?")
    print(f"    Confidence: {formatted3['confidence']}")
    print()

    # =========================================================================
    # TEST 5: Out-of-scope questions
    # =========================================================================
    print("\nTEST 5: Out-of-Scope Questions")
    print("-" * 40)

    reset_session()

    queries_outofscope = [
        "What is the weather today?",
        "Who is the president of the United States?",
        "How do I cook pasta?",
    ]

    for q in queries_outofscope:
        result = chat(q)
        formatted = format_result(q, result)
        results.append({"category": "Out-of-Scope", **formatted})
        print(f"Q: {q}")
        print(f"   Rejected: {formatted['rejected']} | Mode: {formatted['mode']}")
        print()

    # =========================================================================
    # TEST 6: Directory questions (boundary test)
    # =========================================================================
    print("\nTEST 6: Directory Questions (Boundary Test)")
    print("-" * 40)

    reset_session()

    queries_directory = [
        "Where is the registrar's office?",
        "Where is the library?",
        "Where can I find the canteen?",
    ]

    for q in queries_directory:
        result = chat(q)
        formatted = format_result(q, result)
        results.append({"category": "Directory", **formatted})
        print(f"Q: {q}")
        print(f"   Mode: {formatted['mode']} | Confidence: {formatted['confidence']} | Rejected: {formatted['rejected']}")
        print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Count results by category
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "rejected": 0, "high_conf": 0}
        categories[cat]["total"] += 1
        if r["rejected"]:
            categories[cat]["rejected"] += 1
        if r["confidence"] == "High":
            categories[cat]["high_conf"] += 1

    print("\nResults by Category:")
    for cat, stats in categories.items():
        print(f"  {cat}: {stats['total']} queries, {stats['rejected']} rejected, {stats['high_conf']} high confidence")

    # Check for issues
    issues = []

    # Check if directory queries used directory mode
    dir_results = [r for r in results if r["category"] == "Directory"]
    dir_wrong_mode = [r for r in dir_results if r["mode"] != "directory"]
    if dir_wrong_mode:
        issues.append(f"Directory queries used wrong mode: {len(dir_wrong_mode)}")

    # Check if out-of-scope were properly handled
    oos_results = [r for r in results if r["category"] == "Out-of-Scope"]
    oos_accepted = [r for r in oos_results if not r["rejected"] and r["mode"] != "general"]
    if oos_accepted:
        issues.append(f"Out-of-scope queries incorrectly accepted: {len(oos_accepted)}")

    # Check memory follow-ups
    memory_results = [r for r in results if "Memory" in r["category"]]
    memory_rejected = [r for r in memory_results if r["rejected"]]
    if len(memory_rejected) > 1:
        issues.append(f"Too many memory follow-ups rejected: {len(memory_rejected)}")

    print("\n" + "-" * 40)
    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nFINAL ASSESSMENT: ISSUES FOUND")
    else:
        print("No critical issues found.")
        print("\nFINAL ASSESSMENT: PASS")

    print("=" * 70)

    return results, issues

if __name__ == "__main__":
    results, issues = run_tests()
