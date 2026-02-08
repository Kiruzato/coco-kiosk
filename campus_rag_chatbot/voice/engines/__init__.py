"""
Voice Engines Package
=====================

Phase 32: Voice Infrastructure Foundation
Phase 38: Google Cloud STT Integration

Engine implementations for STT and TTS services.

STT Engines:
- WhisperCppEngine: Offline STT using whisper.cpp
- WhisperOpenAIEngine: Cloud STT using OpenAI Whisper API
- GoogleCloudSTTEngine: Cloud STT using Google Cloud Speech-to-Text (Phase 38)

TTS Engines:
- PiperTTSEngine: Offline TTS using Piper
- EspeakTTSEngine: Offline TTS using espeak-ng (fallback)
- OpenAITTSEngine: Cloud TTS using OpenAI TTS API (optional)
"""

# Lazy imports to avoid loading all engines at startup
__all__ = [
    'WhisperCppEngine',
    'WhisperOpenAIEngine',
    'GoogleCloudSTTEngine',
    'PiperTTSEngine',
    'EspeakTTSEngine',
]
