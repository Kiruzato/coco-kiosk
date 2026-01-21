"""
Phase 16: Structured Event Tracking
====================================
Privacy-safe, metadata-only event logging for observability.

Tracks:
- Query types (directory/document/general)
- Clarification triggers and resolutions
- Answer confidence levels
- Refusal reasons

Does NOT log:
- Raw user queries
- Full AI responses
- Personally identifiable information
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from collections import deque

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Structured event types for observability."""
    QUERY_RECEIVED = "query_received"
    CLARIFICATION_TRIGGERED = "clarification_triggered"
    CLARIFICATION_RESOLVED = "clarification_resolved"
    ANSWER_RETURNED = "answer_returned"
    ANSWER_REFUSED = "answer_refused"


@dataclass
class Event:
    """A single tracked event."""
    event_type: str
    timestamp: str
    session_id: str
    metadata: Dict[str, Any]


class EventTracker:
    """
    Tracks structured events for observability.

    Features:
    - Rolling log with max size (prevents unbounded growth)
    - In-memory stats for fast access
    - Thread-safe operations
    - Privacy-safe (metadata only)
    """

    def __init__(self, log_dir: Path, max_events: int = 10000):
        """
        Initialize the event tracker.

        Args:
            log_dir: Directory to store event logs
            max_events: Maximum events to retain in log file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.log_dir / "events.jsonl"
        self.max_events = max_events
        self._lock = threading.Lock()

        # In-memory rolling buffer for recent events
        self._recent_events: deque = deque(maxlen=1000)

        # Aggregated statistics
        self._stats = {
            "total_queries": 0,
            "by_query_type": {"directory": 0, "document": 0, "general": 0},
            "clarifications_triggered": 0,
            "clarifications_by_type": {"directory": 0, "document": 0},
            "clarifications_resolved": 0,
            "clarifications_failed": 0,
            "answers_returned": 0,
            "answers_refused": 0,
            "by_confidence": {"high": 0, "medium": 0, "low": 0},
            "refusal_reasons": {},
        }

        # Load existing stats from log file
        self._load_existing_stats()
        logger.info(f"EventTracker initialized. Log file: {self.events_file}")

    def _load_existing_stats(self):
        """Load and aggregate stats from existing log file."""
        if not self.events_file.exists():
            return

        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event_data = json.loads(line)
                        event = Event(**event_data)
                        self._update_stats_from_event(event)
                        self._recent_events.append(event_data)
                    except (json.JSONDecodeError, TypeError):
                        continue
            logger.info(f"Loaded {self._stats['total_queries']} existing events")
        except Exception as e:
            logger.warning(f"Could not load existing events: {e}")

    def track(self, event_type: EventType, session_id: str, **metadata):
        """
        Track an event with metadata.

        Args:
            event_type: Type of event (from EventType enum)
            session_id: Anonymous session identifier
            **metadata: Additional metadata fields (query_type, reason, etc.)
        """
        event = Event(
            event_type=event_type.value,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            metadata=metadata
        )

        with self._lock:
            self._write_event(event)
            self._update_stats_from_event(event)
            self._recent_events.append(asdict(event))

    def _write_event(self, event: Event):
        """Write event to log file."""
        try:
            with open(self.events_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(event)) + '\n')

            # Enforce rolling limit periodically
            self._enforce_rolling_limit()
        except Exception as e:
            logger.error(f"Failed to write event: {e}")

    def _enforce_rolling_limit(self):
        """Keep log file under max_events limit."""
        try:
            if not self.events_file.exists():
                return

            # Check file size as proxy (avoid reading entire file every time)
            file_size = self.events_file.stat().st_size
            if file_size < self.max_events * 500:  # ~500 bytes per event estimate
                return

            with open(self.events_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if len(lines) > self.max_events:
                # Keep most recent events
                with open(self.events_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-self.max_events:])
                logger.info(f"Trimmed events log to {self.max_events} events")
        except Exception as e:
            logger.warning(f"Could not enforce rolling limit: {e}")

    def _update_stats_from_event(self, event: Event):
        """Update in-memory statistics from an event."""
        event_type = event.event_type
        metadata = event.metadata

        if event_type == EventType.QUERY_RECEIVED.value:
            self._stats["total_queries"] += 1
            query_type = metadata.get("query_type", "general")
            if query_type in self._stats["by_query_type"]:
                self._stats["by_query_type"][query_type] += 1

        elif event_type == EventType.CLARIFICATION_TRIGGERED.value:
            self._stats["clarifications_triggered"] += 1
            clar_type = metadata.get("clarification_type", "directory")
            if clar_type in self._stats["clarifications_by_type"]:
                self._stats["clarifications_by_type"][clar_type] += 1

        elif event_type == EventType.CLARIFICATION_RESOLVED.value:
            if metadata.get("success"):
                self._stats["clarifications_resolved"] += 1
            else:
                self._stats["clarifications_failed"] += 1

        elif event_type == EventType.ANSWER_RETURNED.value:
            self._stats["answers_returned"] += 1
            confidence = metadata.get("confidence_level", "medium").lower()
            if confidence in self._stats["by_confidence"]:
                self._stats["by_confidence"][confidence] += 1

        elif event_type == EventType.ANSWER_REFUSED.value:
            self._stats["answers_refused"] += 1
            reason = metadata.get("reason", "unknown")
            self._stats["refusal_reasons"][reason] = \
                self._stats["refusal_reasons"].get(reason, 0) + 1

    def get_stats(self) -> Dict:
        """
        Get current aggregated statistics.

        Returns:
            Dictionary with all tracked statistics
        """
        with self._lock:
            return dict(self._stats)

    def get_recent_events(self, limit: int = 100) -> List[Dict]:
        """
        Get recent events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events (most recent last)
        """
        with self._lock:
            events = list(self._recent_events)
            return events[-limit:]

    def get_analytics_summary(self) -> Dict:
        """
        Get computed analytics summary for admin dashboard.

        Returns:
            Dictionary with computed rates and breakdowns
        """
        with self._lock:
            stats = dict(self._stats)

        total = stats["total_queries"] or 1  # Avoid division by zero

        # Calculate rates
        clarification_rate = (stats["clarifications_triggered"] / total) * 100
        refusal_rate = (stats["answers_refused"] / total) * 100

        clarification_success = 0
        total_clarifications = stats["clarifications_triggered"]
        if total_clarifications > 0:
            clarification_success = (stats["clarifications_resolved"] / total_clarifications) * 100

        return {
            "summary": {
                "total_queries": stats["total_queries"],
                "clarification_rate": round(clarification_rate, 1),
                "refusal_rate": round(refusal_rate, 1),
                "clarification_success_rate": round(clarification_success, 1),
            },
            "by_query_type": stats["by_query_type"],
            "by_confidence": stats["by_confidence"],
            "clarifications_by_type": stats["clarifications_by_type"],
            "refusal_reasons": stats["refusal_reasons"],
            "recent_events_count": len(self._recent_events),
        }

    def reset_stats(self):
        """Reset all statistics (for testing or admin use)."""
        with self._lock:
            self._stats = {
                "total_queries": 0,
                "by_query_type": {"directory": 0, "document": 0, "general": 0},
                "clarifications_triggered": 0,
                "clarifications_by_type": {"directory": 0, "document": 0},
                "clarifications_resolved": 0,
                "clarifications_failed": 0,
                "answers_returned": 0,
                "answers_refused": 0,
                "by_confidence": {"high": 0, "medium": 0, "low": 0},
                "refusal_reasons": {},
            }
            self._recent_events.clear()
            logger.info("Event statistics reset")
