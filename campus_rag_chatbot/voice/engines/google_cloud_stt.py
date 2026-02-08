"""
Google Cloud Speech-to-Text Engine
==================================

Phase 38: Google Cloud STT Integration

Cloud-based speech-to-text using Google Cloud Speech-to-Text V1.
Designed for the 60-minute monthly free tier with data logging.

Requirements:
- GOOGLE_APPLICATION_CREDENTIALS environment variable (path to service account JSON)
- google-cloud-speech Python package

Configuration:
- Uses "default" model with data logging for free tier eligibility
- Standard recognition (not enhanced) for maximum free tier coverage

Usage:
    engine = GoogleCloudSTTEngine(config)
    if engine.is_available():
        result = await engine.transcribe(audio_data)
"""

import asyncio
import io
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..stt_service import STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)


class GoogleCloudSTTEngine(STTEngine):
    """
    Google Cloud Speech-to-Text V1 engine.

    Uses the Standard model with data logging to maximize free tier usage.
    Free tier: 60 minutes/month of Standard model with data logging.

    Note: Data logging means audio may be used by Google to improve their
    service. This is required for the free tier.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Google Cloud STT engine.

        Args:
            config: Configuration dict with:
                - credentials_path: Path to service account JSON (optional, uses env var if not set)
                - language_code: Language code (default 'en-US')
                - model: Model name (default 'default' for free tier)
                - enable_automatic_punctuation: Add punctuation (default True)
                - enabled: Whether engine is enabled (default True)
        """
        self.config = config
        self.language_code = config.get('language_code', 'en-US')
        self.model = config.get('model', 'default')  # 'default' uses data logging = free tier
        self.enable_punctuation = config.get('enable_automatic_punctuation', True)
        self.enabled = config.get('enabled', True)

        # Get credentials path from config or environment
        self._credentials_path = config.get('credentials_path') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        # Check for google-cloud-speech package
        self._has_package = self._check_package()

        # Validate credentials file exists
        self._credentials_valid = self._validate_credentials()

        # Lazy-loaded client
        self._client = None

        if self.is_available():
            logger.info(f"[GOOGLE-STT] Initialized with model: {self.model}, language: {self.language_code}")
        else:
            reasons = []
            if not self.enabled:
                reasons.append("disabled")
            if not self._has_package:
                reasons.append("google-cloud-speech package not installed")
            if not self._credentials_path:
                reasons.append("GOOGLE_APPLICATION_CREDENTIALS not set")
            elif not self._credentials_valid:
                reasons.append(f"credentials file not found: {self._credentials_path}")
            logger.warning(f"[GOOGLE-STT] Not available: {', '.join(reasons)}")

    def _check_package(self) -> bool:
        """Check if google-cloud-speech package is available."""
        try:
            from google.cloud import speech
            return True
        except ImportError:
            return False

    def _validate_credentials(self) -> bool:
        """Validate that credentials file exists and is readable."""
        if not self._credentials_path:
            return False

        path = Path(self._credentials_path)
        if not path.exists():
            return False

        # Try to read and parse the JSON
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            # Check for required fields in service account JSON
            return 'type' in data and 'project_id' in data
        except (json.JSONDecodeError, IOError):
            return False

    def _get_client(self):
        """Get or create Google Cloud Speech client (lazy initialization)."""
        if self._client is None:
            from google.cloud import speech

            # Set credentials path in environment for the client
            if self._credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self._credentials_path

            self._client = speech.SpeechClient()
            logger.info("[GOOGLE-STT] Speech client initialized")

        return self._client

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return "google-cloud-stt"

    def is_available(self) -> bool:
        """Check if engine is available."""
        return (
            self.enabled and
            self._has_package and
            self._credentials_path is not None and
            self._credentials_valid
        )

    def reload_credentials(self) -> bool:
        """
        Reload credentials from file (for hot reload support).

        Returns:
            True if credentials are valid after reload
        """
        # Re-read credentials path from environment
        self._credentials_path = self.config.get('credentials_path') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self._credentials_valid = self._validate_credentials()

        # Reset client to force re-initialization
        self._client = None

        logger.info(f"[GOOGLE-STT] Credentials reloaded. Valid: {self._credentials_valid}")
        return self._credentials_valid

    def get_project_id(self) -> Optional[str]:
        """
        Get project ID from credentials file.

        Returns:
            Project ID string or None if not available
        """
        if not self._credentials_path:
            return None

        try:
            with open(self._credentials_path, 'r') as f:
                data = json.load(f)
            return data.get('project_id')
        except (json.JSONDecodeError, IOError):
            return None

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio using Google Cloud Speech-to-Text API.

        Args:
            audio_data: WAV audio bytes (16kHz mono recommended)
            sample_rate: Audio sample rate
            language: Language code (used to set language_code if different from config)

        Returns:
            TranscriptionResult with transcription and confidence
        """
        if not self.is_available():
            raise RuntimeError("Google Cloud STT engine not available")

        start_time = asyncio.get_event_loop().time()

        try:
            from google.cloud import speech

            # Get audio duration from WAV header
            import wave
            with io.BytesIO(audio_data) as f:
                with wave.open(f, 'rb') as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / rate if rate > 0 else 0.0

            # Prepare audio content
            audio = speech.RecognitionAudio(content=audio_data)

            # Map simple language code to full code
            lang_code = self._map_language_code(language)

            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code=lang_code,
                model=self.model,
                use_enhanced=False,  # Standard model for free tier
                enable_automatic_punctuation=self.enable_punctuation,
                # Enable data logging for free tier
                # Note: This is implicit with 'default' model
            )

            # Run synchronous API call in thread pool
            loop = asyncio.get_event_loop()
            client = self._get_client()

            response = await loop.run_in_executor(
                None,
                lambda: client.recognize(config=config, audio=audio)
            )

            # Process response
            text = ""
            confidence = 0.0
            segments = []

            for result in response.results:
                if result.alternatives:
                    best_alt = result.alternatives[0]
                    text += best_alt.transcript + " "
                    # Google provides confidence per result
                    if best_alt.confidence > 0:
                        confidence = max(confidence, best_alt.confidence)
                    segments.append({
                        "text": best_alt.transcript,
                        "confidence": best_alt.confidence
                    })

            text = text.strip()

            # If no confidence provided, estimate
            if confidence == 0.0:
                confidence = self._estimate_confidence(text)

            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

            logger.info(f"[GOOGLE-STT] Transcribed {duration:.2f}s audio: '{text[:50]}...' (confidence: {confidence:.2f})")

            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=duration,
                engine_used=self.engine_name,
                processing_time_ms=processing_time,
                raw_segments=segments if segments else None
            )

        except Exception as e:
            logger.error(f"[GOOGLE-STT] Transcription failed: {e}")
            raise

    def _map_language_code(self, lang: str) -> str:
        """
        Map simple language code to Google's full language code.

        Args:
            lang: Simple language code (e.g., 'en', 'fil')

        Returns:
            Full language code (e.g., 'en-US', 'fil-PH')
        """
        mapping = {
            'en': 'en-US',
            'fil': 'fil-PH',
            'tl': 'fil-PH',  # Tagalog alias
            'es': 'es-ES',
            'fr': 'fr-FR',
            'de': 'de-DE',
            'ja': 'ja-JP',
            'ko': 'ko-KR',
            'zh': 'zh-CN',
        }

        # If already a full code, use as-is
        if '-' in lang:
            return lang

        return mapping.get(lang.lower(), self.language_code)

    def _estimate_confidence(self, text: str) -> float:
        """
        Estimate confidence when API doesn't provide one.

        Args:
            text: Transcribed text

        Returns:
            Estimated confidence (0.0-1.0)
        """
        if not text or not text.strip():
            return 0.0

        # Base confidence for cloud API
        confidence = 0.85

        # Penalize very short transcriptions
        words = text.split()
        if len(words) < 2:
            confidence -= 0.2

        # Penalize if text has uncertainty markers
        uncertainty_markers = ['[', ']', '...', '(?)']
        for marker in uncertainty_markers:
            if marker in text:
                confidence -= 0.1

        return max(0.1, min(1.0, confidence))
