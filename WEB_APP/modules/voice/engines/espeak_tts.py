"""
espeak-ng TTS Engine
====================

Phase 32: Voice Infrastructure Foundation

Offline text-to-speech using espeak-ng.
Fast, lightweight fallback TTS for when Piper is unavailable.

Requirements:
- espeak-ng system package
- espeak-ng Python wrapper (optional)

Usage:
    engine = EspeakTTSEngine(config)
    if engine.is_available():
        result = await engine.synthesize("Hello world")
"""

import asyncio
import subprocess
import tempfile
import os
import logging
from typing import Dict, Any, Optional

from ..tts_service import TTSEngine, SynthesisResult
from ..audio_utils import get_audio_info

logger = logging.getLogger(__name__)


class EspeakTTSEngine(TTSEngine):
    """
    espeak-ng TTS engine for fast offline speech synthesis.

    Uses the espeak-ng command-line tool for synthesis.
    Lower quality than Piper but much faster and smaller.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize espeak-ng engine.

        Args:
            config: Configuration dict with:
                - voice: Voice name (default 'en-us')
                - rate: Speech rate in words per minute (default 150)
                - pitch: Pitch adjustment (default 50)
                - amplitude: Volume (default 100)
        """
        self.config = config
        self.voice = config.get('voice', 'en-us')
        self.rate = config.get('rate', 150)
        self.pitch = config.get('pitch', 50)
        self.amplitude = config.get('amplitude', 100)

        # Check for espeak-ng
        self._executable = self._find_executable()

        if self.is_available():
            logger.info(f"[ESPEAK] Initialized with voice: {self.voice}")

    def _find_executable(self) -> Optional[str]:
        """Find espeak-ng executable."""
        # Check common names
        for name in ['espeak-ng', 'espeak']:
            try:
                result = subprocess.run(
                    [name, '--version'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return name
            except FileNotFoundError:
                continue

        return None

    @property
    def engine_name(self) -> str:
        """Get engine name."""
        return f"espeak-ng ({self.voice})"

    def is_available(self) -> bool:
        """Check if engine is available."""
        return self._executable is not None

    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech using espeak-ng.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with WAV audio data
        """
        if not self.is_available():
            raise RuntimeError("espeak-ng engine not available")

        # Create temp file for output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            output_path = f.name

        try:
            # Build command
            cmd = [
                self._executable,
                '-v', self.voice,
                '-s', str(self.rate),
                '-p', str(self.pitch),
                '-a', str(self.amplitude),
                '-w', output_path,
                text
            ]

            # Run espeak-ng
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )

            if process.returncode != 0:
                logger.error(f"[ESPEAK] Synthesis failed: {stderr.decode()}")
                raise RuntimeError(f"espeak-ng failed: {stderr.decode()}")

            # Read output file
            with open(output_path, 'rb') as f:
                audio_data = f.read()

            # Get audio info
            try:
                info = get_audio_info(audio_data)
                duration = info.duration_seconds
                sample_rate = info.sample_rate
            except Exception:
                # Default values if parsing fails
                duration = len(audio_data) / (22050 * 2)  # Rough estimate
                sample_rate = 22050

            return SynthesisResult(
                audio_data=audio_data,
                format='wav',
                sample_rate=sample_rate,
                duration_seconds=duration,
                engine_used=self.engine_name,
            )

        finally:
            # Clean up temp file
            try:
                os.unlink(output_path)
            except Exception:
                pass
