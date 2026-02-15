"""
Voice Engines Package
=====================

Phase 32: Voice Infrastructure Foundation
Phase 38: Google Cloud STT Integration

Engine implementations for STT and TTS services.

STT Engines:
- WhisperCppEngine: Offline STT using whisper.cpp
- GoogleCloudSTTEngine: Cloud STT using Google Cloud Speech-to-Text

TTS Engines:
- PiperTTSEngine: Offline TTS using Piper
- EspeakTTSEngine: Offline TTS using espeak-ng (fallback)
"""

# Lazy imports to avoid loading all engines at startup
__all__ = [
    'WhisperCppEngine',
    'GoogleCloudSTTEngine',
    'PiperTTSEngine',
    'EspeakTTSEngine',
]
