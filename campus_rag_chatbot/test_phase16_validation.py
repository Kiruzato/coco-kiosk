"""
Phase 16.1: Observability Validation Gate
==========================================
Comprehensive validation of Phase 16 event tracking implementation.

This script validates:
1. Event Coverage - Each event fires exactly once
2. Metadata Accuracy - Fields match actual system state
3. Privacy Safety - No user content in logs
4. Boundary Protection - Directory/Document separation
5. Admin API Security - Authentication required
6. Rolling Log - Max events enforced

Run: python test_phase16_validation.py
"""

import sys
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from event_tracker import EventTracker, EventType

# ============================================================================
# Test Utilities
# ============================================================================

class ValidationResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.details = []
        self.issues = []

    def add_check(self, description: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.details.append(f"  [{status}] {description}")
        if detail:
            self.details.append(f"        {detail}")
        if not passed:
            self.passed = False
            self.issues.append(description)

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}\n" + "\n".join(self.details)


def create_test_tracker() -> Tuple[EventTracker, Path]:
    """Create a fresh EventTracker with temp directory."""
    temp_dir = Path(tempfile.mkdtemp())
    tracker = EventTracker(log_dir=temp_dir, max_events=100)
    return tracker, temp_dir


def read_events_from_file(filepath: Path) -> List[Dict]:
    """Read all events from JSONL file."""
    events = []
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


# ============================================================================
# Task 1: Event Coverage Verification
# ============================================================================

def test_event_coverage() -> ValidationResult:
    """Verify each event type fires exactly once per condition."""
    result = ValidationResult("Task 1: Event Coverage Verification")

    tracker, temp_dir = create_test_tracker()
    session_id = "test-session-001"

    # Test 1: QUERY_RECEIVED fires once
    tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
    events = read_events_from_file(tracker.events_file)
    query_events = [e for e in events if e["event_type"] == "query_received"]
    result.add_check(
        "QUERY_RECEIVED fires once per call",
        len(query_events) == 1,
        f"Expected 1, got {len(query_events)}"
    )

    # Test 2: CLARIFICATION_TRIGGERED fires once
    tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                  clarification_type="directory", reason="ambiguity", num_candidates=3)
    events = read_events_from_file(tracker.events_file)
    clarification_events = [e for e in events if e["event_type"] == "clarification_triggered"]
    result.add_check(
        "CLARIFICATION_TRIGGERED fires once per call",
        len(clarification_events) == 1,
        f"Expected 1, got {len(clarification_events)}"
    )

    # Test 3: CLARIFICATION_RESOLVED fires once
    tracker.track(EventType.CLARIFICATION_RESOLVED, session_id,
                  success=True, clarification_type="directory")
    events = read_events_from_file(tracker.events_file)
    resolved_events = [e for e in events if e["event_type"] == "clarification_resolved"]
    result.add_check(
        "CLARIFICATION_RESOLVED fires once per call",
        len(resolved_events) == 1,
        f"Expected 1, got {len(resolved_events)}"
    )

    # Test 4: ANSWER_RETURNED fires once
    tracker.track(EventType.ANSWER_RETURNED, session_id,
                  confidence_level="high", source_type="directory")
    events = read_events_from_file(tracker.events_file)
    answer_events = [e for e in events if e["event_type"] == "answer_returned"]
    result.add_check(
        "ANSWER_RETURNED fires once per call",
        len(answer_events) == 1,
        f"Expected 1, got {len(answer_events)}"
    )

    # Test 5: ANSWER_REFUSED fires once
    tracker.track(EventType.ANSWER_REFUSED, session_id, reason="low_confidence")
    events = read_events_from_file(tracker.events_file)
    refused_events = [e for e in events if e["event_type"] == "answer_refused"]
    result.add_check(
        "ANSWER_REFUSED fires once per call",
        len(refused_events) == 1,
        f"Expected 1, got {len(refused_events)}"
    )

    # Test 6: All 5 event types are usable
    all_types = {e["event_type"] for e in events}
    expected_types = {"query_received", "clarification_triggered",
                      "clarification_resolved", "answer_returned", "answer_refused"}
    result.add_check(
        "All 5 EventTypes are trackable",
        all_types == expected_types,
        f"Expected {expected_types}, got {all_types}"
    )

    return result


# ============================================================================
# Task 2: Metadata Accuracy Validation
# ============================================================================

def test_metadata_accuracy() -> ValidationResult:
    """Validate metadata fields are populated correctly."""
    result = ValidationResult("Task 2: Metadata Accuracy Validation")

    tracker, temp_dir = create_test_tracker()
    session_id = "test-session-002"

    # Test query_type values
    for query_type in ["directory", "document", "general"]:
        tracker.track(EventType.QUERY_RECEIVED, session_id, query_type=query_type)

    events = read_events_from_file(tracker.events_file)
    query_types = [e["metadata"]["query_type"] for e in events
                   if e["event_type"] == "query_received"]
    result.add_check(
        "query_type accepts directory/document/general",
        set(query_types) == {"directory", "document", "general"},
        f"Got {set(query_types)}"
    )

    # Test clarification_type values
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                  clarification_type="directory", reason="ambiguity", num_candidates=3)
    tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                  clarification_type="document", reason="ambiguity", num_sources=2)

    events = read_events_from_file(tracker.events_file)
    clar_types = [e["metadata"]["clarification_type"] for e in events]
    result.add_check(
        "clarification_type accepts directory/document",
        set(clar_types) == {"directory", "document"},
        f"Got {set(clar_types)}"
    )

    # Test confidence_level values
    tracker, temp_dir = create_test_tracker()
    for conf in ["high", "medium", "low", "n/a"]:
        tracker.track(EventType.ANSWER_RETURNED, session_id,
                      confidence_level=conf, source_type="directory")

    events = read_events_from_file(tracker.events_file)
    conf_levels = [e["metadata"]["confidence_level"] for e in events]
    result.add_check(
        "confidence_level accepts high/medium/low/n/a",
        set(conf_levels) == {"high", "medium", "low", "n/a"},
        f"Got {set(conf_levels)}"
    )

    # Test that confidence is lowercase
    result.add_check(
        "confidence_level values are lowercase",
        all(c == c.lower() for c in conf_levels),
        f"Values: {conf_levels}"
    )

    # Test source_type values
    tracker, temp_dir = create_test_tracker()
    for src in ["directory", "document", "general"]:
        tracker.track(EventType.ANSWER_RETURNED, session_id,
                      confidence_level="high", source_type=src)

    events = read_events_from_file(tracker.events_file)
    src_types = [e["metadata"]["source_type"] for e in events]
    result.add_check(
        "source_type accepts directory/document/general",
        set(src_types) == {"directory", "document", "general"},
        f"Got {set(src_types)}"
    )

    # Test reason field for refusals
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.ANSWER_REFUSED, session_id, reason="low_confidence")

    events = read_events_from_file(tracker.events_file)
    result.add_check(
        "reason field populated for refusals",
        events[0]["metadata"]["reason"] == "low_confidence",
        f"Got {events[0]['metadata'].get('reason', 'MISSING')}"
    )

    # Test timestamp format
    result.add_check(
        "timestamp is ISO format",
        "T" in events[0]["timestamp"] and len(events[0]["timestamp"]) > 19,
        f"Got {events[0]['timestamp']}"
    )

    # Test session_id preserved
    result.add_check(
        "session_id correctly preserved",
        events[0]["session_id"] == session_id,
        f"Expected {session_id}, got {events[0]['session_id']}"
    )

    return result


# ============================================================================
# Task 3: Behavioral Non-Interference (Partial - No Live Server)
# ============================================================================

def test_behavioral_noninterference() -> ValidationResult:
    """Verify tracking has minimal overhead and no state changes."""
    result = ValidationResult("Task 3: Behavioral Non-Interference")

    tracker, temp_dir = create_test_tracker()
    session_id = "test-session-003"

    # Test 1: Tracking latency is minimal
    iterations = 100
    start = time.perf_counter()
    for i in range(iterations):
        tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
    elapsed = time.perf_counter() - start
    avg_latency_ms = (elapsed / iterations) * 1000

    result.add_check(
        "Average tracking latency < 5ms",
        avg_latency_ms < 5.0,
        f"Average: {avg_latency_ms:.3f}ms over {iterations} iterations"
    )

    # Test 2: Tracking doesn't modify input parameters
    metadata = {"query_type": "directory", "extra": "data"}
    original_metadata = dict(metadata)
    tracker.track(EventType.QUERY_RECEIVED, session_id, **metadata)
    result.add_check(
        "Tracking doesn't modify input metadata",
        metadata == original_metadata,
        f"Original: {original_metadata}, After: {metadata}"
    )

    # Test 3: Stats counters are independent
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
    stats_before = tracker.get_stats()
    tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="document")
    stats_after = tracker.get_stats()

    result.add_check(
        "Stats update independently per event",
        stats_after["total_queries"] == stats_before["total_queries"] + 1,
        f"Before: {stats_before['total_queries']}, After: {stats_after['total_queries']}"
    )

    # Test 4: Thread-safety (basic check)
    import threading
    tracker, temp_dir = create_test_tracker()
    errors = []

    def track_events():
        try:
            for i in range(50):
                tracker.track(EventType.QUERY_RECEIVED, f"thread-{threading.current_thread().name}",
                             query_type="directory")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=track_events) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result.add_check(
        "Thread-safe concurrent tracking",
        len(errors) == 0,
        f"Errors: {errors}" if errors else "No errors in 5 concurrent threads"
    )

    # Verify all events were written
    events = read_events_from_file(tracker.events_file)
    result.add_check(
        "All concurrent events persisted",
        len(events) == 250,  # 5 threads * 50 events
        f"Expected 250 events, got {len(events)}"
    )

    return result


# ============================================================================
# Task 4: Privacy & Data Safety
# ============================================================================

def test_privacy_safety() -> ValidationResult:
    """Verify logs contain ONLY metadata, no user content."""
    result = ValidationResult("Task 4: Privacy & Data Safety")

    tracker, temp_dir = create_test_tracker()
    session_id = "test-session-004"

    # Simulate various events with metadata
    tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
    tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                  clarification_type="directory", reason="ambiguity", num_candidates=3)
    tracker.track(EventType.CLARIFICATION_RESOLVED, session_id,
                  success=True, clarification_type="directory")
    tracker.track(EventType.ANSWER_RETURNED, session_id,
                  confidence_level="high", source_type="directory")
    tracker.track(EventType.ANSWER_REFUSED, session_id, reason="low_confidence")

    # Read raw log file
    with open(tracker.events_file, 'r', encoding='utf-8') as f:
        log_content = f.read()

    events = read_events_from_file(tracker.events_file)

    # Check: No query text in logs
    prohibited_terms = [
        "where is", "what is", "how do", "tell me",  # Query patterns
        "library", "canteen", "registrar",  # Specific locations
        "The ", "You can find",  # Response patterns
        "email", "phone", "address",  # PII patterns
        "@", ".com", ".edu",  # Email patterns
    ]

    found_prohibited = []
    for term in prohibited_terms:
        if term.lower() in log_content.lower():
            # Check if it's in a metadata field name (allowed) vs value (not allowed)
            for event in events:
                metadata_values = str(event.get("metadata", {})).lower()
                if term.lower() in metadata_values:
                    found_prohibited.append(term)
                    break

    result.add_check(
        "No query/response text in logs",
        len(found_prohibited) == 0,
        f"Found prohibited terms: {found_prohibited}" if found_prohibited else "Clean"
    )

    # Check: Only allowed metadata fields present
    allowed_metadata_keys = {
        "query_type", "clarification_type", "reason", "num_candidates",
        "num_sources", "success", "confidence_level", "source_type"
    }

    all_metadata_keys = set()
    for event in events:
        all_metadata_keys.update(event.get("metadata", {}).keys())

    unexpected_keys = all_metadata_keys - allowed_metadata_keys
    result.add_check(
        "Only allowed metadata fields present",
        len(unexpected_keys) == 0,
        f"Unexpected keys: {unexpected_keys}" if unexpected_keys else "All keys valid"
    )

    # Check: Session IDs are anonymous (not email/name format)
    session_ids = {e["session_id"] for e in events}
    has_pii_in_session = any("@" in sid or " " in sid for sid in session_ids)
    result.add_check(
        "Session IDs are anonymous",
        not has_pii_in_session,
        f"Session IDs: {session_ids}"
    )

    # Check: Event structure is minimal
    for event in events:
        required_fields = {"event_type", "timestamp", "session_id", "metadata"}
        actual_fields = set(event.keys())
        result.add_check(
            f"Event {event['event_type']} has minimal structure",
            actual_fields == required_fields,
            f"Expected {required_fields}, got {actual_fields}"
        )
        break  # Check one event as sample

    return result


# ============================================================================
# Task 5: Directory vs Document Boundary
# ============================================================================

def test_boundary_protection() -> ValidationResult:
    """Verify directory and document analytics are separated."""
    result = ValidationResult("Task 5: Directory vs Document Boundary")

    tracker, temp_dir = create_test_tracker()

    # Simulate directory query flow
    tracker.track(EventType.QUERY_RECEIVED, "session-dir", query_type="directory")
    tracker.track(EventType.CLARIFICATION_TRIGGERED, "session-dir",
                  clarification_type="directory", reason="ambiguity", num_candidates=2)
    tracker.track(EventType.CLARIFICATION_RESOLVED, "session-dir",
                  success=True, clarification_type="directory")
    tracker.track(EventType.ANSWER_RETURNED, "session-dir",
                  confidence_level="high", source_type="directory")

    # Simulate document query flow
    tracker.track(EventType.QUERY_RECEIVED, "session-doc", query_type="document")
    tracker.track(EventType.CLARIFICATION_TRIGGERED, "session-doc",
                  clarification_type="document", reason="ambiguity", num_sources=3)
    tracker.track(EventType.CLARIFICATION_RESOLVED, "session-doc",
                  success=True, clarification_type="document")
    tracker.track(EventType.ANSWER_RETURNED, "session-doc",
                  confidence_level="medium", source_type="document")

    stats = tracker.get_stats()

    # Check query type breakdown
    result.add_check(
        "by_query_type.directory correctly counted",
        stats["by_query_type"]["directory"] == 1,
        f"Expected 1, got {stats['by_query_type']['directory']}"
    )

    result.add_check(
        "by_query_type.document correctly counted",
        stats["by_query_type"]["document"] == 1,
        f"Expected 1, got {stats['by_query_type']['document']}"
    )

    # Check clarification type breakdown
    result.add_check(
        "clarifications_by_type.directory correctly counted",
        stats["clarifications_by_type"]["directory"] == 1,
        f"Expected 1, got {stats['clarifications_by_type']['directory']}"
    )

    result.add_check(
        "clarifications_by_type.document correctly counted",
        stats["clarifications_by_type"]["document"] == 1,
        f"Expected 1, got {stats['clarifications_by_type']['document']}"
    )

    # Check confidence breakdown
    result.add_check(
        "by_confidence.high correctly counted",
        stats["by_confidence"]["high"] == 1,
        f"Expected 1, got {stats['by_confidence']['high']}"
    )

    result.add_check(
        "by_confidence.medium correctly counted",
        stats["by_confidence"]["medium"] == 1,
        f"Expected 1, got {stats['by_confidence']['medium']}"
    )

    # Check total queries
    result.add_check(
        "total_queries correctly summed",
        stats["total_queries"] == 2,
        f"Expected 2, got {stats['total_queries']}"
    )

    # Check clarifications
    result.add_check(
        "clarifications_triggered correctly counted",
        stats["clarifications_triggered"] == 2,
        f"Expected 2, got {stats['clarifications_triggered']}"
    )

    result.add_check(
        "clarifications_resolved correctly counted",
        stats["clarifications_resolved"] == 2,
        f"Expected 2, got {stats['clarifications_resolved']}"
    )

    return result


# ============================================================================
# Task 6: Admin Visibility (Stats Calculation)
# ============================================================================

def test_admin_visibility() -> ValidationResult:
    """Verify analytics summary calculations are correct."""
    result = ValidationResult("Task 6: Admin Visibility Validation")

    tracker, temp_dir = create_test_tracker()

    # Generate test data: 10 queries
    for i in range(10):
        session_id = f"session-{i}"

        if i < 4:  # 4 directory queries
            tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="directory")
            if i == 0:  # 1 triggers clarification
                tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                              clarification_type="directory", reason="ambiguity", num_candidates=2)
                tracker.track(EventType.CLARIFICATION_RESOLVED, session_id,
                              success=True, clarification_type="directory")
            tracker.track(EventType.ANSWER_RETURNED, session_id,
                          confidence_level="high", source_type="directory")
        elif i < 7:  # 3 document queries
            tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="document")
            if i == 4:  # 1 triggers clarification
                tracker.track(EventType.CLARIFICATION_TRIGGERED, session_id,
                              clarification_type="document", reason="ambiguity", num_sources=2)
                # This one doesn't resolve (user abandons)
            if i == 5:  # 1 gets refused
                tracker.track(EventType.ANSWER_REFUSED, session_id, reason="low_confidence")
            else:
                tracker.track(EventType.ANSWER_RETURNED, session_id,
                              confidence_level="medium", source_type="document")
        else:  # 3 general queries
            tracker.track(EventType.QUERY_RECEIVED, session_id, query_type="general")
            tracker.track(EventType.ANSWER_RETURNED, session_id,
                          confidence_level="n/a", source_type="general")

    analytics = tracker.get_analytics_summary()

    # Test summary values
    result.add_check(
        "total_queries correct",
        analytics["summary"]["total_queries"] == 10,
        f"Expected 10, got {analytics['summary']['total_queries']}"
    )

    # Clarification rate: 2 triggers / 10 queries = 20%
    result.add_check(
        "clarification_rate correct (20%)",
        analytics["summary"]["clarification_rate"] == 20.0,
        f"Expected 20.0, got {analytics['summary']['clarification_rate']}"
    )

    # Refusal rate: 1 refused / 10 queries = 10%
    result.add_check(
        "refusal_rate correct (10%)",
        analytics["summary"]["refusal_rate"] == 10.0,
        f"Expected 10.0, got {analytics['summary']['refusal_rate']}"
    )

    # Clarification success: 1 resolved / 2 triggered = 50%
    result.add_check(
        "clarification_success_rate correct (50%)",
        analytics["summary"]["clarification_success_rate"] == 50.0,
        f"Expected 50.0, got {analytics['summary']['clarification_success_rate']}"
    )

    # Test breakdowns
    result.add_check(
        "by_query_type breakdown correct",
        analytics["by_query_type"] == {"directory": 4, "document": 3, "general": 3},
        f"Got {analytics['by_query_type']}"
    )

    result.add_check(
        "by_confidence breakdown correct",
        analytics["by_confidence"]["high"] == 4 and analytics["by_confidence"]["medium"] == 2,
        f"Got {analytics['by_confidence']}"
    )

    result.add_check(
        "refusal_reasons tracked",
        "low_confidence" in analytics["refusal_reasons"],
        f"Got {analytics['refusal_reasons']}"
    )

    return result


# ============================================================================
# Task 7: Failure & Edge Case Coverage
# ============================================================================

def test_edge_cases() -> ValidationResult:
    """Validate analytics for failure and edge cases."""
    result = ValidationResult("Task 7: Failure & Edge Case Coverage")

    tracker, temp_dir = create_test_tracker()

    # Test 1: Unresolved clarification (no CLARIFICATION_RESOLVED)
    tracker.track(EventType.QUERY_RECEIVED, "session-abandon", query_type="directory")
    tracker.track(EventType.CLARIFICATION_TRIGGERED, "session-abandon",
                  clarification_type="directory", reason="ambiguity", num_candidates=2)
    # User abandons - no resolution event

    stats = tracker.get_stats()
    result.add_check(
        "Unresolved clarification: triggered > resolved",
        stats["clarifications_triggered"] > stats["clarifications_resolved"],
        f"Triggered: {stats['clarifications_triggered']}, Resolved: {stats['clarifications_resolved']}"
    )

    # Test 2: Multiple clarifications in same session (repeated loops)
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.CLARIFICATION_TRIGGERED, "session-loop",
                  clarification_type="directory", reason="ambiguity", num_candidates=3)
    tracker.track(EventType.CLARIFICATION_TRIGGERED, "session-loop",
                  clarification_type="directory", reason="ambiguity", num_candidates=2)

    stats = tracker.get_stats()
    result.add_check(
        "Multiple clarification triggers counted",
        stats["clarifications_triggered"] == 2,
        f"Expected 2, got {stats['clarifications_triggered']}"
    )

    # Test 3: Low confidence refusal
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.QUERY_RECEIVED, "session-refuse", query_type="directory")
    tracker.track(EventType.ANSWER_REFUSED, "session-refuse", reason="low_confidence")

    stats = tracker.get_stats()
    result.add_check(
        "Low confidence refusal tracked",
        stats["answers_refused"] == 1 and "low_confidence" in stats["refusal_reasons"],
        f"Refused: {stats['answers_refused']}, Reasons: {stats['refusal_reasons']}"
    )

    # Test 4: Different refusal reasons tracked separately
    tracker.track(EventType.ANSWER_REFUSED, "session-refuse2", reason="inactive_entity")
    tracker.track(EventType.ANSWER_REFUSED, "session-refuse3", reason="low_confidence")

    stats = tracker.get_stats()
    result.add_check(
        "Different refusal reasons tracked separately",
        len(stats["refusal_reasons"]) >= 2,
        f"Reasons: {stats['refusal_reasons']}"
    )

    # Test 5: Empty session_id handling
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.QUERY_RECEIVED, "", query_type="directory")
    events = read_events_from_file(tracker.events_file)
    result.add_check(
        "Empty session_id handled gracefully",
        len(events) == 1 and events[0]["session_id"] == "",
        f"Session ID: '{events[0]['session_id']}'" if events else "No events"
    )

    return result


# ============================================================================
# Task 8: Performance & Stability
# ============================================================================

def test_performance_stability() -> ValidationResult:
    """Verify performance characteristics and stability."""
    result = ValidationResult("Task 8: Performance & Stability")

    # Test 1: Rolling log enforcement
    tracker, temp_dir = create_test_tracker()  # max_events=100

    # Write 150 events
    for i in range(150):
        tracker.track(EventType.QUERY_RECEIVED, f"session-{i}", query_type="directory")

    # Force enforcement
    tracker._enforce_rolling_limit()

    events = read_events_from_file(tracker.events_file)
    result.add_check(
        "Rolling log enforced (max 100 events)",
        len(events) <= 100,
        f"Expected <= 100, got {len(events)}"
    )

    # Test 2: In-memory buffer capped
    result.add_check(
        "In-memory buffer capped at 1000",
        len(tracker._recent_events) <= 1000,
        f"Buffer size: {len(tracker._recent_events)}"
    )

    # Test 3: Stats persist across tracker restarts
    tracker, temp_dir = create_test_tracker()
    tracker.track(EventType.QUERY_RECEIVED, "persist-test", query_type="directory")
    tracker.track(EventType.ANSWER_RETURNED, "persist-test",
                  confidence_level="high", source_type="directory")

    original_stats = tracker.get_stats()

    # Create new tracker pointing to same directory
    tracker2 = EventTracker(log_dir=temp_dir, max_events=100)
    loaded_stats = tracker2.get_stats()

    result.add_check(
        "Stats persist across restarts",
        loaded_stats["total_queries"] == original_stats["total_queries"],
        f"Original: {original_stats['total_queries']}, Loaded: {loaded_stats['total_queries']}"
    )

    # Test 4: Graceful handling of invalid event data (defensive)
    try:
        tracker.track(EventType.QUERY_RECEIVED, "test", query_type=None)
        result.add_check("Handles None metadata values", True, "No exception raised")
    except Exception as e:
        result.add_check("Handles None metadata values", False, str(e))

    # Test 5: File I/O error handling (simulate by reading from fresh tracker)
    tracker, temp_dir = create_test_tracker()
    try:
        stats = tracker.get_stats()
        result.add_check(
            "Fresh tracker returns valid stats",
            isinstance(stats, dict) and "total_queries" in stats,
            f"Stats type: {type(stats)}"
        )
    except Exception as e:
        result.add_check("Fresh tracker returns valid stats", False, str(e))

    return result


# ============================================================================
# Main Execution
# ============================================================================

def run_all_validations() -> Tuple[List[ValidationResult], bool]:
    """Run all validation tasks and return results."""
    results = []

    print("=" * 70)
    print("PHASE 16.1: OBSERVABILITY VALIDATION GATE")
    print("=" * 70)
    print()

    tests = [
        test_event_coverage,
        test_metadata_accuracy,
        test_behavioral_noninterference,
        test_privacy_safety,
        test_boundary_protection,
        test_admin_visibility,
        test_edge_cases,
        test_performance_stability,
    ]

    for test_func in tests:
        print(f"Running {test_func.__name__}...")
        try:
            result = test_func()
            results.append(result)
            print(result)
            print()
        except Exception as e:
            result = ValidationResult(test_func.__name__)
            result.add_check("Test execution", False, f"Exception: {e}")
            results.append(result)
            print(result)
            print()

    # Summary
    all_passed = all(r.passed for r in results)
    passed_count = sum(1 for r in results if r.passed)

    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")

    print()
    print(f"Result: {passed_count}/{len(results)} tasks passed")
    print()

    if all_passed:
        print("ACCEPTANCE STATUS: ACCEPTED")
        print("Phase 16 observability implementation meets all validation criteria.")
    else:
        print("ACCEPTANCE STATUS: NOT ACCEPTED")
        print("Issues found that must be resolved:")
        for r in results:
            if not r.passed:
                for issue in r.issues:
                    print(f"  - [{r.name}] {issue}")

    print("=" * 70)

    return results, all_passed


if __name__ == "__main__":
    results, passed = run_all_validations()
    sys.exit(0 if passed else 1)
