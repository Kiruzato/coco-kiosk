"""
Edge TTS Engine
===============

Phase 32: Voice Infrastructure Foundation

Text-to-speech using Microsoft Edge's TTS service via edge-tts library.
Works on all platforms without system dependencies.

Note: Requires internet connection (not offline-capable).

Usage:
    engine = EdgeTTSEngine(config)
    if engine.is_available():
        result = await engine.synthesize("Hello world")
"""

import asyncio
import io
import logging
from typing import Dict, Any, Optional

from ..tts_service import TTSEngine, SynthesisResult

logger = logging.getLogger(__name__)


class EdgeTTSEngine(TTSEngine):
    """
    Edge TTS engine using Microsoft's online TTS service.

    Works on Windows/Linux/Mac without additional system dependencies.
    Requires internet connection.
    """

    # Available voices (subset of most natural sounding)
    VOICES = {
        'en-US-JennyNeural': 'Female, American English',
        'en-US-GuyNeural': 'Male, American English',
        'en-US-AriaNeural': 'Female, American English (conversational)',
        'en-GB-SoniaNeural': 'Female, British English',
        'en-PH-RosaNeural': 'Female, Philippine English',
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Edge TTS engine.

        Args:
            config: Configuration dict with:
                - voice: Voice name (default: en-US-JennyNeural)
                - rate: Speaking rate adjustment (e.g., "+10%", "-20%")
                - pitch: Pitch adjustment (e.g., "+5Hz", "-10Hz")
        """
        self.config = config
        self.voice = config.get('voice', 'en-US-JennyNeural')
        self.rate = config.get('rate', '+0%')
        self.pitch = config.get('pitch', '+0Hz')

        # Check if edge-tts is available
        self._has_edge_tts = self._check_edge_tts()

        if self._has_edge_tts:
            logger.info(f"[EDGE-TTS] Initialized with voice: {self.voice}")

    def _check_edge_tts(self) -> bool:
        """Check if edge-tts package is available."""
        try:
            import edge_tts
            return True
        except ImportError:
            logger.warning("[EDGE-TTS] edge-tts package not installed")
            return False

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return f"edge-tts ({self.voice})"

    def is_available(self) -> bool:
        """Check if engine is available."""
        return self._has_edge_tts

    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech using Edge TTS.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with MP3 audio data (converted to WAV)
        """
        if not self.is_available():
            raise RuntimeError("Edge TTS engine not available")

        try:
            import edge_tts

            # Create communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch
            )

            # Collect audio data
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            if not audio_chunks:
                raise RuntimeError("No audio generated")

            # Combine all chunks (MP3 format)
            mp3_data = b''.join(audio_chunks)

            # Convert MP3 to WAV for consistency
            wav_data, duration = self._convert_mp3_to_wav(mp3_data)

            return SynthesisResult(
                audio_data=wav_data,
                format='wav',
                sample_rate=22050,  # After conversion
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        except Exception as e:
            logger.error(f"[EDGE-TTS] Synthesis failed: {e}")
            raise

    def _convert_mp3_to_wav(self, mp3_data: bytes) -> tuple:
        """Convert MP3 audio to WAV format."""
        try:
            from pydub import AudioSegment
            import wave

            # Load MP3 data
            mp3_buffer = io.BytesIO(mp3_data)
            audio = AudioSegment.from_mp3(mp3_buffer)

            # Convert to mono 22050Hz for consistency with Piper
            audio = audio.set_frame_rate(22050).set_channels(1)

            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format='wav')

            # Get duration
            duration = len(audio) / 1000.0  # pydub uses milliseconds

            wav_buffer.seek(0)
            return wav_buffer.read(), duration

        except ImportError:
            logger.warning("[EDGE-TTS] pydub not available, returning MP3 directly")
            # If pydub isn't available, return MP3 directly
            # Estimate duration (rough estimate based on typical speech rate)
            estimated_duration = len(mp3_data) / 16000  # Very rough estimate
            return mp3_data, estimated_duration
        except Exception as e:
            logger.error(f"[EDGE-TTS] MP3 to WAV conversion failed: {e}")
            raise
