"""
STT Usage Tracker
=================

Phase 38: Google Cloud STT Integration

Backend-authoritative usage tracking for Google Cloud STT free tier.
Tracks total converted audio duration with automatic monthly reset.

Features:
- Round-up billing (1.1s -> 2s) per Google Cloud pricing
- Lazy monthly reset on first request of new month
- Thread-safe file persistence
- Usage history preservation
"""

import json
import math
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Current usage statistics for display."""
    current_month: str  # "YYYY-MM"
    used_seconds: int
    quota_seconds: int
    remaining_seconds: int
    usage_percent: float
    transcription_count: int
    last_updated: str  # ISO8601


@dataclass
class MonthlyRecord:
    """Historical record for a completed month."""
    month: str  # "YYYY-MM"
    used_seconds: int
    transcription_count: int


class STTUsageTracker:
    """
    Tracks Google Cloud STT usage for quota management.

    Designed for the 60-minute free tier with automatic monthly reset.
    All operations are thread-safe and persist to disk immediately.
    """

    # Default quota: 60 minutes = 3600 seconds
    DEFAULT_QUOTA_SECONDS = 3600

    def __init__(self, data_dir: Path, quota_seconds: int = DEFAULT_QUOTA_SECONDS):
        """
        Initialize the usage tracker.

        Args:
            data_dir: Directory for storing usage data
            quota_seconds: Monthly quota in seconds (default: 3600 = 60 min)
        """
        self.data_dir = Path(data_dir)
        self.usage_file = self.data_dir / "stt_usage.json"
        self.quota_seconds = quota_seconds
        # Use RLock (reentrant lock) to allow nested lock acquisition
        # This is needed because record_usage() calls get_usage() while holding the lock
        self._lock = threading.RLock()

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize usage data
        self._usage_data = self._load_or_init()

        logger.info(f"[USAGE] Initialized STT usage tracker. Current: {self._usage_data.get('used_seconds', 0)}s / {self.quota_seconds}s")

    def _load_or_init(self) -> Dict[str, Any]:
        """Load existing usage data or initialize new."""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"[USAGE] Loaded usage data: {data.get('used_seconds', 0)}s used in {data.get('current_month', 'N/A')}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[USAGE] Failed to load usage file, initializing new: {e}")

        # Initialize new usage data
        return self._create_initial_data()

    def _create_initial_data(self) -> Dict[str, Any]:
        """Create initial usage data structure."""
        now = datetime.utcnow()
        return {
            "current_month": now.strftime("%Y-%m"),
            "used_seconds": 0,
            "quota_seconds": self.quota_seconds,
            "transcription_count": 0,
            "last_updated": now.isoformat() + "Z",
            "monthly_history": []
        }

    def _save(self) -> None:
        """Persist usage data to file."""
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(self._usage_data, f, indent=2)
        except IOError as e:
            logger.error(f"[USAGE] Failed to save usage data: {e}")

    def _check_month_reset(self) -> bool:
        """
        Check if calendar month changed and reset if needed.

        Returns:
            True if reset occurred, False otherwise.
        """
        current_month = datetime.utcnow().strftime("%Y-%m")
        stored_month = self._usage_data.get("current_month", "")

        if current_month != stored_month:
            logger.info(f"[USAGE] Month changed from {stored_month} to {current_month}. Resetting usage.")

            # Archive the old month's data
            if stored_month and self._usage_data.get("used_seconds", 0) > 0:
                history_record = {
                    "month": stored_month,
                    "used_seconds": self._usage_data.get("used_seconds", 0),
                    "transcription_count": self._usage_data.get("transcription_count", 0)
                }

                # Keep only last 12 months of history
                history = self._usage_data.get("monthly_history", [])
                history.append(history_record)
                if len(history) > 12:
                    history = history[-12:]
                self._usage_data["monthly_history"] = history

            # Reset for new month
            self._usage_data["current_month"] = current_month
            self._usage_data["used_seconds"] = 0
            self._usage_data["transcription_count"] = 0
            self._usage_data["last_updated"] = datetime.utcnow().isoformat() + "Z"

            self._save()
            return True

        return False

    @staticmethod
    def round_up_seconds(duration: float) -> int:
        """
        Round up duration to next full second.

        Per Google Cloud STT billing:
        - 1.0s -> 1s
        - 1.1s -> 2s
        - 0.5s -> 1s

        Args:
            duration: Audio duration in seconds

        Returns:
            Rounded-up duration in whole seconds
        """
        return math.ceil(duration) if duration > 0 else 0

    def record_usage(self, duration_seconds: float) -> UsageStats:
        """
        Record a transcription usage.

        Args:
            duration_seconds: Actual audio duration in seconds

        Returns:
            Updated usage statistics

        Note:
            Duration is rounded UP to next full second per Google billing.
        """
        with self._lock:
            # Check for month reset first
            self._check_month_reset()

            # Round up duration per Google billing
            billed_seconds = self.round_up_seconds(duration_seconds)

            # Update usage
            self._usage_data["used_seconds"] = self._usage_data.get("used_seconds", 0) + billed_seconds
            self._usage_data["transcription_count"] = self._usage_data.get("transcription_count", 0) + 1
            self._usage_data["last_updated"] = datetime.utcnow().isoformat() + "Z"

            # Persist immediately
            self._save()

            logger.info(f"[USAGE] Recorded {billed_seconds}s (from {duration_seconds:.2f}s audio). Total: {self._usage_data['used_seconds']}s / {self.quota_seconds}s")

            return self.get_usage()

    def get_usage(self) -> UsageStats:
        """
        Get current usage statistics.

        Returns:
            UsageStats with current month's usage
        """
        with self._lock:
            # Check for month reset
            self._check_month_reset()

            used = self._usage_data.get("used_seconds", 0)
            quota = self.quota_seconds
            remaining = max(0, quota - used)
            percent = (used / quota * 100) if quota > 0 else 0.0

            return UsageStats(
                current_month=self._usage_data.get("current_month", ""),
                used_seconds=used,
                quota_seconds=quota,
                remaining_seconds=remaining,
                usage_percent=round(percent, 1),
                transcription_count=self._usage_data.get("transcription_count", 0),
                last_updated=self._usage_data.get("last_updated", "")
            )

    def is_quota_exceeded(self) -> bool:
        """
        Check if monthly quota is exceeded.

        Returns:
            True if used_seconds >= quota_seconds
        """
        with self._lock:
            self._check_month_reset()
            return self._usage_data.get("used_seconds", 0) >= self.quota_seconds

    def get_remaining_seconds(self) -> int:
        """
        Get remaining seconds in quota.

        Returns:
            Number of seconds remaining (0 if exceeded)
        """
        with self._lock:
            self._check_month_reset()
            used = self._usage_data.get("used_seconds", 0)
            return max(0, self.quota_seconds - used)

    def get_history(self) -> List[MonthlyRecord]:
        """
        Get usage history for previous months.

        Returns:
            List of MonthlyRecord for archived months
        """
        with self._lock:
            history = self._usage_data.get("monthly_history", [])
            return [
                MonthlyRecord(
                    month=record.get("month", ""),
                    used_seconds=record.get("used_seconds", 0),
                    transcription_count=record.get("transcription_count", 0)
                )
                for record in history
            ]

    def to_dict(self) -> Dict[str, Any]:
        """
        Export usage data as dictionary for API response.

        Returns:
            Dictionary with all usage data
        """
        stats = self.get_usage()
        return {
            "current_month": stats.current_month,
            "used_seconds": stats.used_seconds,
            "quota_seconds": stats.quota_seconds,
            "remaining_seconds": stats.remaining_seconds,
            "usage_percent": stats.usage_percent,
            "transcription_count": stats.transcription_count,
            "last_updated": stats.last_updated,
            "is_quota_exceeded": self.is_quota_exceeded(),
            "monthly_history": [asdict(record) for record in self.get_history()]
        }


def format_seconds_as_time(seconds: int) -> str:
    """
    Format seconds as MM:SS string.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted string like "30:47" or "1:05:30" for hours
    """
    if seconds < 0:
        seconds = 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"
