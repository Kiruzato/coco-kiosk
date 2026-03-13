"""
Text-to-Speech Service
======================

Phase 32: Voice Infrastructure Foundation

Provides text-to-speech synthesis with automatic engine fallback.

Features:
- Text optimization for natural speech
- Response length limiting
- Abbreviation expansion
- Automatic fallback on primary engine failure

Supported Engines:
- Piper TTS (primary, offline)
- espeak-ng (fallback, offline)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging
import time
import re

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis."""
    audio_data: bytes
    format: str  # 'wav', 'mp3', 'ogg'
    sample_rate: int
    duration_seconds: float
    engine_used: str
    processing_time_ms: float = 0.0
    text_length: int = 0

    def is_empty(self) -> bool:
        """Check if synthesis produced no audio."""
        return len(self.audio_data) == 0


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with audio data
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


class TTSService:
    """
    Text-to-Speech service with response optimization.

    Features:
    - Sentence-level streaming (optional)
    - Response shortening for very long answers
    - SSML support for natural prosody
    """

    # Abbreviation expansion is now handled by tts_text_preprocessor module
    # for context-aware processing (e.g., "St." → "Saint" vs "Street")

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize TTS service with configuration.

        Args:
            config: TTS configuration dict with 'primary', 'fallback', 'max_chars'
        """
        self.config = config
        self.primary_engine: Optional[TTSEngine] = None
        self.fallback_engine: Optional[TTSEngine] = None
        self.max_chars = config.get('max_chars', 500)

        self._init_engines()

    def _init_engines(self):
        """Initialize TTS engines based on configuration."""
        primary_config = self.config.get('primary', {})
        fallback_config = self.config.get('fallback', {})

        # Initialize primary engine based on configured type
        engine_type = primary_config.get('engine', 'piper')

        if engine_type == 'piper':
            try:
                from .engines.piper_tts import PiperTTSEngine
                self.primary_engine = PiperTTSEngine(primary_config)
                logger.info(f"[TTS] Primary engine initialized: {self.primary_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize Piper: {e}")

        else:
            logger.warning(f"[TTS] Unknown engine type: {engine_type}")

        # Initialize fallback engine
        fallback_type = fallback_config.get('engine', 'espeak-ng')

        # Skip if fallback is same as primary
        if fallback_type == engine_type:
            logger.info(f"[TTS] Fallback engine '{fallback_type}' is same as primary, skipping fallback init")
        elif fallback_type == 'espeak-ng':
            try:
                from .engines.espeak_tts import EspeakTTSEngine
                self.fallback_engine = EspeakTTSEngine(fallback_config)
                logger.info(f"[TTS] Fallback engine initialized: {self.fallback_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize espeak-ng fallback: {e}")
        elif fallback_type == 'piper':
            try:
                from .engines.piper_tts import PiperTTSEngine
                self.fallback_engine = PiperTTSEngine(fallback_config)
                logger.info(f"[TTS] Fallback engine initialized: {self.fallback_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize piper fallback: {e}")

    def is_available(self) -> bool:
        """Check if any TTS engine is available."""
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
            },
            "max_chars": self.max_chars,
        }

    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with audio data
        """
        if not text or not text.strip():
            return SynthesisResult(
                audio_data=b'',
                format='wav',
                sample_rate=22050,
                duration_seconds=0.0,
                engine_used='none',
                text_length=0,
            )

        # Optimize text for speech (non-fatal — falls back to raw text)
        try:
            optimized_text = self._optimize_for_speech(text)
        except Exception as e:
            logger.warning(f"[TTS] Text optimization failed, using raw text: {e}")
            optimized_text = text

        # Try primary engine
        if self.primary_engine and self.primary_engine.is_available():
            try:
                start_time = time.time()
                result = await self.primary_engine.synthesize(optimized_text)
                result.processing_time_ms = (time.time() - start_time) * 1000
                result.text_length = len(optimized_text)

                logger.info(
                    f"[TTS] Synthesized {len(optimized_text)} chars "
                    f"in {result.processing_time_ms:.0f}ms "
                    f"({result.duration_seconds:.1f}s audio)"
                )
                return result

            except Exception as e:
                logger.error(f"[TTS] Primary engine failed: {e}")

        # Try fallback engine
        if self.fallback_engine and self.fallback_engine.is_available():
            try:
                start_time = time.time()
                result = await self.fallback_engine.synthesize(optimized_text)
                result.processing_time_ms = (time.time() - start_time) * 1000
                result.text_length = len(optimized_text)

                logger.info(f"[TTS] Fallback synthesized: {result.duration_seconds:.1f}s")
                return result

            except Exception as e:
                logger.error(f"[TTS] Fallback engine failed: {e}")

        # All engines failed
        logger.error("[TTS] All engines failed or unavailable")
        return SynthesisResult(
            audio_data=b'',
            format='wav',
            sample_rate=22050,
            duration_seconds=0.0,
            engine_used='none',
            text_length=len(text),
        )

    def _optimize_for_speech(self, text: str) -> str:
        """
        Optimize text for natural speech output.

        - Remove markdown formatting
        - Expand abbreviations (context-aware)
        - Expand numbered lists for natural reading

        Note: Text is no longer truncated - TTS reads the entire response.
        """
        # Remove markdown formatting
        text = self._strip_markdown(text)

        # Context-aware abbreviation expansion (safe — falls back to original on error)
        try:
            from .tts_text_preprocessor import preprocess_for_tts
            text = preprocess_for_tts(text)
        except Exception as e:
            logger.warning(f"[TTS] Preprocessing failed, using text as-is: {e}")

        # Expand numbered lists for natural reading
        text = self._expand_numbered_lists(text)

        # Clean up whitespace
        text = ' '.join(text.split())

        return text

    def _strip_markdown(self, text: str) -> str:
        """Remove markdown formatting from text."""
        # Remove bold/italic markers
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # Remove headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

        # Remove bullet points but keep content
        text = re.sub(r'^[\*\-•]\s*', '', text, flags=re.MULTILINE)

        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        return text

    def _expand_numbered_lists(self, text: str) -> str:
        """Expand numbered lists for natural reading."""
        # Convert "1. Item" to "Number one: Item"
        def replace_number(match):
            num = int(match.group(1))
            ordinals = {
                1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth', 5: 'Fifth',
                6: 'Sixth', 7: 'Seventh', 8: 'Eighth', 9: 'Ninth', 10: 'Tenth'
            }
            return ordinals.get(num, f'Number {num}') + ': '

        text = re.sub(r'^(\d+)\.\s*', replace_number, text, flags=re.MULTILINE)
        return text

