"""
Whisper.cpp STT Engine
======================

Phase 32: Voice Infrastructure Foundation

Offline speech-to-text using whisper.cpp.
Optimized for Raspberry Pi 5 with ARM64 NEON SIMD instructions.

Requirements:
- whisper.cpp compiled for the target platform
- Model file (e.g., ggml-tiny.en.bin)

Usage:
    engine = WhisperCppEngine(config)
    if engine.is_available():
        result = await engine.transcribe(audio_data)
"""

import asyncio
import subprocess
import tempfile
import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ..stt_service import STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperCppEngine(STTEngine):
    """
    Whisper.cpp STT engine for offline transcription.

    Uses the whisper.cpp command-line interface for transcription.
    Can be configured to use the Python bindings (pywhispercpp) if available.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Whisper.cpp engine.

        Args:
            config: Configuration dict with:
                - model_path: Path to .bin model file
                - threads: Number of CPU threads (default 4)
                - language: Language code (default 'en')
                - beam_size: Beam search size (default 5)
        """
        self.config = config
        self.model_path = Path(config.get('model_path', ''))
        self.threads = config.get('threads', 4)
        self.language = config.get('language', 'en')
        self.beam_size = config.get('beam_size', 5)

        # Try to find whisper.cpp executable
        self.executable = self._find_executable()

        # Check for Python bindings
        self._has_python_bindings = self._check_python_bindings()

        if self.is_available():
            logger.info(f"[WHISPER] Initialized with model: {self.model_path}")
        else:
            logger.warning("[WHISPER] Engine not available - model or executable missing")

    def _find_executable(self) -> Optional[Path]:
        """Find whisper.cpp executable."""
        # Common locations to check
        possible_paths = [
            Path('/usr/local/bin/whisper'),
            Path('/usr/bin/whisper'),
            Path.home() / 'whisper.cpp' / 'main',
            Path.home() / 'whisper.cpp' / 'build' / 'bin' / 'main',
            Path(__file__).parent.parent.parent / 'whisper.cpp' / 'main',
        ]

        # Also check PATH
        try:
            result = subprocess.run(
                ['which', 'whisper'] if os.name != 'nt' else ['where', 'whisper'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                possible_paths.insert(0, Path(result.stdout.strip()))
        except Exception:
            pass

        for path in possible_paths:
            if path.exists() and os.access(path, os.X_OK):
                return path

        return None

    def _check_python_bindings(self) -> bool:
        """Check if Python bindings are available."""
        try:
            import pywhispercpp
            return True
        except ImportError:
            return False

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return "whisper.cpp"

    def is_available(self) -> bool:
        """Check if engine is available."""
        if not self.model_path.exists():
            return False

        # Either executable or Python bindings must be available
        return self.executable is not None or self._has_python_bindings

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe audio using whisper.cpp.

        Args:
            audio_data: WAV audio bytes (16kHz mono expected)
            sample_rate: Sample rate (should be 16000)
            language: Language code

        Returns:
            TranscriptionResult with transcription
        """
        if not self.is_available():
            raise RuntimeError("Whisper.cpp engine not available")

        # Use Python bindings if available (faster)
        if self._has_python_bindings:
            return await self._transcribe_with_bindings(audio_data, language)

        # Fall back to CLI
        return await self._transcribe_with_cli(audio_data, language)

    async def _transcribe_with_bindings(
        self,
        audio_data: bytes,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using Python bindings."""
        try:
            import pywhispercpp.model as whisper_model
            import numpy as np
            import wave
            import io

            # Parse WAV to get audio samples
            with io.BytesIO(audio_data) as f:
                with wave.open(f, 'rb') as wav:
                    frames = wav.readframes(wav.getnframes())
                    duration = wav.getnframes() / wav.getframerate()

            # Convert to float32 numpy array
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            # Load model and transcribe
            model = whisper_model.Model(str(self.model_path), n_threads=self.threads)

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            segments = await loop.run_in_executor(
                None,
                lambda: model.transcribe(samples, language=language)
            )

            # Combine segments
            text = ' '.join(seg.text for seg in segments).strip()

            # Estimate confidence (whisper.cpp doesn't provide this directly)
            confidence = self._estimate_confidence(text, segments)

            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        except Exception as e:
            logger.error(f"[WHISPER] Python binding transcription failed: {e}")
            # Fall back to CLI
            return await self._transcribe_with_cli(audio_data, language)

    async def _transcribe_with_cli(
        self,
        audio_data: bytes,
        language: str
    ) -> TranscriptionResult:
        """Transcribe using whisper.cpp CLI."""
        # Write audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            audio_path = f.name

        try:
            # Build command
            cmd = [
                str(self.executable),
                '-m', str(self.model_path),
                '-f', audio_path,
                '-t', str(self.threads),
                '-l', language,
                '--output-txt',
                '--no-timestamps',
            ]

            # Run whisper.cpp
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0  # 60 second timeout
            )

            if process.returncode != 0:
                logger.error(f"[WHISPER] CLI failed: {stderr.decode()}")
                raise RuntimeError(f"Whisper.cpp failed: {stderr.decode()}")

            # Parse output
            text = stdout.decode().strip()

            # Get duration from audio file
            import wave
            import io
            with io.BytesIO(audio_data) as f:
                with wave.open(f, 'rb') as wav:
                    duration = wav.getnframes() / wav.getframerate()

            # Estimate confidence
            confidence = self._estimate_confidence_from_text(text)

            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        finally:
            # Clean up temp file
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    def _estimate_confidence(self, text: str, segments: list) -> float:
        """
        Estimate transcription confidence.

        Whisper.cpp doesn't provide per-word confidence, so we estimate
        based on text characteristics.
        """
        if not text:
            return 0.0

        # Base confidence
        confidence = 0.8

        # Penalize very short transcriptions
        if len(text.split()) < 2:
            confidence -= 0.2

        # Penalize if text contains uncertainty markers
        uncertainty_markers = ['[inaudible]', '...', '(unclear)', '?']
        for marker in uncertainty_markers:
            if marker in text.lower():
                confidence -= 0.1

        # Penalize if too many non-ASCII characters (might be noise)
        non_ascii_ratio = sum(1 for c in text if ord(c) > 127) / max(len(text), 1)
        if non_ascii_ratio > 0.1:
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))

    def _estimate_confidence_from_text(self, text: str) -> float:
        """Estimate confidence from output text only."""
        if not text:
            return 0.0

        confidence = 0.8

        # Check for common issues
        if len(text.split()) < 2:
            confidence -= 0.2

        if re.search(r'\[.*?\]', text):  # Has bracketed annotations
            confidence -= 0.15

        if text.count('?') > 2:  # Multiple question marks might indicate uncertainty
            confidence -= 0.1

        return max(0.1, min(1.0, confidence))
