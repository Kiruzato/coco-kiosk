"""
Voice Configuration
===================

Phase 32: Voice Infrastructure Foundation

Configuration for STT (Speech-to-Text) and TTS (Text-to-Speech) services.
Designed for offline-first operation on Raspberry Pi 5.

Environment Variables:
    VOICE_ENABLED: Enable/disable voice features (default: true)
    WHISPER_MODEL_PATH: Path to Whisper.cpp model file
    PIPER_MODEL_PATH: Path to Piper TTS model file
    WHISPER_THREADS: Number of CPU threads for Whisper (default: 4)
    WHISPER_CLOUD_FALLBACK: Enable cloud fallback for low confidence (default: false)
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "voice" / "models"

# Default model paths (can be overridden by environment variables)
DEFAULT_WHISPER_MODEL = MODELS_DIR / "whisper" / "ggml-tiny.en.bin"
DEFAULT_PIPER_MODEL = MODELS_DIR / "piper" / "en_US-amy-medium.onnx"
DEFAULT_PIPER_CONFIG = MODELS_DIR / "piper" / "en_US-amy-medium.onnx.json"


def _get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def _get_int_env(key: str, default: int) -> int:
    """Get integer value from environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_float_env(key: str, default: float) -> float:
    """Get float value from environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# Main voice configuration
VOICE_CONFIG: Dict[str, Any] = {
    # Master enable/disable
    "enabled": _get_bool_env("VOICE_ENABLED", True),

    # Speech-to-Text configuration
    "stt": {
        "primary": {
            "engine": "whisper.cpp",
            "model_path": os.getenv("WHISPER_MODEL_PATH", str(DEFAULT_WHISPER_MODEL)),
            "language": "en",
            "threads": _get_int_env("WHISPER_THREADS", 4),  # RPi5 has 4 cores
            "beam_size": 5,
            "best_of": 3,
        },
        "fallback": {
            "engine": "openai-whisper",
            "model": "whisper-1",
            "enabled": _get_bool_env("WHISPER_CLOUD_FALLBACK", False),
        },
        "thresholds": {
            "min_confidence": _get_float_env("STT_MIN_CONFIDENCE", 0.7),
            "retry_on_low_confidence": True,
            "max_audio_duration_seconds": _get_int_env("STT_MAX_DURATION", 30),
        }
    },

    # Phase 38: Google Cloud STT configuration
    "google_cloud_stt": {
        "credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "model": "default",  # 'default' uses data logging = free tier
        "language_code": "en-US",
        "sample_rate_hertz": 16000,
        "enable_automatic_punctuation": True,
        "enabled": _get_bool_env("GOOGLE_STT_ENABLED", True),
    },

    # Phase 38: Usage tracking configuration
    "usage_tracking": {
        "enabled": _get_bool_env("USAGE_TRACKING_ENABLED", True),
        "quota_seconds": _get_int_env("GOOGLE_STT_QUOTA_SECONDS", 3600),  # 60 minutes
        "warn_threshold_percent": _get_int_env("USAGE_WARN_THRESHOLD", 80),  # Warn at 80%
    },

    # Text-to-Speech configuration
    "tts": {
        "primary": {
            "engine": "piper",
            "voice": "en_US-amy-medium",
            "model_path": os.getenv("PIPER_MODEL_PATH", str(DEFAULT_PIPER_MODEL)),
            "config_path": os.getenv("PIPER_CONFIG_PATH", str(DEFAULT_PIPER_CONFIG)),
            "sample_rate": 22050,
            "speaker_id": 0,
        },
        "fallback": {
            "engine": "edge-tts",
            "voice": "en-US-JennyNeural",
            "rate": "+0%",
        },
        "cloud_fallback": {
            "engine": "openai-tts",
            "voice": "nova",
            "model": "tts-1",
            "enabled": _get_bool_env("TTS_CLOUD_FALLBACK", False),
        },
        "max_chars": _get_int_env("TTS_MAX_CHARS", 500),  # Limit TTS length
    },

    # Audio format configuration
    "audio": {
        "input": {
            "sample_rate": 16000,  # Whisper expects 16kHz
            "channels": 1,
            "format": "wav",
        },
        "output": {
            "sample_rate": 22050,  # Piper outputs 22.05kHz
            "channels": 1,
            "format": "wav",
        },
        "temp_storage_ttl_seconds": _get_int_env("VOICE_AUDIO_TTL", 300),  # 5 minutes
        "max_upload_size_mb": _get_int_env("VOICE_MAX_UPLOAD_MB", 10),
    },

    # Timeouts and limits
    "timeouts": {
        "stt_timeout_seconds": _get_int_env("STT_TIMEOUT", 30),
        "tts_timeout_seconds": _get_int_env("TTS_TIMEOUT", 15),
        "total_timeout_seconds": _get_int_env("VOICE_TOTAL_TIMEOUT", 60),
    },
}


def is_voice_enabled() -> bool:
    """Check if voice features are enabled."""
    return VOICE_CONFIG.get("enabled", False)


def get_stt_config() -> Dict[str, Any]:
    """Get STT configuration."""
    return VOICE_CONFIG.get("stt", {})


def get_tts_config() -> Dict[str, Any]:
    """Get TTS configuration."""
    return VOICE_CONFIG.get("tts", {})


def get_audio_config() -> Dict[str, Any]:
    """Get audio configuration."""
    return VOICE_CONFIG.get("audio", {})


def validate_config() -> Dict[str, bool]:
    """
    Validate voice configuration.

    Returns dict with validation results for each component.
    """
    results = {
        "voice_enabled": is_voice_enabled(),
        "stt_model_exists": False,
        "tts_model_exists": False,
        "stt_fallback_configured": False,
        "tts_fallback_configured": False,
    }

    # Check STT model
    stt_model_path = Path(VOICE_CONFIG["stt"]["primary"]["model_path"])
    results["stt_model_exists"] = stt_model_path.exists()

    # Check TTS model
    tts_model_path = Path(VOICE_CONFIG["tts"]["primary"]["model_path"])
    results["tts_model_exists"] = tts_model_path.exists()

    # Check fallback configuration
    results["stt_fallback_configured"] = VOICE_CONFIG["stt"]["fallback"].get("enabled", False)
    results["tts_fallback_configured"] = VOICE_CONFIG["tts"]["cloud_fallback"].get("enabled", False)

    if not results["stt_model_exists"]:
        logger.warning(f"[VOICE] STT model not found at: {stt_model_path}")

    if not results["tts_model_exists"]:
        logger.warning(f"[VOICE] TTS model not found at: {tts_model_path}")

    return results


def log_config_summary():
    """Log a summary of the voice configuration."""
    validation = validate_config()

    logger.info("[VOICE] Configuration Summary:")
    logger.info(f"  - Voice enabled: {validation['voice_enabled']}")
    logger.info(f"  - STT engine: {VOICE_CONFIG['stt']['primary']['engine']}")
    logger.info(f"  - STT model exists: {validation['stt_model_exists']}")
    logger.info(f"  - TTS engine: {VOICE_CONFIG['tts']['primary']['engine']}")
    logger.info(f"  - TTS model exists: {validation['tts_model_exists']}")
    logger.info(f"  - Cloud fallback (STT): {validation['stt_fallback_configured']}")
    logger.info(f"  - Cloud fallback (TTS): {validation['tts_fallback_configured']}")
