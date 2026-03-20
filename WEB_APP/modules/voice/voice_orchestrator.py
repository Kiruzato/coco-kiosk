"""
Voice Orchestrator
==================

Phase 32: Voice Infrastructure Foundation

Coordinates voice interactions: STT -> Chat -> TTS

Key principle: Voice is a MODALITY LAYER, not a decision layer.
All grounding, confidence, and determinism rules flow through
the existing /chat API unchanged.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable
import logging
import time

from .stt_service import STTService, TranscriptionResult
from .tts_service import TTSService, SynthesisResult

# Phase 46: Import input preprocessor for STT artifact cleanup
try:
    from WEB_APP.modules.input_preprocessor import preprocess_input
except ImportError:
    # Fallback if module not found
    def preprocess_input(text, source="text"):
        return text

# Unified offline error handling
try:
    from WEB_APP.modules.response_orchestrator import OFFLINE_MESSAGE, is_network_error
except ImportError:
    OFFLINE_MESSAGE = "It looks like there's no internet connection. I'm unable to process your request right now."
    def is_network_error(exc):
        msg = str(exc).lower()
        return any(kw in msg for kw in ("connection", "timeout", "timed out", "network", "unreachable"))

logger = logging.getLogger(__name__)


@dataclass
class VoiceInteractionResult:
    """Complete result of a voice interaction."""

    # STT phase
    transcription: Optional[TranscriptionResult] = None
    transcription_success: bool = False

    # Chat phase (from existing /chat)
    chat_response: Optional[Dict[str, Any]] = None
    chat_success: bool = False

    # TTS phase
    synthesis: Optional[SynthesisResult] = None
    synthesis_success: bool = False

    # Timing
    total_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    chat_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0

    # Error info
    error_message: Optional[str] = None
    requires_text_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "transcription": {
                "text": self.transcription.text if self.transcription else "",
                "confidence": self.transcription.confidence if self.transcription else 0.0,
                "language": self.transcription.language if self.transcription else "en",
                "engine": self.transcription.engine_used if self.transcription else None,
            } if self.transcription else None,
            "transcription_success": self.transcription_success,
            "chat_response": self.chat_response,
            "chat_success": self.chat_success,
            "synthesis_success": self.synthesis_success,
            "latency_ms": {
                "stt": self.stt_latency_ms,
                "chat": self.chat_latency_ms,
                "tts": self.tts_latency_ms,
                "total": self.total_latency_ms,
            },
            "error_message": self.error_message,
            "requires_text_fallback": self.requires_text_fallback,
        }


class VoiceOrchestrator:
    """
    Orchestrates voice interactions while preserving RAG guarantees.

    Key principle: Voice is a MODALITY LAYER, not a decision layer.
    All grounding, confidence, and determinism rules flow through
    the existing /chat API unchanged.
    """

    def __init__(
        self,
        stt_service: STTService,
        tts_service: TTSService,
        chat_handler: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
        event_tracker: Optional[Any] = None
    ):
        """
        Initialize voice orchestrator.

        Args:
            stt_service: Speech-to-text service
            tts_service: Text-to-speech service
            chat_handler: Async function to handle chat (receives message, session_id)
            event_tracker: EventTracker for logging (optional)
        """
        self.stt = stt_service
        self.tts = tts_service
        self.chat_handler = chat_handler
        self.event_tracker = event_tracker

    def set_chat_handler(self, handler: Callable[..., Awaitable[Dict[str, Any]]]):
        """Set the chat handler function."""
        self.chat_handler = handler

    def is_available(self) -> bool:
        """Check if voice services are available."""
        return self.stt.is_available()  # TTS is optional

    def get_status(self) -> Dict[str, Any]:
        """Get status of voice services."""
        return {
            "stt": self.stt.get_engine_info(),
            "tts": self.tts.get_engine_info(),
            "available": self.is_available(),
        }

    async def transcribe_only(
        self,
        audio_data: bytes,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio without chat or TTS.

        Args:
            audio_data: Raw audio bytes
            language: Language code

        Returns:
            TranscriptionResult
        """
        return await self.stt.transcribe(audio_data, language=language)

    async def synthesize_only(self, text: str) -> SynthesisResult:
        """
        Synthesize text without STT or chat.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult
        """
        return await self.tts.synthesize(text)

    async def process_voice_interaction(
        self,
        audio_data: bytes,
        session_id: str = "default",
        skip_tts: bool = False,
        language: str = "en"
    ) -> VoiceInteractionResult:
        """
        Process complete voice interaction: STT -> Chat -> TTS

        This method:
        1. Transcribes audio to text (STT)
        2. Sends text through EXISTING chat pipeline (preserves all guarantees)
        3. Synthesizes response to audio (TTS)

        The chat pipeline is untouched - voice is purely I/O transformation.

        Args:
            audio_data: Raw audio bytes
            session_id: Session ID for chat context
            skip_tts: Skip TTS synthesis
            language: Language code

        Returns:
            VoiceInteractionResult with all phases
        """
        start_time = time.time()
        result = VoiceInteractionResult()

        # ========================================
        # Phase 1: Speech-to-Text
        # ========================================
        stt_start = time.time()
        try:
            transcription = await self.stt.transcribe(audio_data, language=language)
            result.transcription = transcription
            result.transcription_success = True
            result.stt_latency_ms = (time.time() - stt_start) * 1000

            logger.info(
                f"[VOICE] STT complete: "
                f"confidence={transcription.confidence:.2f}, "
                f"text='{transcription.text[:50]}...'" if len(transcription.text) > 50
                else f"[VOICE] STT complete: confidence={transcription.confidence:.2f}, text='{transcription.text}'"
            )

            # Check confidence threshold
            if not transcription.is_high_confidence():
                logger.warning(f"[VOICE] Low STT confidence: {transcription.confidence:.2f}")
                result.requires_text_fallback = True
                # Still continue - let frontend decide whether to prompt for confirmation

            # Check for empty transcription
            if transcription.is_empty():
                logger.warning("[VOICE] Empty transcription - no speech detected")
                result.error_message = "No speech detected. Please try again."
                result.total_latency_ms = (time.time() - start_time) * 1000
                self._log_voice_event(result, session_id)
                return result

        except Exception as e:
            logger.error(f"[VOICE] STT failed: {e}")
            if is_network_error(e):
                logger.warning("[VOICE] Network error during STT — returning offline message")
                result.error_message = OFFLINE_MESSAGE
            else:
                result.error_message = f"Could not understand audio: {str(e)}"
            result.stt_latency_ms = (time.time() - stt_start) * 1000
            result.total_latency_ms = (time.time() - start_time) * 1000
            self._log_voice_event(result, session_id)
            return result

        # ========================================
        # Phase 2: Chat (EXISTING PIPELINE - UNCHANGED)
        # ========================================
        if self.chat_handler is None:
            logger.warning("[VOICE] No chat handler configured")
            result.error_message = "Chat service not configured"
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result

        chat_start = time.time()
        try:
            # Phase 46: Preprocess STT output before sending to chat
            # Cleans up number formatting, operator artifacts, etc.
            preprocessed_text = preprocess_input(transcription.text, source="voice")
            if preprocessed_text != transcription.text:
                logger.info(
                    f"[VOICE] Preprocessed: '{transcription.text[:50]}' -> '{preprocessed_text[:50]}'"
                )

            # Call existing chat handler with preprocessed text
            # This preserves ALL grounding, confidence, and determinism rules
            chat_response = await self.chat_handler(
                message=preprocessed_text,
                session_id=session_id
            )
            result.chat_response = chat_response
            result.chat_success = True
            result.chat_latency_ms = (time.time() - chat_start) * 1000

            logger.info(
                f"[VOICE] Chat complete: "
                f"mode={chat_response.get('mode', 'unknown')}, "
                f"confidence={chat_response.get('confidence', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"[VOICE] Chat failed: {e}")
            if is_network_error(e):
                logger.warning("[VOICE] Network error during chat — returning offline message")
                result.error_message = OFFLINE_MESSAGE
            else:
                result.error_message = f"Could not process question: {str(e)}"
            result.chat_latency_ms = (time.time() - chat_start) * 1000
            result.total_latency_ms = (time.time() - start_time) * 1000
            self._log_voice_event(result, session_id)
            return result

        # ========================================
        # Phase 3: Text-to-Speech
        # ========================================
        if not skip_tts and self.tts.is_available():
            tts_start = time.time()
            try:
                # Get the answer text for synthesis
                answer_text = chat_response.get('answer', '')

                # Don't synthesize if rejected or no answer
                if answer_text and not chat_response.get('rejected', False):
                    synthesis = await self.tts.synthesize(answer_text)
                    result.synthesis = synthesis
                    result.synthesis_success = True

                    logger.info(
                        f"[VOICE] TTS complete: "
                        f"duration={synthesis.duration_seconds:.1f}s, "
                        f"engine={synthesis.engine_used}"
                    )

            except Exception as e:
                logger.warning(f"[VOICE] TTS failed (non-fatal): {e}")
                # TTS failure is non-fatal - text answer still available

            result.tts_latency_ms = (time.time() - tts_start) * 1000

        result.total_latency_ms = (time.time() - start_time) * 1000

        # Log voice interaction event
        self._log_voice_event(result, session_id)

        return result

    def _log_voice_event(self, result: VoiceInteractionResult, session_id: str):
        """Log voice interaction for analytics."""
        if self.event_tracker is None:
            return

        try:
            # Import EventType here to avoid circular import
            from WEB_APP.modules.event_tracker import EventType
            self.event_tracker.track(
                event_type=EventType.VOICE_INTERACTION,
                session_id=session_id,
                stt_success=result.transcription_success,
                stt_confidence=result.transcription.confidence if result.transcription else None,
                stt_engine=result.transcription.engine_used if result.transcription else None,
                chat_success=result.chat_success,
                chat_mode=result.chat_response.get('mode') if result.chat_response else None,
                tts_success=result.synthesis_success,
                total_latency_ms=result.total_latency_ms,
                requires_text_fallback=result.requires_text_fallback,
                has_error=result.error_message is not None,
            )
        except Exception as e:
            logger.warning(f"[VOICE] Failed to log event: {e}")
