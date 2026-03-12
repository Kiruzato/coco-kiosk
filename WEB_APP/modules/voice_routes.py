"""
Voice API Routes
================

Phase 32: Voice Infrastructure Foundation
Phase 33: Voice API Layer Enhancements

FastAPI routes for voice operations (STT, TTS, voice chat).

Endpoints:
- POST /voice/transcribe - Transcribe audio to text
- POST /voice/synthesize - Synthesize text to speech
- POST /voice/chat - Complete voice interaction (STT -> Chat -> TTS)
- GET /voice/status - Check voice service status
- GET /voice/health - Detailed health check for monitoring
- GET /voice/audio/{audio_id} - Retrieve temporarily stored audio
- WS /voice/stream - WebSocket for streaming transcription (Phase 33)
"""

import io
import uuid
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/voice", tags=["voice"])


# ============================================================================
# Phase 33: Error Codes
# ============================================================================

class VoiceErrorCode(str, Enum):
    """Standardized error codes for voice API."""
    SERVICE_UNAVAILABLE = "VOICE_SERVICE_UNAVAILABLE"
    STT_UNAVAILABLE = "STT_UNAVAILABLE"
    TTS_UNAVAILABLE = "TTS_UNAVAILABLE"
    INVALID_AUDIO = "INVALID_AUDIO"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    EMPTY_AUDIO = "EMPTY_AUDIO"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    SYNTHESIS_FAILED = "SYNTHESIS_FAILED"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    RATE_LIMITED = "RATE_LIMITED"
    AUDIO_NOT_FOUND = "AUDIO_NOT_FOUND"
    TEXT_REQUIRED = "TEXT_REQUIRED"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"


class VoiceError(HTTPException):
    """Custom exception with error code."""
    def __init__(self, status_code: int, code: VoiceErrorCode, detail: str):
        super().__init__(status_code=status_code, detail={"code": code.value, "message": detail})


# ============================================================================
# Phase 33: Rate Limiting
# ============================================================================

@dataclass
class RateLimitEntry:
    """Track request counts for rate limiting."""
    count: int = 0
    window_start: float = field(default_factory=time.time)


# Rate limit configuration
RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = {
    "transcribe": 30,   # 30 transcriptions per minute
    "synthesize": 60,   # 60 synthesis requests per minute
    "chat": 20,         # 20 full voice chats per minute
}

# In-memory rate limit storage (keyed by IP or session)
_rate_limits: Dict[str, Dict[str, RateLimitEntry]] = {}


def _check_rate_limit(client_id: str, endpoint: str) -> bool:
    """
    Check if client has exceeded rate limit.

    Returns True if request is allowed, False if rate limited.
    """
    now = time.time()
    max_requests = RATE_LIMIT_MAX_REQUESTS.get(endpoint, 60)

    if client_id not in _rate_limits:
        _rate_limits[client_id] = {}

    if endpoint not in _rate_limits[client_id]:
        _rate_limits[client_id][endpoint] = RateLimitEntry(count=1, window_start=now)
        return True

    entry = _rate_limits[client_id][endpoint]

    # Reset window if expired
    if now - entry.window_start > RATE_LIMIT_WINDOW_SECONDS:
        entry.count = 1
        entry.window_start = now
        return True

    # Check limit
    if entry.count >= max_requests:
        return False

    entry.count += 1
    return True


def _get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Use X-Forwarded-For if behind proxy, otherwise use client host
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============================================================================
# Temporary Audio Storage
# ============================================================================

# Format: {audio_id: {"data": bytes, "created_at": timestamp, "format": str}}
_audio_storage: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_audio_ttl_seconds = 300  # 5 minutes
_max_audio_entries = 100  # Limit storage size

# Phase 33: Track storage metrics
_storage_metrics = {
    "total_stored": 0,
    "total_retrieved": 0,
    "total_expired": 0,
}


# ============================================================================
# Request/Response Models
# ============================================================================

class TranscribeResponse(BaseModel):
    """Response from /voice/transcribe endpoint."""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    engine_used: str
    is_low_confidence: bool
    processing_time_ms: float
    # Phase 33: Additional fields
    is_fallback: bool = False
    word_count: int = 0


class SynthesizeRequest(BaseModel):
    """Request to /voice/synthesize endpoint."""
    text: str
    voice: Optional[str] = None  # Override default voice
    speed: Optional[float] = 1.0  # Speech speed multiplier (not yet implemented)


class VoiceChatResponse(BaseModel):
    """Response from /voice/chat endpoint."""
    # Session - CRITICAL for multi-turn conversations like clarification
    session_id: str

    # Transcription
    transcribed_text: str
    transcription_confidence: float

    # Chat response (mirrors existing ChatResponse)
    answer: str
    mode: str
    confidence: str
    sources: list
    rejected: bool
    # Phase 35: Include structured_answer for unified rendering
    structured_answer: Optional[dict] = None
    # Phase 39B: Include debug_info for debug panel
    debug_info: Optional[dict] = None
    # Phase 54: Metadata visibility (consistent with text responses)
    metadata_visible: bool = True
    fusion_mode: str = "linear"
    fusion_label_visible: bool = True

    # Audio
    audio_url: Optional[str] = None
    has_audio: bool = False

    # Flags
    requires_text_confirmation: bool
    error_message: Optional[str] = None

    # Timing
    latency_ms: dict


class VoiceStatusResponse(BaseModel):
    """Response from /voice/status endpoint."""
    voice_enabled: bool
    stt_available: bool
    stt_engine: Optional[str]
    tts_available: bool
    tts_engine: Optional[str]
    confidence_threshold: float


# Phase 33: Health check response
class VoiceHealthResponse(BaseModel):
    """Detailed health check response for monitoring."""
    status: str  # "healthy", "degraded", "unhealthy"
    voice_enabled: bool
    components: Dict[str, Dict[str, Any]]
    metrics: Dict[str, Any]
    uptime_seconds: float
    version: str = "33.0"


# Phase 33: WebSocket message models
class StreamingTranscriptMessage(BaseModel):
    """Message sent during streaming transcription."""
    type: str  # "partial", "final", "error"
    text: str
    confidence: float = 0.0
    is_final: bool = False
    timestamp: float = 0.0


# ============================================================================
# Module-level services (initialized by app.py)
# ============================================================================

_voice_orchestrator = None
_stt_service = None
_tts_service = None


# Phase 33: Startup time for uptime tracking
_startup_time: float = time.time()

# Phase 33: Request metrics
_request_metrics = {
    "transcribe_count": 0,
    "transcribe_success": 0,
    "transcribe_errors": 0,
    "synthesize_count": 0,
    "synthesize_success": 0,
    "synthesize_errors": 0,
    "chat_count": 0,
    "chat_success": 0,
    "chat_errors": 0,
}


def init_voice_services(orchestrator=None, stt=None, tts=None):
    """Initialize voice services. Called by app.py during startup."""
    global _voice_orchestrator, _stt_service, _tts_service, _startup_time
    _voice_orchestrator = orchestrator
    _stt_service = stt
    _tts_service = tts
    _startup_time = time.time()
    logger.info("[VOICE-ROUTES] Voice services initialized")


async def reload_voice_services(settings=None):
    """
    Reload voice services with new configuration.

    Phase 36: Called when admin changes voice provider settings.

    Args:
        settings: VoiceSettings object with new configuration

    Returns:
        Dict with reload status
    """
    global _voice_orchestrator, _stt_service, _tts_service

    try:
        from WEB_APP.modules.voice.config import VOICE_CONFIG
        from WEB_APP.modules.voice.stt_service import STTService
        from WEB_APP.modules.voice.tts_service import TTSService
        from WEB_APP.modules.voice.voice_orchestrator import VoiceOrchestrator

        logger.info("[VOICE-ROUTES] Reloading voice services...")

        # Get current chat handler from orchestrator
        chat_handler = None
        event_tracker = None
        if _voice_orchestrator:
            chat_handler = _voice_orchestrator.chat_handler
            event_tracker = _voice_orchestrator.event_tracker

        # Update config based on settings if provided
        if settings:
            # Update STT config
            if settings.stt_provider:
                VOICE_CONFIG['stt']['primary']['engine'] = settings.stt_provider
                logger.info(f"[VOICE-ROUTES] STT provider set to: {settings.stt_provider}")

            # Update TTS config
            if settings.tts_provider:
                VOICE_CONFIG['tts']['primary']['engine'] = settings.tts_provider
                logger.info(f"[VOICE-ROUTES] TTS provider set to: {settings.tts_provider}")

        # Reinitialize services
        new_stt = STTService(VOICE_CONFIG.get('stt', {}))
        new_tts = TTSService(VOICE_CONFIG.get('tts', {}))

        # Check availability
        stt_available = new_stt.is_available()
        tts_available = new_tts.is_available()

        logger.info(f"[VOICE-ROUTES] Reloaded - STT available: {stt_available}, TTS available: {tts_available}")

        # Create new orchestrator if we have a chat handler
        if chat_handler:
            new_orchestrator = VoiceOrchestrator(
                stt_service=new_stt,
                tts_service=new_tts,
                chat_handler=chat_handler,
                event_tracker=event_tracker
            )
            _voice_orchestrator = new_orchestrator

        # Update service references
        _stt_service = new_stt
        _tts_service = new_tts

        return {
            "success": True,
            "stt_available": stt_available,
            "tts_available": tts_available,
            "stt_engine": new_stt.get_engine_info().get("engine") if stt_available else None,
            "tts_engine": new_tts.get_engine_info().get("engine") if tts_available else None
        }

    except Exception as e:
        logger.error(f"[VOICE-ROUTES] Failed to reload services: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_orchestrator():
    """Get voice orchestrator, raising error if not initialized."""
    if _voice_orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Voice services not initialized"
        )
    return _voice_orchestrator


def get_stt_service():
    """Get STT service, raising error if not initialized."""
    if _stt_service is None:
        raise HTTPException(
            status_code=503,
            detail="STT service not initialized"
        )
    return _stt_service


def get_tts_service():
    """Get TTS service, raising error if not initialized."""
    if _tts_service is None:
        raise HTTPException(
            status_code=503,
            detail="TTS service not initialized"
        )
    return _tts_service


# Phase 41: Usage tracker singleton for voice_routes
# Kept separate from app.py to avoid circular import issues
_voice_usage_tracker = None

def _get_voice_usage_tracker():
    """Get or create usage tracker for voice routes."""
    global _voice_usage_tracker
    if _voice_usage_tracker is None:
        from WEB_APP.modules.voice.usage_tracker import STTUsageTracker
        data_dir = Path(__file__).parent / "data"
        _voice_usage_tracker = STTUsageTracker(data_dir)
    return _voice_usage_tracker


def _record_google_stt_usage(engine_used: str, duration_seconds: float):
    """
    Record Google Cloud STT usage for quota tracking.

    Phase 41: Fix for usage tracking not updating.
    Only records usage when Google Cloud STT is the engine used.

    Args:
        engine_used: Name of the STT engine that was used
        duration_seconds: Audio duration in seconds
    """
    if engine_used == "google-cloud-stt" and duration_seconds > 0:
        try:
            tracker = _get_voice_usage_tracker()
            tracker.record_usage(duration_seconds)
            logger.info(f"[USAGE] Recorded Google STT usage: {duration_seconds:.2f}s")
        except Exception as e:
            # Don't fail the request if usage tracking fails
            logger.warning(f"[USAGE] Failed to record Google STT usage: {e}")


# ============================================================================
# Audio Storage Helpers
# ============================================================================

def _cleanup_expired_audio():
    """Remove expired audio entries."""
    now = time.time()
    expired = [
        aid for aid, data in _audio_storage.items()
        if now - data["created_at"] > _audio_ttl_seconds
    ]
    for aid in expired:
        del _audio_storage[aid]
        _storage_metrics["total_expired"] += 1


def store_audio_temporarily(audio_data: bytes, audio_format: str = "wav") -> str:
    """
    Store audio temporarily and return ID.

    Audio is auto-deleted after TTL expires.
    """
    _cleanup_expired_audio()

    # Limit storage size
    while len(_audio_storage) >= _max_audio_entries:
        _audio_storage.popitem(last=False)  # Remove oldest

    audio_id = str(uuid.uuid4())
    _audio_storage[audio_id] = {
        "data": audio_data,
        "created_at": time.time(),
        "format": audio_format,
        "size_bytes": len(audio_data),
    }

    _storage_metrics["total_stored"] += 1
    return audio_id


def retrieve_audio(audio_id: str) -> Optional[bytes]:
    """Retrieve audio by ID, returning None if expired or not found."""
    _cleanup_expired_audio()

    entry = _audio_storage.get(audio_id)
    if entry is None:
        return None

    _storage_metrics["total_retrieved"] += 1
    return entry["data"]


def get_storage_stats() -> Dict[str, Any]:
    """Get audio storage statistics."""
    _cleanup_expired_audio()
    total_size = sum(e["size_bytes"] for e in _audio_storage.values())
    return {
        "current_entries": len(_audio_storage),
        "max_entries": _max_audio_entries,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "ttl_seconds": _audio_ttl_seconds,
        **_storage_metrics,
    }


# ============================================================================
# Phase 33: Audio Validation
# ============================================================================

# Supported audio formats and their magic bytes
AUDIO_SIGNATURES = {
    b'RIFF': 'wav',
    b'\x1a\x45\xdf\xa3': 'webm',
    b'ID3': 'mp3',
    b'\xff\xfb': 'mp3',
    b'\xff\xfa': 'mp3',
    b'OggS': 'ogg',
    b'fLaC': 'flac',
}

# Maximum audio constraints
MAX_AUDIO_SIZE_MB = 10
MAX_AUDIO_DURATION_SECONDS = 60


def validate_audio_file(audio_data: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate uploaded audio file for security and format compliance.

    Returns validation result with format info or raises VoiceError.
    """
    # Check empty
    if len(audio_data) == 0:
        raise VoiceError(400, VoiceErrorCode.EMPTY_AUDIO, "Audio file is empty")

    # Check size
    size_mb = len(audio_data) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        raise VoiceError(
            400,
            VoiceErrorCode.AUDIO_TOO_LARGE,
            f"Audio file too large: {size_mb:.1f}MB (max {MAX_AUDIO_SIZE_MB}MB)"
        )

    # Detect format from magic bytes
    detected_format = None
    for signature, fmt in AUDIO_SIGNATURES.items():
        if audio_data[:len(signature)] == signature:
            detected_format = fmt
            break

    # If format detection failed, try to infer from filename
    if detected_format is None and filename:
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else None
        if ext in ('wav', 'webm', 'mp3', 'ogg', 'flac', 'm4a'):
            detected_format = ext

    if detected_format is None:
        raise VoiceError(
            400,
            VoiceErrorCode.UNSUPPORTED_FORMAT,
            "Unsupported audio format. Supported: WAV, WebM, MP3, OGG"
        )

    # Security check: ensure no embedded scripts or suspicious content
    # (Basic check for HTML/JS injection in audio files)
    suspicious_patterns = [b'<script', b'javascript:', b'data:text/html']
    for pattern in suspicious_patterns:
        if pattern in audio_data[:1000]:  # Check first 1KB
            raise VoiceError(
                400,
                VoiceErrorCode.INVALID_AUDIO,
                "Invalid audio file content"
            )

    return {
        "format": detected_format,
        "size_bytes": len(audio_data),
        "size_mb": round(size_mb, 2),
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status", response_model=VoiceStatusResponse)
async def voice_status():
    """
    Check voice service availability.

    Useful for frontend to determine whether to show voice UI.
    """
    try:
        from WEB_APP.modules.voice.config import VOICE_CONFIG, is_voice_enabled

        stt_available = False
        stt_engine = None
        tts_available = False
        tts_engine = None
        confidence_threshold = 0.7

        if _stt_service:
            stt_available = _stt_service.is_available()
            info = _stt_service.get_engine_info()
            stt_engine = info.get("primary", {}).get("name")
            confidence_threshold = info.get("confidence_threshold", 0.7)

        if _tts_service:
            tts_available = _tts_service.is_available()
            info = _tts_service.get_engine_info()
            tts_engine = info.get("primary", {}).get("name")

        return VoiceStatusResponse(
            voice_enabled=is_voice_enabled(),
            stt_available=stt_available,
            stt_engine=stt_engine,
            tts_available=tts_available,
            tts_engine=tts_engine,
            confidence_threshold=confidence_threshold,
        )

    except ImportError:
        return VoiceStatusResponse(
            voice_enabled=False,
            stt_available=False,
            stt_engine=None,
            tts_available=False,
            tts_engine=None,
            confidence_threshold=0.7,
        )


# Phase 33: Health endpoint for monitoring
@router.get("/health", response_model=VoiceHealthResponse)
async def voice_health():
    """
    Detailed health check for monitoring systems.

    Returns component status, metrics, and uptime information.
    """
    try:
        from WEB_APP.modules.voice.config import is_voice_enabled

        components = {}
        overall_status = "healthy"

        # Check STT
        if _stt_service:
            stt_available = _stt_service.is_available()
            stt_info = _stt_service.get_engine_info()
            components["stt"] = {
                "status": "healthy" if stt_available else "unavailable",
                "available": stt_available,
                "engine": stt_info.get("primary", {}).get("name"),
                "fallback_enabled": stt_info.get("fallback", {}).get("enabled", False),
            }
            if not stt_available:
                overall_status = "degraded"
        else:
            components["stt"] = {"status": "not_initialized", "available": False}
            overall_status = "degraded"

        # Check TTS
        if _tts_service:
            tts_available = _tts_service.is_available()
            tts_info = _tts_service.get_engine_info()
            components["tts"] = {
                "status": "healthy" if tts_available else "unavailable",
                "available": tts_available,
                "engine": tts_info.get("primary", {}).get("name"),
            }
            if not tts_available:
                overall_status = "degraded"
        else:
            components["tts"] = {"status": "not_initialized", "available": False}
            overall_status = "degraded"

        # Check orchestrator
        components["orchestrator"] = {
            "status": "healthy" if _voice_orchestrator else "not_initialized",
            "available": _voice_orchestrator is not None,
        }

        # Storage status
        storage_stats = get_storage_stats()
        components["audio_storage"] = {
            "status": "healthy",
            "current_entries": storage_stats["current_entries"],
            "total_size_mb": storage_stats["total_size_mb"],
        }

        # If nothing is available, mark as unhealthy
        if not is_voice_enabled():
            overall_status = "unhealthy"

        return VoiceHealthResponse(
            status=overall_status,
            voice_enabled=is_voice_enabled(),
            components=components,
            metrics={
                "requests": _request_metrics,
                "storage": storage_stats,
            },
            uptime_seconds=round(time.time() - _startup_time, 2),
        )

    except Exception as e:
        logger.error(f"[VOICE] Health check error: {e}")
        return VoiceHealthResponse(
            status="unhealthy",
            voice_enabled=False,
            components={"error": {"message": str(e)}},
            metrics={},
            uptime_seconds=round(time.time() - _startup_time, 2),
        )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(..., description="Audio file (WebM, WAV, or MP3)"),
    language: str = Form(default="en", description="Expected language code")
):
    """
    Transcribe audio to text using STT service.

    Accepts: audio/webm, audio/wav, audio/mp3
    Returns: Transcription with confidence score

    If confidence < threshold, is_low_confidence=True suggests showing text input.

    Rate limit: 30 requests per minute per client.
    """
    _request_metrics["transcribe_count"] += 1

    # Phase 33: Rate limiting
    client_id = _get_client_id(request)
    if not _check_rate_limit(client_id, "transcribe"):
        _request_metrics["transcribe_errors"] += 1
        raise VoiceError(
            429,
            VoiceErrorCode.RATE_LIMITED,
            "Rate limit exceeded. Please wait before making more requests."
        )

    # Get service
    stt = get_stt_service()
    if not stt.is_available():
        _request_metrics["transcribe_errors"] += 1
        raise VoiceError(503, VoiceErrorCode.STT_UNAVAILABLE, "STT service not available")

    # Read and validate audio data
    audio_data = await audio.read()
    validation = validate_audio_file(audio_data, audio.filename)

    try:
        result = await stt.transcribe(audio_data, language=language)

        # Check for empty transcription
        if result.is_empty():
            _request_metrics["transcribe_errors"] += 1
            raise VoiceError(
                422,
                VoiceErrorCode.NO_SPEECH_DETECTED,
                "No speech detected in audio"
            )

        # Phase 41: Record Google STT usage for quota tracking
        _record_google_stt_usage(result.engine_used, result.duration_seconds)

        _request_metrics["transcribe_success"] += 1
        return TranscribeResponse(
            text=result.text,
            confidence=result.confidence,
            language=result.language,
            duration_seconds=result.duration_seconds,
            engine_used=result.engine_used,
            is_low_confidence=not result.is_high_confidence(),
            processing_time_ms=result.processing_time_ms,
            is_fallback=result.is_fallback,
            word_count=len(result.text.split()) if result.text else 0,
        )

    except VoiceError:
        raise
    except Exception as e:
        _request_metrics["transcribe_errors"] += 1
        logger.error(f"[VOICE] Transcription error: {e}")
        raise VoiceError(500, VoiceErrorCode.TRANSCRIPTION_FAILED, str(e))


@router.post("/synthesize")
async def synthesize_speech(request: Request, body: SynthesizeRequest):
    """
    Synthesize text to speech using TTS service.

    Returns: Audio stream (WAV format)

    Rate limit: 60 requests per minute per client.
    """
    _request_metrics["synthesize_count"] += 1

    # Phase 33: Rate limiting
    client_id = _get_client_id(request)
    if not _check_rate_limit(client_id, "synthesize"):
        _request_metrics["synthesize_errors"] += 1
        raise VoiceError(
            429,
            VoiceErrorCode.RATE_LIMITED,
            "Rate limit exceeded. Please wait before making more requests."
        )

    # Validate text
    if not body.text or not body.text.strip():
        _request_metrics["synthesize_errors"] += 1
        raise VoiceError(400, VoiceErrorCode.TEXT_REQUIRED, "Text is required")

    # Check text length (increased to support full response reading)
    max_text_length = 10000  # Characters - allows full chatbot responses
    if len(body.text) > max_text_length:
        _request_metrics["synthesize_errors"] += 1
        raise VoiceError(
            400,
            VoiceErrorCode.TEXT_TOO_LONG,
            f"Text too long: {len(body.text)} characters (max {max_text_length})"
        )

    # Get service
    tts = get_tts_service()
    if not tts.is_available():
        _request_metrics["synthesize_errors"] += 1
        raise VoiceError(503, VoiceErrorCode.TTS_UNAVAILABLE, "TTS service not available")

    try:
        result = await tts.synthesize(body.text)

        if result.is_empty():
            _request_metrics["synthesize_errors"] += 1
            raise VoiceError(500, VoiceErrorCode.SYNTHESIS_FAILED, "TTS produced no audio")

        _request_metrics["synthesize_success"] += 1
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=response.wav",
                "X-Audio-Duration": str(result.duration_seconds),
                "X-TTS-Engine": result.engine_used,
                "X-Processing-Time-Ms": str(result.processing_time_ms),
                "X-Text-Length": str(len(body.text)),
            }
        )

    except VoiceError:
        raise
    except Exception as e:
        _request_metrics["synthesize_errors"] += 1
        logger.error(f"[VOICE] Synthesis error: {e}")
        raise VoiceError(500, VoiceErrorCode.SYNTHESIS_FAILED, str(e))


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(
    request: Request,
    audio: UploadFile = File(..., description="Audio file"),
    session_id: Optional[str] = Form(default=None, description="Session ID for context"),
    skip_tts: bool = Form(default=False, description="Skip TTS synthesis")
):
    """
    Combined voice interaction: STT -> Chat -> TTS

    This is the primary endpoint for voice-enabled kiosk interaction.

    Flow:
    1. Transcribe uploaded audio
    2. Process through existing chat pipeline (all guarantees preserved)
    3. Synthesize response to audio (unless skip_tts=True)

    Returns both text and audio response.

    Rate limit: 20 requests per minute per client.
    """
    _request_metrics["chat_count"] += 1

    # Phase 33: Rate limiting
    client_id = _get_client_id(request)
    if not _check_rate_limit(client_id, "chat"):
        _request_metrics["chat_errors"] += 1
        raise VoiceError(
            429,
            VoiceErrorCode.RATE_LIMITED,
            "Rate limit exceeded. Please wait before making more requests."
        )

    orchestrator = get_orchestrator()

    # Read and validate audio data
    audio_data = await audio.read()
    validate_audio_file(audio_data, audio.filename)

    # Compute actual session_id (generate if not provided)
    # This is CRITICAL for multi-turn conversations like clarification
    actual_session_id = session_id or f"voice-{uuid.uuid4().hex[:8]}"

    try:
        result = await orchestrator.process_voice_interaction(
            audio_data=audio_data,
            session_id=actual_session_id,
            skip_tts=skip_tts,
        )

        # Phase 41: Record Google STT usage for quota tracking
        if result.transcription:
            _record_google_stt_usage(
                result.transcription.engine_used,
                result.transcription.duration_seconds
            )

        # Generate audio URL if synthesis succeeded
        audio_url = None
        has_audio = False
        if result.synthesis and result.synthesis_success:
            audio_id = store_audio_temporarily(result.synthesis.audio_data)
            audio_url = f"/voice/audio/{audio_id}"
            has_audio = True

        # Phase 39B: Merge voice service info into debug_info
        debug_info = result.chat_response.get('debug_info') if result.chat_response else None
        if debug_info:
            # Add STT engine info from transcription result
            if result.transcription:
                debug_info['stt_engine'] = result.transcription.engine_used
                debug_info['stt_fallback_used'] = result.transcription.is_fallback
            # Add TTS engine info from synthesis result
            if result.synthesis:
                debug_info['tts_engine'] = result.synthesis.engine_used
                debug_info['tts_fallback_used'] = getattr(result.synthesis, 'is_fallback', False)
            # Add voice latencies to timing
            if 'timing' in debug_info:
                debug_info['timing']['stt_ms'] = result.stt_latency_ms
                debug_info['timing']['tts_ms'] = result.tts_latency_ms

        # Build response
        _request_metrics["chat_success"] += 1
        return VoiceChatResponse(
            session_id=actual_session_id,
            transcribed_text=result.transcription.text if result.transcription else "",
            transcription_confidence=result.transcription.confidence if result.transcription else 0.0,
            answer=result.chat_response.get('answer', '') if result.chat_response else "",
            mode=result.chat_response.get('mode', 'unknown') if result.chat_response else "error",
            confidence=result.chat_response.get('confidence', 'LOW') if result.chat_response else "LOW",
            sources=result.chat_response.get('sources', []) if result.chat_response else [],
            rejected=result.chat_response.get('rejected', True) if result.chat_response else True,
            # Phase 35: Include structured_answer for unified rendering
            structured_answer=result.chat_response.get('structured_answer') if result.chat_response else None,
            # Phase 39B: Include debug_info with voice service info merged
            debug_info=debug_info,
            # Phase 54: Propagate metadata visibility settings
            metadata_visible=result.chat_response.get('metadata_visible', True) if result.chat_response else True,
            fusion_mode=result.chat_response.get('fusion_mode', 'linear') if result.chat_response else 'linear',
            fusion_label_visible=result.chat_response.get('fusion_label_visible', True) if result.chat_response else True,
            audio_url=audio_url,
            has_audio=has_audio,
            requires_text_confirmation=result.requires_text_fallback,
            error_message=result.error_message,
            latency_ms={
                "stt": result.stt_latency_ms,
                "chat": result.chat_latency_ms,
                "tts": result.tts_latency_ms,
                "total": result.total_latency_ms,
            }
        )

    except VoiceError:
        _request_metrics["chat_errors"] += 1
        raise
    except Exception as e:
        _request_metrics["chat_errors"] += 1
        logger.error(f"[VOICE] Voice chat error: {e}")
        raise VoiceError(500, VoiceErrorCode.TRANSCRIPTION_FAILED, str(e))


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """
    Retrieve temporarily stored audio file.

    Audio is stored for 5 minutes then auto-deleted.
    """
    audio_data = retrieve_audio(audio_id)

    if audio_data is None:
        raise VoiceError(404, VoiceErrorCode.AUDIO_NOT_FOUND, "Audio not found or expired")

    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/wav",
        headers={
            "Content-Disposition": f"inline; filename={audio_id}.wav",
        }
    )


# ============================================================================
# Phase 33: WebSocket Streaming Transcription
# ============================================================================

# Track active WebSocket connections
_active_websockets: Dict[str, WebSocket] = {}


@router.websocket("/stream")
async def websocket_stream_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for streaming audio transcription.

    Protocol:
    1. Client connects and sends audio chunks as binary messages
    2. Server processes chunks and sends back partial/final transcripts
    3. Client sends "END" text message when done

    Messages from server (JSON):
    - {"type": "connected", "session_id": "..."}
    - {"type": "partial", "text": "...", "confidence": 0.0}
    - {"type": "final", "text": "...", "confidence": 0.9, "is_final": true}
    - {"type": "error", "code": "...", "message": "..."}
    """
    await websocket.accept()

    session_id = f"ws-{uuid.uuid4().hex[:8]}"
    _active_websockets[session_id] = websocket

    logger.info(f"[VOICE-WS] Client connected: {session_id}")

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": time.time(),
        })

        # Accumulate audio chunks
        audio_chunks: List[bytes] = []
        total_size = 0
        max_size = MAX_AUDIO_SIZE_MB * 1024 * 1024

        while True:
            # Receive message (binary audio or text command)
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Handle text messages (commands)
            if "text" in message:
                text = message["text"]

                if text == "END":
                    # Process accumulated audio
                    if audio_chunks:
                        await _process_websocket_audio(
                            websocket, session_id, b"".join(audio_chunks)
                        )
                    audio_chunks = []
                    total_size = 0

                elif text == "CANCEL":
                    audio_chunks = []
                    total_size = 0
                    await websocket.send_json({
                        "type": "cancelled",
                        "timestamp": time.time(),
                    })

                elif text == "PING":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                    })

            # Handle binary messages (audio data)
            elif "bytes" in message:
                chunk = message["bytes"]
                chunk_size = len(chunk)

                # Check size limit
                if total_size + chunk_size > max_size:
                    await websocket.send_json({
                        "type": "error",
                        "code": VoiceErrorCode.AUDIO_TOO_LARGE.value,
                        "message": f"Audio exceeds maximum size of {MAX_AUDIO_SIZE_MB}MB",
                    })
                    audio_chunks = []
                    total_size = 0
                    continue

                audio_chunks.append(chunk)
                total_size += chunk_size

                # Send acknowledgment for large chunks
                if len(audio_chunks) % 10 == 0:
                    await websocket.send_json({
                        "type": "receiving",
                        "chunks": len(audio_chunks),
                        "total_size": total_size,
                    })

    except WebSocketDisconnect:
        logger.info(f"[VOICE-WS] Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"[VOICE-WS] Error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e),
            })
        except Exception:
            pass
    finally:
        _active_websockets.pop(session_id, None)


async def _process_websocket_audio(
    websocket: WebSocket,
    session_id: str,
    audio_data: bytes
):
    """Process accumulated audio and send transcription results."""
    try:
        # Validate audio
        try:
            validate_audio_file(audio_data)
        except VoiceError as e:
            await websocket.send_json({
                "type": "error",
                "code": e.detail.get("code") if isinstance(e.detail, dict) else "INVALID_AUDIO",
                "message": e.detail.get("message") if isinstance(e.detail, dict) else str(e.detail),
            })
            return

        # Get STT service
        if not _stt_service or not _stt_service.is_available():
            await websocket.send_json({
                "type": "error",
                "code": VoiceErrorCode.STT_UNAVAILABLE.value,
                "message": "STT service not available",
            })
            return

        # Send processing status
        await websocket.send_json({
            "type": "processing",
            "timestamp": time.time(),
        })

        # Transcribe
        result = await _stt_service.transcribe(audio_data)

        # Phase 41: Record Google STT usage for quota tracking
        _record_google_stt_usage(result.engine_used, result.duration_seconds)

        # Send result
        await websocket.send_json({
            "type": "final",
            "text": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "engine_used": result.engine_used,
            "is_low_confidence": not result.is_high_confidence(),
            "is_final": True,
            "timestamp": time.time(),
        })

        _request_metrics["transcribe_count"] += 1
        _request_metrics["transcribe_success"] += 1

    except Exception as e:
        logger.error(f"[VOICE-WS] Processing error: {e}")
        _request_metrics["transcribe_errors"] += 1
        await websocket.send_json({
            "type": "error",
            "code": VoiceErrorCode.TRANSCRIPTION_FAILED.value,
            "message": str(e),
        })
