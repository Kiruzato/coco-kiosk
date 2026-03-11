"""
Speech-to-Text Service
======================

Phase 32: Voice Infrastructure Foundation

Provides speech-to-text transcription with automatic engine fallback.

Strategy:
1. Try primary engine (Whisper.cpp or Google Cloud STT)
2. If confidence < threshold, retry with fallback engine (if enabled)
3. Return best result with confidence metadata

Supported Engines:
- whisper.cpp (local, offline)
- Google Cloud STT (cloud, free-tier)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription."""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    engine_used: str
    is_fallback: bool = False
    processing_time_ms: float = 0.0
    raw_segments: Optional[list] = None  # For detailed segment info

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if transcription confidence meets threshold."""
        return self.confidence >= threshold

    def is_empty(self) -> bool:
        """Check if transcription produced no text."""
        return not self.text or not self.text.strip()


class STTEngine(ABC):
    """Abstract base class for STT engines."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes (WAV format, 16kHz mono)
            sample_rate: Audio sample rate
            language: Expected language code

        Returns:
            TranscriptionResult with text and confidence
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the engine is available and ready."""
        pass

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Get the engine name for logging/display."""
        pass


class STTService:
    """
    Speech-to-Text service with automatic fallback.

    Strategy:
    1. Try primary engine (Whisper.cpp, offline)
    2. If confidence < threshold, retry with cloud engine
    3. Return best result with confidence metadata
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize STT service with configuration.

        Args:
            config: STT configuration dict with 'primary', 'fallback', 'thresholds'
        """
        self.config = config
        self.primary_engine: Optional[STTEngine] = None
        self.fallback_engine: Optional[STTEngine] = None
        self.confidence_threshold = config.get('thresholds', {}).get('min_confidence', 0.7)
        self.max_duration = config.get('thresholds', {}).get('max_audio_duration_seconds', 30)

        self._init_engines()

    def _init_engines(self):
        """Initialize STT engines based on configuration."""
        primary_config = self.config.get('primary', {})
        fallback_config = self.config.get('fallback', {})

        # Initialize primary engine
        engine_type = primary_config.get('engine', 'whisper.cpp')
        if engine_type == 'whisper.cpp':
            try:
                from .engines.whisper_cpp import WhisperCppEngine
                self.primary_engine = WhisperCppEngine(primary_config)
                logger.info(f"[STT] Primary engine initialized: {self.primary_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[STT] Failed to initialize Whisper.cpp: {e}")
                # Try fallback as primary
                self._init_fallback_as_primary()

        # Phase 38: Google Cloud STT as primary
        elif engine_type == 'google-cloud-stt':
            try:
                from .engines.google_cloud_stt import GoogleCloudSTTEngine
                self.primary_engine = GoogleCloudSTTEngine(primary_config)
                if self.primary_engine.is_available():
                    logger.info(f"[STT] Primary engine initialized: {self.primary_engine.engine_name}")
                else:
                    logger.warning("[STT] Google Cloud STT not available (check credentials)")
                    self._init_fallback_as_primary()
            except Exception as e:
                logger.warning(f"[STT] Failed to initialize Google Cloud STT: {e}")
                self._init_fallback_as_primary()

        # Initialize fallback engine
        if fallback_config.get('enabled', False):
            fallback_type = fallback_config.get('engine', 'openai-whisper')

            # Phase 38: Support Google Cloud STT as fallback
            if fallback_type == 'google-cloud-stt':
                try:
                    from .engines.google_cloud_stt import GoogleCloudSTTEngine
                    self.fallback_engine = GoogleCloudSTTEngine(fallback_config)
                    if self.fallback_engine.is_available():
                        logger.info(f"[STT] Fallback engine initialized: {self.fallback_engine.engine_name}")
                    else:
                        logger.warning("[STT] Google Cloud STT fallback not available")
                        self.fallback_engine = None
                except Exception as e:
                    logger.warning(f"[STT] Failed to initialize Google Cloud STT fallback: {e}")

            elif fallback_type == 'whisper.cpp':
                try:
                    from .engines.whisper_cpp import WhisperCppEngine
                    self.fallback_engine = WhisperCppEngine(fallback_config)
                    if self.fallback_engine.is_available():
                        logger.info(f"[STT] Fallback engine initialized: {self.fallback_engine.engine_name}")
                    else:
                        logger.warning("[STT] Whisper.cpp fallback not available (model missing)")
                        self.fallback_engine = None
                except Exception as e:
                    logger.warning(f"[STT] Failed to initialize Whisper.cpp fallback: {e}")

    def _init_fallback_as_primary(self):
        """Use fallback engine as primary if primary fails to initialize."""
        fallback_config = self.config.get('fallback', {})
        if fallback_config.get('enabled', False):
            fallback_type = fallback_config.get('engine', 'google-cloud-stt')
            try:
                if fallback_type == 'google-cloud-stt':
                    from .engines.google_cloud_stt import GoogleCloudSTTEngine
                    self.primary_engine = GoogleCloudSTTEngine(fallback_config)
                else:
                    from .engines.whisper_cpp import WhisperCppEngine
                    self.primary_engine = WhisperCppEngine(fallback_config)
                if self.primary_engine.is_available():
                    logger.info("[STT] Using fallback engine as primary")
                else:
                    logger.error("[STT] Fallback engine not available")
                    self.primary_engine = None
            except Exception as e:
                logger.error(f"[STT] Failed to initialize any STT engine: {e}")

    def is_available(self) -> bool:
        """Check if any STT engine is available."""
        if self.primary_engine and self.primary_engine.is_available():
            return True
        if self.fallback_engine and self.fallback_engine.is_available():
            return True
        return False

    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about configured engines."""
        return {
            "primary": {
                "name": self.primary_engine.engine_name if self.primary_engine else None,
                "available": self.primary_engine.is_available() if self.primary_engine else False,
            },
            "fallback": {
                "name": self.fallback_engine.engine_name if self.fallback_engine else None,
                "available": self.fallback_engine.is_available() if self.fallback_engine else False,
                "enabled": self.config.get('fallback', {}).get('enabled', False),
            },
            "confidence_threshold": self.confidence_threshold,
        }

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio with automatic fallback.

        Args:
            audio_data: Raw audio bytes (WAV or other supported format)
            sample_rate: Audio sample rate
            language: Expected language code

        Returns:
            TranscriptionResult with text and confidence
        """
        from .audio_utils import normalize_audio, validate_audio

        # Validate and normalize audio
        try:
            validate_audio(audio_data, max_duration_seconds=self.max_duration)
            normalized_audio = normalize_audio(audio_data, target_sample_rate=16000)
        except Exception as e:
            logger.error(f"[STT] Audio preprocessing failed: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                language=language,
                duration_seconds=0.0,
                engine_used="none",
                is_fallback=False,
            )

        # Try primary engine
        if self.primary_engine and self.primary_engine.is_available():
            try:
                start_time = time.time()
                result = await self.primary_engine.transcribe(
                    normalized_audio,
                    sample_rate=16000,
                    language=language
                )
                result.processing_time_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"[STT] Primary engine result: "
                    f"confidence={result.confidence:.2f}, "
                    f"text_len={len(result.text)}, "
                    f"time={result.processing_time_ms:.0f}ms"
                )

                # If high confidence, return immediately
                if result.is_high_confidence(self.confidence_threshold):
                    return result

                # Low confidence - try fallback if available
                if self.fallback_engine and self.fallback_engine.is_available():
                    logger.info(
                        f"[STT] Low confidence ({result.confidence:.2f}), trying fallback"
                    )
                    fallback_result = await self._try_fallback(normalized_audio, language)

                    # Return better result
                    if fallback_result and fallback_result.confidence > result.confidence:
                        logger.info(
                            f"[STT] Using fallback result: confidence={fallback_result.confidence:.2f}"
                        )
                        return fallback_result

                return result

            except Exception as e:
                logger.error(f"[STT] Primary engine failed: {e}")
                # Fall through to try fallback

        # Try fallback on primary failure
        if self.fallback_engine and self.fallback_engine.is_available():
            fallback_result = await self._try_fallback(normalized_audio, language)
            if fallback_result:
                return fallback_result

        # No engines available or all failed
        logger.error("[STT] All engines failed or unavailable")
        return TranscriptionResult(
            text="",
            confidence=0.0,
            language=language,
            duration_seconds=0.0,
            engine_used="none",
            is_fallback=False,
        )

    async def _try_fallback(
        self,
        audio_data: bytes,
        language: str
    ) -> Optional[TranscriptionResult]:
        """Try transcription with fallback engine."""
        try:
            start_time = time.time()
            result = await self.fallback_engine.transcribe(
                audio_data,
                sample_rate=16000,
                language=language
            )
            result.processing_time_ms = (time.time() - start_time) * 1000
            result.is_fallback = True

            logger.info(
                f"[STT] Fallback engine result: "
                f"confidence={result.confidence:.2f}, "
                f"text_len={len(result.text)}, "
                f"time={result.processing_time_ms:.0f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"[STT] Fallback engine failed: {e}")
            return None
