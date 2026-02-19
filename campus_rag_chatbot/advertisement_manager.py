"""
Advertisement Manager
=====================

Phase 48: Advertisement Panel Management System

Handles CRUD operations for advertisement images displayed in the kiosk UI.
Follows existing patterns from document_manager.py.
"""

import json
import logging
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Allowed image types
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@dataclass
class Advertisement:
    """Advertisement data model."""
    id: str
    filename: str
    original_name: str
    mime_type: str
    file_size: int
    uploaded_at: str
    status: str  # 'active' or 'inactive'
    display_order: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Advertisement':
        return cls(**data)


class AdvertisementManager:
    """
    Manages advertisement images for the kiosk display.

    Storage:
    - Images: data/advertisements/
    - Registry: data/advertisement_registry.json
    """

    def __init__(self, data_dir: Path):
        """
        Initialize the advertisement manager.

        Args:
            data_dir: Path to the data directory
        """
        self.data_dir = Path(data_dir)
        self.ads_dir = self.data_dir / "advertisements"
        self.registry_path = self.data_dir / "advertisement_registry.json"

        # Ensure directories exist
        self.ads_dir.mkdir(parents=True, exist_ok=True)

        # Load registry
        self._registry: Dict[str, Any] = self._load_registry()
        logger.info(f"[ADS] Loaded {len(self._registry.get('advertisements', []))} advertisements")

    def _load_registry(self) -> Dict[str, Any]:
        """Load the advertisement registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"[ADS] Failed to load registry: {e}")
                return self._create_empty_registry()
        return self._create_empty_registry()

    def _create_empty_registry(self) -> Dict[str, Any]:
        """Create an empty registry structure."""
        return {
            "version": "1.0",
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "advertisements": []
        }

    def _save_registry(self) -> None:
        """Save the registry to disk."""
        self._registry["last_updated"] = datetime.utcnow().isoformat() + "Z"
        try:
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(self._registry, f, indent=2, ensure_ascii=False)
            logger.debug("[ADS] Registry saved")
        except IOError as e:
            logger.error(f"[ADS] Failed to save registry: {e}")
            raise

    def _validate_image(self, filename: str, content_type: str, file_size: int) -> tuple[bool, str]:
        """
        Validate an image file.

        Args:
            filename: Original filename
            content_type: MIME type
            file_size: File size in bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

        # Check MIME type
        if content_type not in ALLOWED_MIME_TYPES:
            return False, f"Invalid content type: {content_type}"

        # Check file size
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"

        return True, ""

    def _generate_filename(self, original_name: str) -> str:
        """Generate a unique filename for storage."""
        ext = Path(original_name).suffix.lower()
        unique_id = uuid.uuid4().hex[:12]
        return f"ad_{unique_id}{ext}"

    def _get_next_order(self) -> int:
        """Get the next display order value."""
        ads = self._registry.get("advertisements", [])
        if not ads:
            return 1
        return max(ad.get("display_order", 0) for ad in ads) + 1

    async def upload(
        self,
        filename: str,
        content_type: str,
        file_data: bytes
    ) -> Advertisement:
        """
        Upload a new advertisement image.

        Args:
            filename: Original filename
            content_type: MIME type
            file_data: Raw file bytes

        Returns:
            The created Advertisement

        Raises:
            ValueError: If validation fails
        """
        # Validate
        is_valid, error = self._validate_image(filename, content_type, len(file_data))
        if not is_valid:
            raise ValueError(error)

        # Generate unique filename
        stored_filename = self._generate_filename(filename)
        file_path = self.ads_dir / stored_filename

        # Save file
        try:
            with open(file_path, 'wb') as f:
                f.write(file_data)
        except IOError as e:
            logger.error(f"[ADS] Failed to save file: {e}")
            raise ValueError(f"Failed to save file: {e}")

        # Create advertisement record
        ad = Advertisement(
            id=str(uuid.uuid4()),
            filename=stored_filename,
            original_name=filename,
            mime_type=content_type,
            file_size=len(file_data),
            uploaded_at=datetime.utcnow().isoformat() + "Z",
            status="active",
            display_order=self._get_next_order()
        )

        # Add to registry
        self._registry["advertisements"].append(ad.to_dict())
        self._save_registry()

        logger.info(f"[ADS] Uploaded: {filename} -> {stored_filename}")
        return ad

    def list_active(self) -> List[Advertisement]:
        """Get all active advertisements, sorted by display order."""
        ads = [
            Advertisement.from_dict(ad)
            for ad in self._registry.get("advertisements", [])
            if ad.get("status") == "active"
        ]
        return sorted(ads, key=lambda a: a.display_order)

    def list_all(self) -> List[Advertisement]:
        """Get all advertisements, sorted by display order."""
        ads = [
            Advertisement.from_dict(ad)
            for ad in self._registry.get("advertisements", [])
        ]
        return sorted(ads, key=lambda a: a.display_order)

    def get(self, ad_id: str) -> Optional[Advertisement]:
        """Get a specific advertisement by ID."""
        for ad in self._registry.get("advertisements", []):
            if ad.get("id") == ad_id:
                return Advertisement.from_dict(ad)
        return None

    def delete(self, ad_id: str) -> bool:
        """
        Delete an advertisement.

        Args:
            ad_id: Advertisement ID

        Returns:
            True if deleted, False if not found
        """
        ads = self._registry.get("advertisements", [])

        # Find the ad
        ad_to_delete = None
        for i, ad in enumerate(ads):
            if ad.get("id") == ad_id:
                ad_to_delete = ads.pop(i)
                break

        if not ad_to_delete:
            return False

        # Delete the file
        file_path = self.ads_dir / ad_to_delete["filename"]
        if file_path.exists():
            try:
                file_path.unlink()
            except IOError as e:
                logger.error(f"[ADS] Failed to delete file: {e}")
                # Continue anyway - registry should be updated

        # Save registry
        self._save_registry()

        logger.info(f"[ADS] Deleted: {ad_to_delete['original_name']} ({ad_id})")
        return True

    def set_status(self, ad_id: str, status: str) -> bool:
        """
        Set the status of an advertisement.

        Args:
            ad_id: Advertisement ID
            status: 'active' or 'inactive'

        Returns:
            True if updated, False if not found
        """
        if status not in ("active", "inactive"):
            raise ValueError("Status must be 'active' or 'inactive'")

        for ad in self._registry.get("advertisements", []):
            if ad.get("id") == ad_id:
                ad["status"] = status
                self._save_registry()
                logger.info(f"[ADS] Status updated: {ad_id} -> {status}")
                return True
        return False

    def reorder(self, ad_ids: List[str]) -> bool:
        """
        Reorder advertisements.

        Args:
            ad_ids: List of advertisement IDs in new order

        Returns:
            True if reordered successfully
        """
        ads = self._registry.get("advertisements", [])
        id_to_ad = {ad["id"]: ad for ad in ads}

        # Validate all IDs exist
        for ad_id in ad_ids:
            if ad_id not in id_to_ad:
                logger.warning(f"[ADS] Reorder: unknown ID {ad_id}")
                return False

        # Update order
        for i, ad_id in enumerate(ad_ids, start=1):
            id_to_ad[ad_id]["display_order"] = i

        self._save_registry()
        logger.info(f"[ADS] Reordered {len(ad_ids)} advertisements")
        return True

    def get_image_url(self, ad: Advertisement) -> str:
        """Get the URL for an advertisement image."""
        return f"/advertisements/{ad.filename}"
