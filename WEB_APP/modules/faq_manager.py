"""
FAQ Manager
===========

Manages Frequently Asked Questions (FAQ) for the CoCo Campus Kiosk.

Features:
- CRUD operations for FAQ items
- Maximum 20 questions limit
- Drag-and-drop reordering support
- Persistent JSON storage
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Configuration
MAX_FAQ_COUNT = 20
DEFAULT_VISIBLE_COUNT = 3  # Number shown before "Show More"


@dataclass
class FAQItem:
    """FAQ item data model."""
    id: str
    question: str
    answer: str
    display_order: int
    created_at: str
    updated_at: str
    status: str = "active"  # 'active' or 'inactive'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FAQItem':
        # Handle missing optional fields
        data.setdefault('status', 'active')
        return cls(**data)


class FAQManager:
    """
    Manages FAQ items for the kiosk display.

    Storage:
    - Registry: data/faq_data.json
    """

    def __init__(self, data_dir: Path):
        """
        Initialize FAQ Manager.

        Args:
            data_dir: Path to the data directory
        """
        self.data_dir = Path(data_dir)
        self.registry_path = self.data_dir / "faq_data.json"
        self._faqs: List[FAQItem] = []
        self._load_registry()

    def _load_registry(self) -> None:
        """Load FAQ registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._faqs = [FAQItem.from_dict(item) for item in data.get('faqs', [])]
                logger.info(f"Loaded {len(self._faqs)} FAQ items from registry")
            except Exception as e:
                logger.error(f"Error loading FAQ registry: {e}")
                self._faqs = []
        else:
            self._faqs = []
            self._save_registry()
            logger.info("Created new FAQ registry")

    def _save_registry(self) -> None:
        """Save FAQ registry to disk."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            data = {
                'faqs': [faq.to_dict() for faq in self._faqs],
                'updated_at': datetime.utcnow().isoformat()
            }
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("FAQ registry saved")
        except Exception as e:
            logger.error(f"Error saving FAQ registry: {e}")
            raise

    def get_all(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all FAQ items.

        Args:
            include_inactive: Whether to include inactive items

        Returns:
            List of FAQ items sorted by display_order
        """
        faqs = self._faqs if include_inactive else [f for f in self._faqs if f.status == 'active']
        sorted_faqs = sorted(faqs, key=lambda x: x.display_order)
        return [faq.to_dict() for faq in sorted_faqs]

    def get_by_id(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """Get a single FAQ by ID."""
        for faq in self._faqs:
            if faq.id == faq_id:
                return faq.to_dict()
        return None

    def add(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Add a new FAQ item.

        Args:
            question: The FAQ question
            answer: The FAQ answer

        Returns:
            The created FAQ item

        Raises:
            ValueError: If max FAQ count exceeded or validation fails
        """
        # Check limit
        active_count = len([f for f in self._faqs if f.status == 'active'])
        if active_count >= MAX_FAQ_COUNT:
            raise ValueError(f"Maximum FAQ limit ({MAX_FAQ_COUNT}) reached")

        # Validate
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        if not answer or not answer.strip():
            raise ValueError("Answer cannot be empty")

        # Create new FAQ
        now = datetime.utcnow().isoformat()
        max_order = max((f.display_order for f in self._faqs), default=-1)

        faq = FAQItem(
            id=str(uuid.uuid4()),
            question=question.strip(),
            answer=answer.strip(),
            display_order=max_order + 1,
            created_at=now,
            updated_at=now,
            status='active'
        )

        self._faqs.append(faq)
        self._save_registry()

        logger.info(f"Added FAQ: {faq.id}")
        return faq.to_dict()

    def update(self, faq_id: str, question: Optional[str] = None,
               answer: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing FAQ item.

        Args:
            faq_id: The FAQ ID to update
            question: New question text (optional)
            answer: New answer text (optional)
            status: New status (optional)

        Returns:
            The updated FAQ item

        Raises:
            ValueError: If FAQ not found or validation fails
        """
        faq = None
        for f in self._faqs:
            if f.id == faq_id:
                faq = f
                break

        if not faq:
            raise ValueError(f"FAQ not found: {faq_id}")

        # Update fields
        if question is not None:
            if not question.strip():
                raise ValueError("Question cannot be empty")
            faq.question = question.strip()

        if answer is not None:
            if not answer.strip():
                raise ValueError("Answer cannot be empty")
            faq.answer = answer.strip()

        if status is not None:
            if status not in ('active', 'inactive'):
                raise ValueError("Status must be 'active' or 'inactive'")
            faq.status = status

        faq.updated_at = datetime.utcnow().isoformat()
        self._save_registry()

        logger.info(f"Updated FAQ: {faq_id}")
        return faq.to_dict()

    def delete(self, faq_id: str) -> bool:
        """
        Delete an FAQ item.

        Args:
            faq_id: The FAQ ID to delete

        Returns:
            True if deleted, False if not found
        """
        for i, faq in enumerate(self._faqs):
            if faq.id == faq_id:
                self._faqs.pop(i)
                self._reorder_after_delete()
                self._save_registry()
                logger.info(f"Deleted FAQ: {faq_id}")
                return True

        return False

    def _reorder_after_delete(self) -> None:
        """Reorder FAQs after deletion to maintain sequential order."""
        sorted_faqs = sorted(self._faqs, key=lambda x: x.display_order)
        for i, faq in enumerate(sorted_faqs):
            faq.display_order = i

    def reorder(self, ordered_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Reorder FAQ items based on provided ID list.

        Args:
            ordered_ids: List of FAQ IDs in desired order

        Returns:
            Updated list of FAQ items

        Raises:
            ValueError: If any ID is invalid
        """
        # Validate all IDs exist
        id_set = {faq.id for faq in self._faqs}
        for faq_id in ordered_ids:
            if faq_id not in id_set:
                raise ValueError(f"Invalid FAQ ID: {faq_id}")

        # Create ID to FAQ mapping
        id_to_faq = {faq.id: faq for faq in self._faqs}

        # Update display_order based on position in ordered_ids
        for i, faq_id in enumerate(ordered_ids):
            if faq_id in id_to_faq:
                id_to_faq[faq_id].display_order = i
                id_to_faq[faq_id].updated_at = datetime.utcnow().isoformat()

        self._save_registry()
        logger.info(f"Reordered {len(ordered_ids)} FAQ items")

        return self.get_all(include_inactive=True)

    def get_config(self) -> Dict[str, Any]:
        """Get FAQ configuration."""
        return {
            'max_count': MAX_FAQ_COUNT,
            'default_visible': DEFAULT_VISIBLE_COUNT,
            'current_count': len([f for f in self._faqs if f.status == 'active']),
            'total_count': len(self._faqs)
        }
