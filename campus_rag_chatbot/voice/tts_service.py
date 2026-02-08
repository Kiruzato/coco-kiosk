"""
Text-to-Speech Service
======================

Phase 32: Voice Infrastructure Foundation
Phase 37: Edge-TTS as selectable primary engine

Provides text-to-speech synthesis with automatic engine fallback.

Features:
- Text optimization for natural speech
- Response length limiting
- Abbreviation expansion
- Automatic fallback on primary engine failure

Supported Engines (Phase 37):
- Piper TTS (primary, offline)
- Edge-TTS (primary or fallback, free)
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

    # Common abbreviations to expand for speech
    ABBREVIATIONS = {
        'Dr.': 'Doctor',
        'Engr.': 'Engineer',
        'Atty.': 'Attorney',
        'Prof.': 'Professor',
        'Bldg.': 'Building',
        'Rm.': 'Room',
        'Flr.': 'Floor',
        'St.': 'Street',
        'Ave.': 'Avenue',
        'vs.': 'versus',
        'etc.': 'etcetera',
        'e.g.': 'for example',
        'i.e.': 'that is',
        'CCIT': 'C C I T',  # Spell out acronyms
        'CABEIHM': 'CABEIHM',  # Leave complex acronyms as-is
        'CoCo': 'Coco',  # Pronounce as word
    }

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

        # Phase 37: Support edge-tts as primary engine
        elif engine_type == 'edge-tts':
            try:
                from .engines.edge_tts import EdgeTTSEngine
                self.primary_engine = EdgeTTSEngine(primary_config)
                logger.info(f"[TTS] Primary engine initialized: {self.primary_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize Edge TTS as primary: {e}")

        # Phase 37: Log warning for non-selectable engines
        elif engine_type == 'openai-tts':
            logger.warning("[TTS] OpenAI TTS is not supported as primary engine (paid cloud service)")

        else:
            logger.warning(f"[TTS] Unknown engine type: {engine_type}")

        # Initialize fallback engine
        fallback_type = fallback_config.get('engine', 'edge-tts')

        # Phase 37: Skip if fallback is same as primary
        if fallback_type == engine_type:
            logger.info(f"[TTS] Fallback engine '{fallback_type}' is same as primary, skipping fallback init")
        elif fallback_type == 'espeak-ng':
            try:
                from .engines.espeak_tts import EspeakTTSEngine
                self.fallback_engine = EspeakTTSEngine(fallback_config)
                logger.info(f"[TTS] Fallback engine initialized: {self.fallback_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize espeak-ng fallback: {e}")
        elif fallback_type == 'edge-tts':
            try:
                from .engines.edge_tts import EdgeTTSEngine
                self.fallback_engine = EdgeTTSEngine(fallback_config)
                logger.info(f"[TTS] Fallback engine initialized: {self.fallback_engine.engine_name}")
            except Exception as e:
                logger.warning(f"[TTS] Failed to initialize edge-tts fallback: {e}")
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

        # Optimize text for speech
        optimized_text = self._optimize_for_speech(text)

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

        - Truncate very long responses
        - Expand abbreviations
        - Remove markdown formatting
        - Add pauses at appropriate points
        """
        # Remove markdown formatting
        text = self._strip_markdown(text)

        # Expand abbreviations
        for abbr, expansion in self.ABBREVIATIONS.items():
            text = text.replace(abbr, expansion)

        # Expand numbered lists for natural reading
        text = self._expand_numbered_lists(text)

        # Truncate if too long
        if len(text) > self.max_chars:
            text = self._truncate_at_sentence(text)

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

    def _truncate_at_sentence(self, text: str) -> str:
        """Truncate text at a sentence boundary."""
        truncated = text[:self.max_chars]

        # Find last sentence boundary
        last_period = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )

        # Only truncate at sentence if we're keeping at least half the content
        if last_period > self.max_chars * 0.5:
            truncated = truncated[:last_period + 1]

        return truncated + " For more details, please see the screen."
