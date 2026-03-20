"""
Phase 36/37/38: Voice Provider Registry
=======================================
Provides discovery and status checking for STT/TTS providers.
Used by admin UI to display available providers and their status.

Phase 37 additions:
- is_selectable: Whether provider can be selected as primary
- pricing_tier: "free" or "paid" or "free-tier" (quota-limited)
- status_label: Display label for non-selectable providers
- can_be_fallback: Whether provider can be used as fallback
- Explicit fallback provider selection

Phase 38 additions:
- Google Cloud STT provider with usage tracking
- monthly_quota_seconds: For quota-limited free tier providers
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ProviderInfo:
    """Information about a voice provider."""
    id: str
    name: str
    type: str  # 'stt' or 'tts'
    is_local: bool
    is_available: bool
    is_active: bool = False
    requires_model: bool = False
    model_path: Optional[str] = None
    # Phase 37: New fields for enhanced admin UI
    is_selectable: bool = True           # Can user select as primary?
    pricing_tier: str = "free"           # "free" | "paid" | "free-tier"
    status_label: Optional[str] = None   # e.g., "Cloud - Not Operational"
    can_be_fallback: bool = False        # Can be used as fallback?
    is_fallback_active: bool = False     # Currently selected as fallback?
    # Phase 38: Quota tracking for free-tier providers
    monthly_quota_seconds: Optional[int] = None  # e.g., 3600 for Google STT
    has_usage_tracking: bool = False     # Whether provider tracks usage

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceSettings:
    """Persistent voice configuration settings."""
    stt_provider: str = "whisper.cpp"
    tts_provider: str = "piper"
    stt_fallback_enabled: bool = True
    tts_fallback_enabled: bool = True
    # Phase 37: Explicit fallback provider selection
    stt_fallback_provider: Optional[str] = None  # None = auto-select
    tts_fallback_provider: Optional[str] = None  # None = auto-select
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# PROVIDER DEFINITIONS
# ==============================================================================

# STT Providers
# Phase 37: Added is_selectable, pricing_tier, status_label, can_be_fallback
STT_PROVIDERS = [
    {
        "id": "whisper.cpp",
        "name": "Whisper.cpp (Local)",
        "is_local": True,
        "requires_model": True,
        "model_env": "WHISPER_MODEL_PATH",
        "default_model": "voice/models/whisper/ggml-tiny.en.bin",
        # Phase 37 fields
        "is_selectable": True,
        "pricing_tier": "free",
        "status_label": None,
        "can_be_fallback": True,  # Can be fallback if model available
    },
    # Phase 38: Google Cloud STT (privacy-safe — data logging disabled)
    {
        "id": "google-cloud-stt",
        "name": "Google Cloud STT",
        "is_local": False,
        "requires_model": False,
        "requires_credentials": "GOOGLE_APPLICATION_CREDENTIALS",
        # Phase 37/38 fields
        "is_selectable": True,
        "pricing_tier": "free-tier",  # Quota-limited (60 min/month)
        "status_label": None,
        "can_be_fallback": True,
        # Phase 38: Quota tracking
        "monthly_quota_seconds": 3600,  # 60 minutes
        "has_usage_tracking": True,
    }
]

# TTS Providers
# Phase 37: Added is_selectable, pricing_tier, status_label, can_be_fallback
TTS_PROVIDERS = [
    {
        "id": "piper",
        "name": "Piper TTS (Local)",
        "is_local": True,
        "requires_model": True,
        "model_env": "PIPER_MODEL_PATH",
        "default_model": "voice/models/piper/en_US-amy-medium.onnx",
        # Phase 37 fields
        "is_selectable": True,
        "pricing_tier": "free",
        "status_label": None,
        "can_be_fallback": True,  # Can be fallback if model available
    }
]


# ==============================================================================
# PROVIDER REGISTRY CLASS
# ==============================================================================

class ProviderRegistry:
    """Registry for discovering and managing voice providers."""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize provider registry.

        Args:
            base_path: Base path for resolving relative model paths.
                       Defaults to WEB_APP/modules directory.
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent
        self.base_path = base_path
        self.settings_path = base_path / "data" / "voice_settings.json"
        self._settings: Optional[VoiceSettings] = None

    # ==========================================================================
    # SETTINGS PERSISTENCE
    # ==========================================================================

    def load_settings(self) -> VoiceSettings:
        """Load voice settings from file, or return defaults."""
        if self._settings is not None:
            return self._settings

        try:
            if self.settings_path.exists():
                with open(self.settings_path, 'r') as f:
                    data = json.load(f)
                self._settings = VoiceSettings(
                    stt_provider=data.get('stt_provider', 'whisper.cpp'),
                    tts_provider=data.get('tts_provider', 'piper'),
                    stt_fallback_enabled=data.get('stt_fallback_enabled', True),
                    tts_fallback_enabled=data.get('tts_fallback_enabled', True),
                    # Phase 37: Explicit fallback provider selection
                    stt_fallback_provider=data.get('stt_fallback_provider'),
                    tts_fallback_provider=data.get('tts_fallback_provider'),
                    updated_at=data.get('updated_at')
                )
                logger.info(f"[VOICE-REGISTRY] Loaded settings: STT={self._settings.stt_provider}, TTS={self._settings.tts_provider}")
            else:
                self._settings = VoiceSettings()
                logger.info("[VOICE-REGISTRY] Using default settings")
        except Exception as e:
            logger.warning(f"[VOICE-REGISTRY] Failed to load settings: {e}, using defaults")
            self._settings = VoiceSettings()

        return self._settings

    def save_settings(self, settings: VoiceSettings) -> bool:
        """
        Save voice settings to file.

        Args:
            settings: VoiceSettings to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Ensure data directory exists
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Update timestamp
            settings.updated_at = datetime.utcnow().isoformat() + "Z"

            # Save to file
            with open(self.settings_path, 'w') as f:
                json.dump(settings.to_dict(), f, indent=2)

            # Update cached settings
            self._settings = settings

            logger.info(f"[VOICE-REGISTRY] Saved settings: STT={settings.stt_provider}, TTS={settings.tts_provider}")
            return True

        except Exception as e:
            logger.error(f"[VOICE-REGISTRY] Failed to save settings: {e}")
            return False

    # ==========================================================================
    # PROVIDER DISCOVERY
    # ==========================================================================

    def get_stt_providers(self) -> List[ProviderInfo]:
        """Get list of all STT providers with availability status."""
        settings = self.load_settings()
        providers = []

        for p in STT_PROVIDERS:
            is_available = self._check_provider_available(p)
            # Phase 37: can_be_fallback depends on availability for model-based providers
            can_be_fallback = p.get("can_be_fallback", False)
            if can_be_fallback and p.get("requires_model"):
                can_be_fallback = is_available  # Can only be fallback if model exists
            # Phase 38: Also check credentials for cloud providers
            if can_be_fallback and p.get("requires_credentials"):
                can_be_fallback = is_available

            providers.append(ProviderInfo(
                id=p["id"],
                name=p["name"],
                type="stt",
                is_local=p["is_local"],
                is_available=is_available,
                is_active=(p["id"] == settings.stt_provider),
                requires_model=p.get("requires_model", False),
                model_path=self._get_model_path(p) if p.get("requires_model") else None,
                # Phase 37 fields
                is_selectable=p.get("is_selectable", True),
                pricing_tier=p.get("pricing_tier", "free"),
                status_label=p.get("status_label"),
                can_be_fallback=can_be_fallback,
                is_fallback_active=(p["id"] == settings.stt_fallback_provider),
                # Phase 38 fields
                monthly_quota_seconds=p.get("monthly_quota_seconds"),
                has_usage_tracking=p.get("has_usage_tracking", False),
            ))

        return providers

    def get_tts_providers(self) -> List[ProviderInfo]:
        """Get list of all TTS providers with availability status."""
        settings = self.load_settings()
        providers = []

        for p in TTS_PROVIDERS:
            is_available = self._check_provider_available(p)
            # Phase 37: can_be_fallback depends on availability for model-based providers
            can_be_fallback = p.get("can_be_fallback", False)
            if can_be_fallback and p.get("requires_model"):
                can_be_fallback = is_available  # Can only be fallback if model exists

            providers.append(ProviderInfo(
                id=p["id"],
                name=p["name"],
                type="tts",
                is_local=p["is_local"],
                is_available=is_available,
                is_active=(p["id"] == settings.tts_provider),
                requires_model=p.get("requires_model", False),
                model_path=self._get_model_path(p) if p.get("requires_model") else None,
                # Phase 37 fields
                is_selectable=p.get("is_selectable", True),
                pricing_tier=p.get("pricing_tier", "free"),
                status_label=p.get("status_label"),
                can_be_fallback=can_be_fallback,
                is_fallback_active=(p["id"] == settings.tts_fallback_provider),
            ))

        return providers

    def get_all_providers(self) -> Dict[str, Any]:
        """Get all providers and current configuration."""
        settings = self.load_settings()

        return {
            "stt_providers": [p.to_dict() for p in self.get_stt_providers()],
            "tts_providers": [p.to_dict() for p in self.get_tts_providers()],
            "current_config": {
                "stt_provider": settings.stt_provider,
                "tts_provider": settings.tts_provider,
                "stt_fallback_enabled": settings.stt_fallback_enabled,
                "tts_fallback_enabled": settings.tts_fallback_enabled,
                # Phase 37: Explicit fallback provider selection
                "stt_fallback_provider": settings.stt_fallback_provider,
                "tts_fallback_provider": settings.tts_fallback_provider,
            }
        }

    # ==========================================================================
    # AVAILABILITY CHECKING
    # ==========================================================================

    def _check_provider_available(self, provider_def: Dict) -> bool:
        """Check if a provider is available for use."""
        provider_id = provider_def["id"]

        # Check model file requirement
        if provider_def.get("requires_model"):
            model_path = self._get_model_path(provider_def)
            if not model_path or not Path(model_path).exists():
                return False

        # Check API key requirement
        if provider_def.get("requires_api_key"):
            api_key = os.getenv(provider_def["requires_api_key"])
            if not api_key:
                return False

        # Phase 38: Check credentials file requirement (for Google Cloud)
        if provider_def.get("requires_credentials"):
            creds_path = os.getenv(provider_def["requires_credentials"])
            if not creds_path or not Path(creds_path).exists():
                return False

        return True

    def _get_model_path(self, provider_def: Dict) -> Optional[str]:
        """Get model path for a provider, resolving relative paths against base_path."""
        if not provider_def.get("requires_model"):
            return None

        # Check environment variable first
        env_var = provider_def.get("model_env")
        if env_var:
            env_path = os.getenv(env_var)
            if env_path:
                path = Path(env_path)
                if not path.is_absolute():
                    # Resolve relative path against base_path (matches config.py behavior)
                    path = self.base_path / env_path
                return str(path)

        # Fall back to default path
        default_path = provider_def.get("default_model")
        if default_path:
            full_path = self.base_path / default_path
            return str(full_path)

        return None

    def is_provider_available(self, provider_id: str) -> bool:
        """Check if a specific provider is available."""
        # Check STT providers
        for p in STT_PROVIDERS:
            if p["id"] == provider_id:
                return self._check_provider_available(p)

        # Check TTS providers
        for p in TTS_PROVIDERS:
            if p["id"] == provider_id:
                return self._check_provider_available(p)

        return False

    def validate_provider_selection(
        self,
        stt_provider: str,
        tts_provider: str,
        stt_fallback_provider: Optional[str] = None,
        tts_fallback_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate that selected providers are available and selectable.

        Phase 37: Added selectability validation and fallback validation.

        Returns:
            Dict with 'valid' boolean and 'errors' list
        """
        errors = []

        # Validate STT provider
        stt_valid = False
        for p in STT_PROVIDERS:
            if p["id"] == stt_provider:
                stt_valid = True
                # Phase 37: Check selectability
                if not p.get("is_selectable", True):
                    errors.append(f"STT provider '{stt_provider}' is not selectable: {p.get('status_label', 'Not available')}")
                elif not self._check_provider_available(p):
                    errors.append(f"STT provider '{stt_provider}' is not available")
                break
        if not stt_valid:
            errors.append(f"Unknown STT provider: {stt_provider}")

        # Validate TTS provider
        tts_valid = False
        for p in TTS_PROVIDERS:
            if p["id"] == tts_provider:
                tts_valid = True
                # Phase 37: Check selectability
                if not p.get("is_selectable", True):
                    errors.append(f"TTS provider '{tts_provider}' is not selectable: {p.get('status_label', 'Not available')}")
                elif not self._check_provider_available(p):
                    errors.append(f"TTS provider '{tts_provider}' is not available")
                break
        if not tts_valid:
            errors.append(f"Unknown TTS provider: {tts_provider}")

        # Phase 37: Validate fallback selections
        if stt_fallback_provider:
            fallback_errors = self._validate_fallback("stt", stt_provider, stt_fallback_provider)
            errors.extend(fallback_errors)

        if tts_fallback_provider:
            fallback_errors = self._validate_fallback("tts", tts_provider, tts_fallback_provider)
            errors.extend(fallback_errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def _validate_fallback(
        self,
        provider_type: str,
        primary_provider: str,
        fallback_provider: str
    ) -> List[str]:
        """
        Validate a fallback provider selection.

        Phase 37: Ensures fallback is:
        - Different from primary
        - Marked as can_be_fallback
        - Available (model exists if required)
        - Not a paid provider

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        providers = STT_PROVIDERS if provider_type == "stt" else TTS_PROVIDERS

        # Check fallback is different from primary
        if fallback_provider == primary_provider:
            errors.append(f"{provider_type.upper()} fallback cannot be the same as primary provider")
            return errors

        # Find fallback provider definition
        fallback_def = None
        for p in providers:
            if p["id"] == fallback_provider:
                fallback_def = p
                break

        if fallback_def is None:
            errors.append(f"Unknown {provider_type.upper()} fallback provider: {fallback_provider}")
            return errors

        # Check can_be_fallback flag
        if not fallback_def.get("can_be_fallback", False):
            errors.append(f"Provider '{fallback_provider}' cannot be used as {provider_type.upper()} fallback")
            return errors

        # Check not a paid provider
        if fallback_def.get("pricing_tier") == "paid":
            errors.append(f"Paid provider '{fallback_provider}' cannot be used as fallback")
            return errors

        # Check availability (model exists if required)
        if not self._check_provider_available(fallback_def):
            errors.append(f"{provider_type.upper()} fallback provider '{fallback_provider}' is not available")

        return errors


# ==============================================================================
# MODULE-LEVEL INSTANCE
# ==============================================================================

# Singleton instance for the registry
_registry: Optional[ProviderRegistry] = None

def get_registry() -> ProviderRegistry:
    """Get the singleton provider registry instance."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
