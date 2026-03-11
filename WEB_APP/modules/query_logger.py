"""
Query Logger — Unified Conversation Logging
=============================================
Single-file JSONL storage for conversations with inline feedback.

Schema:
    {query_id, timestamp, query, answer, feedback}

feedback: null (unrated), true (liked), false (disliked)
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Set, Tuple


# ==============================================================================
# CONFIGURATION
# ==============================================================================

DEFAULT_LOG_DIR = Path(__file__).parent / "logs"
CONVERSATION_LOG_FILE = "conversations.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# QUERY LOGGER CLASS
# ==============================================================================

class QueryLogger:
    """
    Unified conversation logger with inline feedback.

    Stores all conversation data in a single JSONL file.
    Retention policy: current + previous calendar month.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize the query logger.

        Args:
            log_dir: Directory to store log files (creates if doesn't exist)
        """
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_log_path = self.log_dir / CONVERSATION_LOG_FILE
        logger.info(f"QueryLogger initialized. Logs will be saved to: {self.log_dir}")

    def log_conversation(self, query: str, answer: str, timestamp: Optional[str] = None) -> str:
        """
        Log a conversation entry with the unified schema.

        Args:
            query:     The user's query string.
            answer:    The system's response string.
            timestamp: Optional ISO timestamp. When provided, the same
                       value should be used in the ChatResponse so that
                       the feedback system can link entries by timestamp.

        Returns:
            A unique query_id for this entry.
        """
        query_id = self._generate_id()
        entry = {
            "query_id":  query_id,
            "timestamp": timestamp or datetime.now().isoformat(),
            "query":     query,
            "answer":    answer,
            "feedback":  None,
        }
        self._append_to_log(self.conversation_log_path, entry)
        return query_id

    def update_feedback(self, query_id: str, is_helpful: bool) -> bool:
        """
        Update the feedback field of a conversation entry.

        Finds the entry whose timestamp matches query_id and sets its
        feedback field. Uses atomic file rewrite.

        Args:
            query_id:   The timestamp string that identifies the conversation.
            is_helpful: True for liked, False for disliked.

        Returns:
            True if the entry was found and updated, False otherwise.
        """
        log_path = self.conversation_log_path
        if not log_path.exists():
            return False

        lines: List[bytes] = []
        found = False

        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        entry = json.loads(stripped)
                    except json.JSONDecodeError:
                        lines.append((stripped + '\n').encode('utf-8'))
                        continue

                    if not found and entry.get("timestamp") == query_id:
                        entry["feedback"] = is_helpful
                        found = True

                    lines.append((json.dumps(entry, ensure_ascii=False) + '\n').encode('utf-8'))

            if not found:
                return False

            # Atomic replace via temp file
            dir_path = log_path.parent
            with tempfile.NamedTemporaryFile(
                mode='wb', dir=dir_path, delete=False, suffix='.tmp'
            ) as tmp:
                tmp_path = tmp.name
                for chunk in lines:
                    tmp.write(chunk)

            os.replace(tmp_path, log_path)
            logger.info(f"[Feedback] Updated feedback for query_id={query_id}: {is_helpful}")
            return True

        except Exception as e:
            logger.error(f"[Feedback] Failed to update feedback: {e}")
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except OSError:
                pass
            return False

    # ==========================================================================
    # RETENTION / CLEANUP
    # ==========================================================================

    @staticmethod
    def _get_allowed_months() -> Set[Tuple[int, int]]:
        """
        Return the set of (year, month) tuples that should be kept.

        Keeps the current calendar month and the immediately preceding calendar
        month, correctly handling year boundaries.
        """
        today = date.today()
        current = (today.year, today.month)

        if today.month == 1:
            previous = (today.year - 1, 12)
        else:
            previous = (today.year, today.month - 1)

        return {current, previous}

    def _cleanup_log_file(self, log_path: Path) -> int:
        """
        Rewrite a JSONL log file, keeping only entries within allowed months.

        Uses atomic write: temp file first, then os.replace().
        Idempotent and safe.

        Returns:
            Number of entries removed.
        """
        if not log_path.exists():
            return 0

        allowed = self._get_allowed_months()
        kept: List[bytes] = []
        removed = 0

        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        entry = json.loads(stripped)
                        ts_raw = entry.get("timestamp", "")
                        ts_date = datetime.fromisoformat(ts_raw[:19])
                        month_key = (ts_date.year, ts_date.month)
                        if month_key in allowed:
                            kept.append((stripped + '\n').encode('utf-8'))
                        else:
                            removed += 1
                    except (json.JSONDecodeError, ValueError):
                        kept.append((stripped + '\n').encode('utf-8'))

            if removed == 0:
                return 0

            dir_path = log_path.parent
            with tempfile.NamedTemporaryFile(
                mode='wb', dir=dir_path, delete=False, suffix='.tmp'
            ) as tmp:
                tmp_path = tmp.name
                for chunk in kept:
                    tmp.write(chunk)

            os.replace(tmp_path, log_path)
            logger.info(
                f"[Retention] Cleaned {log_path.name}: removed {removed} entries, "
                f"kept {len(kept)}."
            )

        except Exception as e:
            logger.error(f"[Retention] Failed to clean {log_path.name}: {e}")
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except OSError:
                pass

        return removed

    def run_cleanup(self) -> Dict[str, int]:
        """
        Apply the retention policy to the conversation log.

        Keeps entries from the current and previous calendar month;
        removes everything older. Safe to call multiple times (idempotent).
        """
        removed = self._cleanup_log_file(self.conversation_log_path)
        result = {self.conversation_log_path.name: removed}

        if removed:
            logger.info(f"[Retention] Removed {removed} expired entries.")
        else:
            logger.info("[Retention] Cleanup complete — no expired entries found.")

        return result

    # ==========================================================================
    # INTERNAL HELPERS
    # ==========================================================================

    def _append_to_log(self, log_path: Path, entry: Dict):
        """Append a log entry to a JSONL file."""
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _generate_id(self) -> str:
        """Generate a unique query ID based on timestamp."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
