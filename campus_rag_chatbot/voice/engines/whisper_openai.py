"""
OpenAI Whisper STT Engine
=========================

Phase 32: Voice Infrastructure Foundation

Cloud-based speech-to-text using OpenAI Whisper API.
Used as fallback when offline transcription confidence is low.

Requirements:
- OPENAI_API_KEY environment variable
- openai Python package

Usage:
    engine = WhisperOpenAIEngine(config)
    if engine.is_available():
        result = await engine.transcribe(audio_data)
"""

import asyncio
import io
import os
import logging
from typing import Dict, Any

from ..stt_service import STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperOpenAIEngine(STTEngine):
    """
    OpenAI Whisper API engine for cloud-based transcription.

    Used as fallback when offline confidence is low or offline
    engine is unavailable.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenAI Whisper engine.

        Args:
            config: Configuration dict with:
                - model: Model name (default 'whisper-1')
                - enabled: Whether fallback is enabled
        """
        self.config = config
        self.model = config.get('model', 'whisper-1')
        self.enabled = config.get('enabled', False)

        # Check for API key
        self._api_key = os.getenv('OPENAI_API_KEY')

        # Check for openai package
        self._has_openai = self._check_openai_package()

        if self.is_available():
            logger.info("[WHISPER-OPENAI] Cloud fallback initialized")

    def _check_openai_package(self) -> bool:
        """Check if openai package is available."""
        try:
            import openai
            return True
        except ImportError:
            return False

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return "openai-whisper"

    def is_available(self) -> bool:
        """Check if engine is available."""
        return (
            self.enabled and
            self._has_openai and
            self._api_key is not None
        )

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio using OpenAI Whisper API.

        Args:
            audio_data: WAV audio bytes
            sample_rate: Sample rate (not used, API handles resampling)
            language: Language code

        Returns:
            TranscriptionResult with transcription
        """
        if not self.is_available():
            raise RuntimeError("OpenAI Whisper engine not available")

        try:
            import openai
            from openai import AsyncOpenAI

            # Get audio duration
            import wave
            with io.BytesIO(audio_data) as f:
                with wave.open(f, 'rb') as wav:
                    duration = wav.getnframes() / wav.getframerate()

            # Create client
            client = AsyncOpenAI(api_key=self._api_key)

            # Create file-like object for API
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            # Call API
            response = await client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
                response_format="verbose_json",  # Get detailed response
            )

            # Extract text and confidence
            text = response.text.strip()

            # OpenAI doesn't provide confidence, but we can estimate
            # based on response characteristics
            confidence = self._estimate_confidence(response)

            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        except Exception as e:
            logger.error(f"[WHISPER-OPENAI] Transcription failed: {e}")
            raise

    def _estimate_confidence(self, response) -> float:
        """
        Estimate confidence from API response.

        OpenAI Whisper API doesn't provide confidence scores,
        so we estimate based on response characteristics.
        """
        # Default high confidence for cloud API
        confidence = 0.9

        text = response.text if hasattr(response, 'text') else str(response)

        # Penalize if text is empty or very short
        if not text or len(text.split()) < 2:
            confidence -= 0.3

        # Check for potential issues in transcription
        if '[' in text or ']' in text:  # Bracketed annotations
            confidence -= 0.1

        return max(0.1, min(1.0, confidence))
