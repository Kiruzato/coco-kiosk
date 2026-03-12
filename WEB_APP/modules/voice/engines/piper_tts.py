"""
Piper TTS Engine
================

Phase 32: Voice Infrastructure Foundation

Offline text-to-speech using Piper TTS.
High-quality neural TTS optimized for Raspberry Pi.

Requirements:
- piper-tts Python package
- Voice model files (.onnx and .onnx.json)

Usage:
    engine = PiperTTSEngine(config)
    if engine.is_available():
        result = await engine.synthesize("Hello world")
"""

import asyncio
import io
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..tts_service import TTSEngine, SynthesisResult

logger = logging.getLogger(__name__)


class PiperTTSEngine(TTSEngine):
    """
    Piper TTS engine for offline speech synthesis.

    Uses ONNX neural network models for high-quality speech.
    Optimized for ARM64 (Raspberry Pi 5).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Piper TTS engine.

        Args:
            config: Configuration dict with:
                - model_path: Path to .onnx model file
                - config_path: Path to .onnx.json config file (optional)
                - voice: Voice name (for logging)
                - sample_rate: Output sample rate (default 22050)
                - speaker_id: Speaker ID for multi-speaker models
        """
        self.config = config
        self.model_path = Path(config.get('model_path', ''))
        self.config_path = Path(config.get('config_path', ''))
        self.voice_name = config.get('voice', 'default')
        self.sample_rate = config.get('sample_rate', 22050)
        self.speaker_id = config.get('speaker_id', 0)

        # Check for piper package
        self._has_piper = self._check_piper_package()
        self._voice = None

        if self.is_available():
            logger.info(f"[PIPER] Initialized with voice: {self.voice_name}")
        else:
            if not self._has_piper:
                logger.warning("[PIPER] piper-tts package not installed (pip install piper-tts)")
            if not self.model_path.exists():
                logger.warning(f"[PIPER] Model file not found: {self.model_path}")

    def _check_piper_package(self) -> bool:
        """Check if piper-tts package is available."""
        try:
            from piper import PiperVoice
            return True
        except ImportError:
            return False

    def _load_voice(self):
        """Lazy load the voice model."""
        if self._voice is not None:
            return

        try:
            from piper import PiperVoice

            # Load voice
            self._voice = PiperVoice.load(
                str(self.model_path),
                config_path=str(self.config_path) if self.config_path.exists() else None
            )
            logger.info(f"[PIPER] Voice loaded: {self.model_path}")

        except Exception as e:
            logger.error(f"[PIPER] Failed to load voice: {e}")
            self._voice = None

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return f"piper ({self.voice_name})"

    def is_available(self) -> bool:
        """Check if engine is available."""
        return self._has_piper and self.model_path.exists()

    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech using Piper.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with WAV audio data
        """
        if not self.is_available():
            raise RuntimeError("Piper TTS engine not available")

        # Lazy load voice
        if self._voice is None:
            self._load_voice()

        if self._voice is None:
            raise RuntimeError("Failed to load Piper voice model")

        try:
            # Run synthesis in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            audio_data, duration = await loop.run_in_executor(
                None,
                self._synthesize_sync,
                text
            )

            return SynthesisResult(
                audio_data=audio_data,
                format='wav',
                sample_rate=self.sample_rate,
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        except Exception as e:
            logger.error(f"[PIPER] Synthesis failed: {e}")
            raise

    def _synthesize_sync(self, text: str) -> tuple:
        """Synchronous synthesis (runs in thread pool)."""
        import wave

        # Create WAV buffer
        wav_buffer = io.BytesIO()

        # Get audio parameters from Piper voice config
        # Piper models are mono (1 channel), 16-bit (2 bytes sample width)
        channels = 1
        sample_width = 2  # 16-bit audio
        # Get sample rate from voice config, fallback to configured value
        sample_rate = getattr(self._voice.config, 'sample_rate', self.sample_rate)

        # synthesize_wav expects a wave.Wave_write object with parameters set
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            self._voice.synthesize_wav(text, wav_file)

        # Get duration from WAV
        wav_buffer.seek(0)
        with wave.open(wav_buffer, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / rate if rate > 0 else 0.0

        wav_buffer.seek(0)
        audio_data = wav_buffer.read()

        return audio_data, duration
