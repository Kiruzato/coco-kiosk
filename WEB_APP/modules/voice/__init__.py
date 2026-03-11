"""
Voice Integration Package
=========================

Phase 32: Voice Infrastructure Foundation

Provides speech-to-text (STT) and text-to-speech (TTS) services for the CoCo
campus kiosk chatbot. Designed for offline-first operation on Raspberry Pi 5.

Architecture:
    Voice is a MODALITY LAYER, not a decision layer.
    All queries flow through the existing /chat API unchanged.
    Voice just handles I/O transformation (audio <-> text).

Components:
- config: Voice configuration management
- audio_utils: Audio format conversion and normalization
- stt_service: Speech-to-Text service abstraction
- tts_service: Text-to-Speech service abstraction
- engines/: Engine implementations (Whisper.cpp, Piper, etc.)

Usage:
    from voice import VoiceOrchestrator
    from WEB_APP.modules.voice.config import VOICE_CONFIG

    orchestrator = VoiceOrchestrator(config=VOICE_CONFIG)
    result = await orchestrator.process_voice_interaction(audio_data, session_id)
"""

from .config import VOICE_CONFIG, is_voice_enabled
from .stt_service import STTService, TranscriptionResult
from .tts_service import TTSService, SynthesisResult
from .voice_orchestrator import VoiceOrchestrator

__all__ = [
    'VOICE_CONFIG',
    'is_voice_enabled',
    'STTService',
    'TranscriptionResult',
    'TTSService',
    'SynthesisResult',
    'VoiceOrchestrator',
]

__version__ = '0.1.0'
