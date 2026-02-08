# Voice Integration Engineering Proposal for CoCo

## Executive Summary

This proposal outlines a production-grade architecture for adding voice input (STT) and voice output (TTS) to the CoCo campus kiosk chatbot. The design prioritizes **offline capability**, **low latency**, **modular decoupling**, and **preservation of existing deterministic guarantees**.

**Author**: AI Systems Architect
**Date**: 2026-02-03
**Status**: Proposal
**Target Phases**: 32-36

---

## 1. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KIOSK HARDWARE LAYER                              │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ USB/I2S Mic │    │ Touchscreen  │    │   Speaker   │    │ Status LEDs │ │
│  └──────┬──────┘    └──────┬───────┘    └──────▲──────┘    └──────▲──────┘ │
└─────────┼──────────────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │                  │
┌─────────┼──────────────────┼──────────────────┼──────────────────┼─────────┐
│         ▼                  ▼                  │                  │         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FRONTEND (Browser/Electron)                      │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌─────────────┐ │   │
│  │  │VoiceCapture │  │ VoiceState   │  │ AudioQueue│  │ TextDisplay │ │   │
│  │  │  Module     │──│  Manager     │──│  Player   │  │   (UI)      │ │   │
│  │  │(Web Audio)  │  │(FSM)         │  │           │  │             │ │   │
│  │  └──────┬──────┘  └──────┬───────┘  └─────▲─────┘  └──────▲──────┘ │   │
│  │         │                │                │               │        │   │
│  │         │         ┌──────▼───────┐        │               │        │   │
│  │         │         │ VoiceAPI     │────────┴───────────────┘        │   │
│  │         └────────►│ Client       │                                 │   │
│  │                   │ (REST/WS)    │                                 │   │
│  │                   └──────┬───────┘                                 │   │
│  └──────────────────────────┼─────────────────────────────────────────┘   │
│                             │                                             │
│              FRONTEND       │              BACKEND                        │
│  ═══════════════════════════╪════════════════════════════════════════════ │
│                             │                                             │
│  ┌──────────────────────────▼─────────────────────────────────────────┐   │
│  │                      FastAPI Backend (app.py)                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    Voice Gateway Router                      │   │   │
│  │  │  POST /voice/transcribe  │  POST /voice/synthesize          │   │   │
│  │  │  WS   /voice/stream      │  GET  /voice/status              │   │   │
│  │  └─────────────┬────────────┴──────────────┬───────────────────┘   │   │
│  │                │                           │                        │   │
│  │    ┌───────────▼───────────┐   ┌───────────▼───────────┐           │   │
│  │    │   STT Service         │   │   TTS Service         │           │   │
│  │    │   (voice_stt.py)      │   │   (voice_tts.py)      │           │   │
│  │    │   ┌───────────────┐   │   │   ┌───────────────┐   │           │   │
│  │    │   │ Whisper.cpp   │   │   │   │ Piper TTS     │   │           │   │
│  │    │   │ (offline)     │   │   │   │ (offline)     │   │           │   │
│  │    │   └───────────────┘   │   │   └───────────────┘   │           │   │
│  │    │   ┌───────────────┐   │   │   ┌───────────────┐   │           │   │
│  │    │   │ OpenAI Whisper│   │   │   │ OpenAI TTS    │   │           │   │
│  │    │   │ (cloud fallbk)│   │   │   │ (cloud fallbk)│   │           │   │
│  │    │   └───────────────┘   │   │   └───────────────┘   │           │   │
│  │    └───────────┬───────────┘   └───────────┬───────────┘           │   │
│  │                │                           │                        │   │
│  │    ┌───────────▼───────────────────────────▼───────────┐           │   │
│  │    │              Voice Orchestrator                    │           │   │
│  │    │  • Confidence routing (low STT → text fallback)   │           │   │
│  │    │  • Timeout handling                               │           │   │
│  │    │  • Error recovery                                 │           │   │
│  │    │  • Voice event logging                            │           │   │
│  │    └───────────────────────┬───────────────────────────┘           │   │
│  │                            │                                        │   │
│  │    ════════════════════════╪════════════════════════════════       │   │
│  │          VOICE LAYER       │       EXISTING RAG LAYER              │   │
│  │    ════════════════════════╪════════════════════════════════       │   │
│  │                            │                                        │   │
│  │                 ┌──────────▼──────────┐                            │   │
│  │                 │   POST /chat        │  ◄── UNCHANGED             │   │
│  │                 │   (existing API)    │                            │   │
│  │                 └──────────┬──────────┘                            │   │
│  │                            │                                        │   │
│  │    ┌───────────────────────▼────────────────────────────────────┐  │   │
│  │    │                 EXISTING RAG PIPELINE                       │  │   │
│  │    │  Directory → Retrieval → Grounding → Extraction → LLM     │  │   │
│  │    │       (All deterministic guarantees preserved)             │  │   │
│  │    └────────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Recommended Technology Stack

### 2.1 Speech-to-Text (STT) Options

| Option | Offline | RPi5 Compatible | Latency | Accuracy | Recommendation |
|--------|---------|-----------------|---------|----------|----------------|
| **Whisper.cpp (tiny/base)** | Yes | Yes (ARM64 optimized) | 1-3s | Good | **Primary** |
| **Vosk** | Yes | Yes | 0.5-1s | Moderate | Alternative |
| **OpenAI Whisper API** | No | Yes | 1-2s | Excellent | Cloud fallback |
| **Google Speech-to-Text** | No | Yes | 0.5-1s | Excellent | Not recommended (privacy) |

**Primary Choice: Whisper.cpp with tiny.en model**

Reasoning:
- **Offline-first**: Critical for kiosk reliability (network outages shouldn't disable voice)
- **ARM64 optimized**: whisper.cpp has NEON SIMD optimizations for RPi5
- **Model size**: tiny.en is ~75MB, fits comfortably in RPi5's 8GB RAM
- **Accuracy**: Sufficient for campus queries (short, predictable domain vocabulary)
- **License**: MIT license, production-safe

```python
# Recommended configuration
STT_CONFIG = {
    "primary": {
        "engine": "whisper.cpp",
        "model": "tiny.en",  # or "base.en" for better accuracy
        "model_path": "models/ggml-tiny.en.bin",
        "language": "en",
        "beam_size": 5,
        "best_of": 3,
    },
    "fallback": {
        "engine": "openai-whisper",
        "model": "whisper-1",
        "enabled": True,  # Enable for low-confidence retries
    },
    "thresholds": {
        "min_confidence": 0.7,  # Below this, show text input prompt
        "retry_on_low_confidence": True,
        "max_audio_duration_seconds": 30,
    }
}
```

### 2.2 Text-to-Speech (TTS) Options

| Option | Offline | RPi5 Compatible | Latency | Quality | Recommendation |
|--------|---------|-----------------|---------|---------|----------------|
| **Piper TTS** | Yes | Yes (ARM64) | 50-200ms | Good | **Primary** |
| **espeak-ng** | Yes | Yes | <50ms | Low | Fast fallback |
| **Coqui TTS** | Yes | Warning (slow) | 1-3s | Excellent | Not recommended |
| **OpenAI TTS** | No | Yes | 0.5-1s | Excellent | Cloud fallback |
| **Google TTS** | No | Yes | 0.3-0.5s | Excellent | Not recommended (privacy) |

**Primary Choice: Piper TTS**

Reasoning:
- **Offline-first**: ONNX-based, runs entirely locally
- **Quality**: Natural-sounding neural voices (trained on LJSpeech, VCTK)
- **Speed**: Real-time factor ~0.1x on RPi5 (generates faster than playback)
- **Voices**: Multiple English voices available, including Filipino-accented options
- **Memory**: ~50MB per voice model
- **License**: MIT license

```python
# Recommended configuration
TTS_CONFIG = {
    "primary": {
        "engine": "piper",
        "voice": "en_US-amy-medium",  # Clear female voice
        "model_path": "models/piper/en_US-amy-medium.onnx",
        "config_path": "models/piper/en_US-amy-medium.onnx.json",
        "sample_rate": 22050,
        "speaker_id": 0,
    },
    "fallback": {
        "engine": "espeak-ng",
        "voice": "en-us",
        "rate": 150,  # Words per minute
    },
    "cloud_fallback": {
        "engine": "openai-tts",
        "voice": "nova",
        "model": "tts-1",
        "enabled": False,  # Only enable if offline quality insufficient
    },
    "audio": {
        "format": "wav",
        "sample_rate": 22050,
        "channels": 1,
    }
}
```

### 2.3 Audio Infrastructure

| Component | Library | Purpose |
|-----------|---------|---------|
| Audio capture | **Web Audio API** (frontend) | Browser-based mic access |
| Audio encoding | **opus-recorder** / native MediaRecorder | Compress audio for upload |
| Audio playback | **HTMLAudioElement** / Web Audio API | Play TTS responses |
| Backend audio I/O | **sounddevice** / **pyaudio** | Direct hardware access (optional) |
| Audio format conversion | **pydub** / **ffmpeg** | Format normalization |

---

## 3. Frontend Flow

### 3.1 Voice Capture Module

```
┌──────────────────────────────────────────────────────────────────────┐
│                        VOICE STATE MACHINE                           │
│                                                                      │
│  ┌─────────┐    click/     ┌──────────┐   silence    ┌───────────┐ │
│  │  IDLE   │───────────────│LISTENING │──────────────│PROCESSING │ │
│  │         │   hotword     │          │   detected   │           │ │
│  └────▲────┘               └────┬─────┘              └─────┬─────┘ │
│       │                         │                          │       │
│       │                         │ cancel                   │       │
│       │                         ▼                          │       │
│       │                    ┌─────────┐                     │       │
│       │                    │CANCELLED│                     │       │
│       │                    └────┬────┘                     │       │
│       │                         │                          │       │
│       │    ┌────────────────────┴──────────────────────────┘       │
│       │    │                                                        │
│       │    ▼                                                        │
│       │  ┌──────────┐   success   ┌──────────┐   audio    ┌──────┐│
│       └──│RESPONDING│◄────────────│ WAITING  │◄───────────│READY ││
│          │(playing) │             │(for TTS) │   ready    │      ││
│          └──────────┘             └──────────┘            └──────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Frontend JavaScript Architecture

```javascript
// static/js/voice/VoiceModule.js

class VoiceModule {
    constructor(chatAPI) {
        this.state = 'IDLE';
        this.chatAPI = chatAPI;
        this.audioContext = null;
        this.mediaRecorder = null;
        this.audioQueue = new AudioQueue();
        this.config = {
            silenceThreshold: -50,      // dB
            silenceDuration: 1500,      // ms of silence to stop recording
            maxRecordingDuration: 30000, // ms max recording
            sampleRate: 16000,          // Hz (Whisper expects 16kHz)
        };
    }

    async initialize() {
        // Request microphone permission
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: this.config.sampleRate,
                echoCancellation: true,
                noiseSuppression: true,
            }
        });
        this.audioContext = new AudioContext({ sampleRate: this.config.sampleRate });
        this.analyser = this.audioContext.createAnalyser();
        // ... setup audio pipeline
    }

    async startListening() {
        if (this.state !== 'IDLE') return;
        this.state = 'LISTENING';
        this.emit('stateChange', { state: 'LISTENING' });

        const chunks = [];
        this.mediaRecorder = new MediaRecorder(this.stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        this.mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        this.mediaRecorder.onstop = () => this.processAudio(chunks);
        this.mediaRecorder.start();

        // Start silence detection
        this.detectSilence();
    }

    async processAudio(chunks) {
        this.state = 'PROCESSING';
        this.emit('stateChange', { state: 'PROCESSING' });

        const audioBlob = new Blob(chunks, { type: 'audio/webm' });

        try {
            // Send to backend for transcription
            const transcription = await this.transcribe(audioBlob);

            if (transcription.confidence < 0.7) {
                // Low confidence - show text input fallback
                this.emit('lowConfidence', {
                    partial: transcription.text,
                    confidence: transcription.confidence
                });
                this.state = 'IDLE';
                return;
            }

            // Send transcribed text to chat API
            this.state = 'WAITING';
            const response = await this.chatAPI.send(transcription.text);

            // Synthesize and play response
            this.state = 'RESPONDING';
            await this.speakResponse(response.answer);

            this.state = 'IDLE';
            this.emit('stateChange', { state: 'IDLE' });

        } catch (error) {
            this.handleError(error);
        }
    }

    async transcribe(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        const response = await fetch('/voice/transcribe', {
            method: 'POST',
            body: formData,
        });

        return response.json();
    }

    async speakResponse(text) {
        const response = await fetch('/voice/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });

        const audioBlob = await response.blob();
        await this.audioQueue.play(audioBlob);
    }
}
```

### 3.3 UI Components

```
┌────────────────────────────────────────────────────────────┐
│                     KIOSK INTERFACE                        │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                                                      │ │
│  │                   CHAT MESSAGES                      │ │
│  │                                                      │ │
│  │  ┌────────────────────────────────────────────────┐ │ │
│  │  │ User: Where is the library?                    │ │ │
│  │  └────────────────────────────────────────────────┘ │ │
│  │  ┌────────────────────────────────────────────────┐ │ │
│  │  │ CoCo: The library is located in B Building,   │ │ │
│  │  │       2nd Floor, Room B201.                    │ │ │
│  │  │       [Speaker Icon] [Playing audio...]        │ │ │
│  │  └────────────────────────────────────────────────┘ │ │
│  │                                                      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  ┌──────────────┐  ┌─────────────────────────────┐  │ │
│  │  │              │  │                             │  │ │
│  │  │  [Mic] SPEAK │  │  Type your question...     │  │ │
│  │  │   [Tap/Hold] │  │  [________________________] │  │ │
│  │  │              │  │                             │  │ │
│  │  └──────────────┘  └─────────────────────────────┘  │ │
│  │                                                      │ │
│  │  ┌──────────────────────────────────────────────┐   │ │
│  │  │ [Mute] Mute Audio  |  [Keyboard] Text Only   │   │ │
│  │  └──────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘

VOICE STATES VISUAL FEEDBACK:
┌─────────────┬───────────────────────────────────────────────┐
│ State       │ Visual Indicator                              │
├─────────────┼───────────────────────────────────────────────┤
│ IDLE        │ Static mic icon, "Tap to speak"               │
│ LISTENING   │ Pulsing red dot, waveform animation           │
│ PROCESSING  │ Spinner, "Understanding..."                   │
│ RESPONDING  │ Speaker icon, audio progress bar              │
│ ERROR       │ Error message with retry button               │
└─────────────┴───────────────────────────────────────────────┘
```

---

## 4. Backend Flow

### 4.1 Voice Service Architecture

```
campus_rag_chatbot/
├── voice/                      # NEW: Voice services package
│   ├── __init__.py
│   ├── config.py               # Voice configuration
│   ├── stt_service.py          # Speech-to-Text abstraction
│   ├── tts_service.py          # Text-to-Speech abstraction
│   ├── voice_orchestrator.py   # Coordination layer
│   ├── audio_utils.py          # Format conversion, normalization
│   ├── engines/                # Engine implementations
│   │   ├── __init__.py
│   │   ├── whisper_cpp.py      # Whisper.cpp wrapper
│   │   ├── whisper_openai.py   # OpenAI Whisper API
│   │   ├── piper_tts.py        # Piper TTS wrapper
│   │   ├── espeak_tts.py       # espeak-ng fallback
│   │   └── openai_tts.py       # OpenAI TTS API
│   └── models/                 # Model files (git-ignored)
│       ├── ggml-tiny.en.bin    # Whisper model
│       └── piper/              # Piper voice models
│           ├── en_US-amy-medium.onnx
│           └── en_US-amy-medium.onnx.json
├── voice_routes.py             # NEW: FastAPI voice endpoints
└── app.py                      # Existing (add voice router)
```

### 4.2 STT Service Implementation

```python
# campus_rag_chatbot/voice/stt_service.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription."""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    engine_used: str
    is_fallback: bool = False

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        return self.confidence >= threshold


class STTEngine(ABC):
    """Abstract base class for STT engines."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class STTService:
    """
    Speech-to-Text service with automatic fallback.

    Strategy:
    1. Try primary engine (Whisper.cpp, offline)
    2. If confidence < threshold, retry with cloud engine
    3. Return best result with confidence metadata
    """

    def __init__(self, config: dict):
        self.config = config
        self.primary_engine = self._init_primary_engine()
        self.fallback_engine = self._init_fallback_engine()
        self.confidence_threshold = config.get('thresholds', {}).get('min_confidence', 0.7)

    def _init_primary_engine(self) -> STTEngine:
        from .engines.whisper_cpp import WhisperCppEngine
        return WhisperCppEngine(self.config['primary'])

    def _init_fallback_engine(self) -> Optional[STTEngine]:
        if not self.config.get('fallback', {}).get('enabled', False):
            return None
        from .engines.whisper_openai import WhisperOpenAIEngine
        return WhisperOpenAIEngine(self.config['fallback'])

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe audio with automatic fallback.

        Args:
            audio_data: Raw audio bytes (WAV or WebM)
            sample_rate: Audio sample rate

        Returns:
            TranscriptionResult with text and confidence
        """
        # Normalize audio format
        from .audio_utils import normalize_audio
        normalized_audio = normalize_audio(audio_data, target_sample_rate=16000)

        # Try primary engine
        try:
            result = await self.primary_engine.transcribe(normalized_audio, sample_rate=16000)
            logger.info(f"[STT] Primary engine result: confidence={result.confidence:.2f}")

            # If high confidence, return immediately
            if result.is_high_confidence(self.confidence_threshold):
                return result

            # Low confidence - try fallback if available
            if self.fallback_engine and self.fallback_engine.is_available():
                logger.info(f"[STT] Low confidence ({result.confidence:.2f}), trying fallback")
                fallback_result = await self.fallback_engine.transcribe(normalized_audio)
                fallback_result.is_fallback = True

                # Return better result
                if fallback_result.confidence > result.confidence:
                    logger.info(f"[STT] Using fallback result: confidence={fallback_result.confidence:.2f}")
                    return fallback_result

            return result

        except Exception as e:
            logger.error(f"[STT] Primary engine failed: {e}")

            # Try fallback on primary failure
            if self.fallback_engine and self.fallback_engine.is_available():
                result = await self.fallback_engine.transcribe(normalized_audio)
                result.is_fallback = True
                return result

            raise
```

### 4.3 TTS Service Implementation

```python
# campus_rag_chatbot/voice/tts_service.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis."""
    audio_data: bytes
    format: str  # 'wav', 'mp3', 'ogg'
    sample_rate: int
    duration_seconds: float
    engine_used: str


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesisResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class TTSService:
    """
    Text-to-Speech service with response optimization.

    Features:
    - Sentence-level streaming (optional)
    - Response shortening for very long answers
    - SSML support for natural prosody
    """

    def __init__(self, config: dict):
        self.config = config
        self.primary_engine = self._init_primary_engine()
        self.fallback_engine = self._init_fallback_engine()
        self.max_chars = config.get('max_chars', 500)  # Limit TTS length

    def _init_primary_engine(self) -> TTSEngine:
        from .engines.piper_tts import PiperTTSEngine
        return PiperTTSEngine(self.config['primary'])

    def _init_fallback_engine(self) -> TTSEngine:
        from .engines.espeak_tts import EspeakTTSEngine
        return EspeakTTSEngine(self.config['fallback'])

    async def synthesize(self, text: str) -> SynthesisResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to speak

        Returns:
            SynthesisResult with audio data
        """
        # Optimize text for speech
        optimized_text = self._optimize_for_speech(text)

        try:
            result = await self.primary_engine.synthesize(optimized_text)
            logger.info(f"[TTS] Synthesized {len(text)} chars in {result.duration_seconds:.2f}s")
            return result

        except Exception as e:
            logger.error(f"[TTS] Primary engine failed: {e}")
            return await self.fallback_engine.synthesize(optimized_text)

    def _optimize_for_speech(self, text: str) -> str:
        """
        Optimize text for natural speech output.

        - Truncate very long responses
        - Expand abbreviations
        - Add pauses at appropriate points
        """
        # Truncate if too long
        if len(text) > self.max_chars:
            # Find sentence boundary
            truncated = text[:self.max_chars]
            last_period = truncated.rfind('.')
            if last_period > self.max_chars * 0.5:
                truncated = truncated[:last_period + 1]
            text = truncated + " For more details, please see the screen."

        # Expand common abbreviations
        replacements = {
            'Dr.': 'Doctor',
            'Engr.': 'Engineer',
            'Bldg.': 'Building',
            'Rm.': 'Room',
            'St.': 'Saint',
            'vs.': 'versus',
        }
        for abbr, expansion in replacements.items():
            text = text.replace(abbr, expansion)

        return text
```

### 4.4 Voice Orchestrator

```python
# campus_rag_chatbot/voice/voice_orchestrator.py

from dataclasses import dataclass
from typing import Optional
import logging
import time

from .stt_service import STTService, TranscriptionResult
from .tts_service import TTSService, SynthesisResult
from event_tracker import EventTracker

logger = logging.getLogger(__name__)

@dataclass
class VoiceInteractionResult:
    """Complete result of a voice interaction."""
    # STT phase
    transcription: Optional[TranscriptionResult]
    transcription_success: bool

    # Chat phase (from existing /chat)
    chat_response: Optional[dict]
    chat_success: bool

    # TTS phase
    synthesis: Optional[SynthesisResult]
    synthesis_success: bool

    # Timing
    total_latency_ms: float
    stt_latency_ms: float
    chat_latency_ms: float
    tts_latency_ms: float

    # Error info
    error_message: Optional[str] = None
    requires_text_fallback: bool = False


class VoiceOrchestrator:
    """
    Orchestrates voice interactions while preserving RAG guarantees.

    Key principle: Voice is a MODALITY LAYER, not a decision layer.
    All grounding, confidence, and determinism rules flow through
    the existing /chat API unchanged.
    """

    def __init__(self, stt_service: STTService, tts_service: TTSService,
                 chat_handler, event_tracker: EventTracker):
        self.stt = stt_service
        self.tts = tts_service
        self.chat_handler = chat_handler  # Reference to handle_chat()
        self.event_tracker = event_tracker

    async def process_voice_interaction(
        self,
        audio_data: bytes,
        session_id: str,
        skip_tts: bool = False
    ) -> VoiceInteractionResult:
        """
        Process complete voice interaction: STT -> Chat -> TTS

        This method:
        1. Transcribes audio to text (STT)
        2. Sends text through EXISTING chat pipeline (preserves all guarantees)
        3. Synthesizes response to audio (TTS)

        The chat pipeline is untouched - voice is purely I/O transformation.
        """
        start_time = time.time()
        result = VoiceInteractionResult(
            transcription=None, transcription_success=False,
            chat_response=None, chat_success=False,
            synthesis=None, synthesis_success=False,
            total_latency_ms=0, stt_latency_ms=0,
            chat_latency_ms=0, tts_latency_ms=0
        )

        # Phase 1: Speech-to-Text
        stt_start = time.time()
        try:
            transcription = await self.stt.transcribe(audio_data)
            result.transcription = transcription
            result.transcription_success = True
            result.stt_latency_ms = (time.time() - stt_start) * 1000

            # Check confidence threshold
            if not transcription.is_high_confidence():
                logger.warning(f"[VOICE] Low STT confidence: {transcription.confidence:.2f}")
                result.requires_text_fallback = True
                # Still continue - let user confirm/edit transcription

        except Exception as e:
            logger.error(f"[VOICE] STT failed: {e}")
            result.error_message = f"Could not understand audio: {str(e)}"
            result.stt_latency_ms = (time.time() - stt_start) * 1000
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result

        # Phase 2: Chat (EXISTING PIPELINE - UNCHANGED)
        chat_start = time.time()
        try:
            # Call existing chat handler with transcribed text
            # This preserves ALL grounding, confidence, and determinism rules
            chat_response = await self.chat_handler(
                message=transcription.text,
                session_id=session_id
            )
            result.chat_response = chat_response
            result.chat_success = True
            result.chat_latency_ms = (time.time() - chat_start) * 1000

        except Exception as e:
            logger.error(f"[VOICE] Chat failed: {e}")
            result.error_message = f"Could not process question: {str(e)}"
            result.chat_latency_ms = (time.time() - chat_start) * 1000
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result

        # Phase 3: Text-to-Speech
        if not skip_tts:
            tts_start = time.time()
            try:
                # Get the answer text for synthesis
                answer_text = chat_response.get('answer', '')

                # Don't synthesize if rejected or no answer
                if answer_text and not chat_response.get('rejected', False):
                    synthesis = await self.tts.synthesize(answer_text)
                    result.synthesis = synthesis
                    result.synthesis_success = True

            except Exception as e:
                logger.warning(f"[VOICE] TTS failed (non-fatal): {e}")
                # TTS failure is non-fatal - text answer still available

            result.tts_latency_ms = (time.time() - tts_start) * 1000

        result.total_latency_ms = (time.time() - start_time) * 1000

        # Log voice interaction event
        self._log_voice_event(result, session_id)

        return result

    def _log_voice_event(self, result: VoiceInteractionResult, session_id: str):
        """Log voice interaction for analytics."""
        self.event_tracker.track_event(
            event_type='voice_interaction',
            metadata={
                'session_id': session_id,
                'stt_success': result.transcription_success,
                'stt_confidence': result.transcription.confidence if result.transcription else None,
                'stt_engine': result.transcription.engine_used if result.transcription else None,
                'chat_success': result.chat_success,
                'tts_success': result.synthesis_success,
                'total_latency_ms': result.total_latency_ms,
                'requires_text_fallback': result.requires_text_fallback,
            }
        )
```

---

## 5. API Changes

### 5.1 New Voice Endpoints

```python
# campus_rag_chatbot/voice_routes.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

router = APIRouter(prefix="/voice", tags=["voice"])

# ============================================================================
# Request/Response Models
# ============================================================================

class TranscribeResponse(BaseModel):
    """Response from /voice/transcribe endpoint."""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    engine_used: str
    is_low_confidence: bool

class SynthesizeRequest(BaseModel):
    """Request to /voice/synthesize endpoint."""
    text: str
    voice: Optional[str] = None  # Override default voice
    speed: Optional[float] = 1.0  # Speech speed multiplier

class VoiceChatRequest(BaseModel):
    """Request for combined voice chat (STT -> Chat -> TTS)."""
    session_id: Optional[str] = None
    skip_tts: bool = False

class VoiceChatResponse(BaseModel):
    """Response from /voice/chat endpoint."""
    # Transcription
    transcribed_text: str
    transcription_confidence: float

    # Chat response (mirrors existing ChatResponse)
    answer: str
    mode: str
    confidence: str
    sources: list
    rejected: bool

    # Audio (base64 or URL)
    audio_url: Optional[str] = None

    # Flags
    requires_text_confirmation: bool

    # Timing
    latency_ms: dict

class VoiceStatusResponse(BaseModel):
    """Response from /voice/status endpoint."""
    stt_available: bool
    stt_engine: str
    tts_available: bool
    tts_engine: str
    voice_enabled: bool

# ============================================================================
# Endpoints
# ============================================================================

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (WebM, WAV, or MP3)"),
    language: str = Form(default="en", description="Expected language code")
):
    """
    Transcribe audio to text using STT service.

    Accepts: audio/webm, audio/wav, audio/mp3
    Returns: Transcription with confidence score

    If confidence < 0.7, is_low_confidence=True suggests showing text input.
    """
    audio_data = await audio.read()

    result = await stt_service.transcribe(audio_data)

    return TranscribeResponse(
        text=result.text,
        confidence=result.confidence,
        language=result.language,
        duration_seconds=result.duration_seconds,
        engine_used=result.engine_used,
        is_low_confidence=not result.is_high_confidence()
    )


@router.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Synthesize text to speech using TTS service.

    Returns: Audio stream (WAV format)
    """
    result = await tts_service.synthesize(request.text)

    return StreamingResponse(
        io.BytesIO(result.audio_data),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "inline; filename=response.wav",
            "X-Audio-Duration": str(result.duration_seconds),
            "X-TTS-Engine": result.engine_used,
        }
    )


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    skip_tts: bool = Form(default=False)
):
    """
    Combined voice interaction: STT -> Chat -> TTS

    This is the primary endpoint for voice-enabled kiosk interaction.

    Flow:
    1. Transcribe uploaded audio
    2. Process through existing chat pipeline (all guarantees preserved)
    3. Synthesize response to audio (unless skip_tts=True)

    Returns both text and audio response.
    """
    audio_data = await audio.read()

    result = await voice_orchestrator.process_voice_interaction(
        audio_data=audio_data,
        session_id=session_id or "voice-default",
        skip_tts=skip_tts
    )

    # Generate audio URL if synthesis succeeded
    audio_url = None
    if result.synthesis:
        # Store audio temporarily and return URL
        audio_id = store_audio_temporarily(result.synthesis.audio_data)
        audio_url = f"/voice/audio/{audio_id}"

    return VoiceChatResponse(
        transcribed_text=result.transcription.text if result.transcription else "",
        transcription_confidence=result.transcription.confidence if result.transcription else 0,
        answer=result.chat_response.get('answer', '') if result.chat_response else "",
        mode=result.chat_response.get('mode', 'unknown') if result.chat_response else "error",
        confidence=result.chat_response.get('confidence', 'LOW') if result.chat_response else "LOW",
        sources=result.chat_response.get('sources', []) if result.chat_response else [],
        rejected=result.chat_response.get('rejected', True) if result.chat_response else True,
        audio_url=audio_url,
        requires_text_confirmation=result.requires_text_fallback,
        latency_ms={
            "stt": result.stt_latency_ms,
            "chat": result.chat_latency_ms,
            "tts": result.tts_latency_ms,
            "total": result.total_latency_ms,
        }
    )


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """
    Retrieve temporarily stored audio file.

    Audio is stored for 5 minutes then auto-deleted.
    """
    audio_data = retrieve_audio(audio_id)
    if not audio_data:
        raise HTTPException(status_code=404, detail="Audio not found or expired")

    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/wav"
    )


@router.get("/status", response_model=VoiceStatusResponse)
async def voice_status():
    """
    Check voice service availability.

    Useful for frontend to know whether to show voice UI.
    """
    return VoiceStatusResponse(
        stt_available=stt_service.primary_engine.is_available(),
        stt_engine=stt_service.primary_engine.__class__.__name__,
        tts_available=tts_service.primary_engine.is_available(),
        tts_engine=tts_service.primary_engine.__class__.__name__,
        voice_enabled=True
    )
```

### 5.2 Existing API Unchanged

The existing `/chat` endpoint remains **completely unchanged**:

```python
# Existing endpoint - NO CHANGES
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Voice layer calls this internally - all grounding/confidence
    rules are enforced here, not in voice layer.
    """
    # ... existing implementation unchanged ...
```

---

## 6. Deployment Considerations

### 6.1 Raspberry Pi 5 Hardware Requirements

```
┌─────────────────────────────────────────────────────────────┐
│                 RECOMMENDED HARDWARE SETUP                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Raspberry Pi 5 (8GB RAM recommended)                       │
│  ├── Active cooling (essential for sustained inference)    │
│  ├── NVMe SSD via M.2 HAT (faster model loading)           │
│  └── Adequate power supply (5V 5A USB-C PD)                │
│                                                             │
│  Audio Input:                                               │
│  ├── USB microphone (Recommended: ReSpeaker USB Mic Array) │
│  │   - Far-field pickup (1-3m range)                       │
│  │   - Built-in noise suppression                          │
│  │   - VAD (Voice Activity Detection) hardware             │
│  └── Alternative: USB webcam with mic                      │
│                                                             │
│  Audio Output:                                              │
│  ├── 3.5mm audio jack -> amplified speakers                │
│  └── Alternative: USB audio adapter for better quality     │
│                                                             │
│  Display:                                                   │
│  └── HDMI touchscreen (7-10 inch for kiosk)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Model Storage & Loading

```
/opt/coco/
├── models/
│   ├── whisper/
│   │   ├── ggml-tiny.en.bin      # 75MB - Primary STT
│   │   └── ggml-base.en.bin      # 142MB - Backup (better accuracy)
│   └── piper/
│       ├── en_US-amy-medium.onnx     # 63MB
│       ├── en_US-amy-medium.onnx.json
│       └── en_US-lessac-medium.onnx  # Alternative voice
└── campus_rag_chatbot/
    └── ...
```

### 6.3 Performance Expectations

| Operation | Expected Latency (RPi5) | Acceptable Threshold |
|-----------|-------------------------|---------------------|
| Audio capture | 50ms | <100ms |
| STT (Whisper tiny) | 1.5-3s for 5s audio | <5s |
| Chat API (existing) | 1-3s | <5s |
| TTS (Piper) | 200-500ms | <1s |
| **Total round-trip** | **3-7s** | **<10s** |

### 6.4 Memory Budget

```
┌────────────────────────────────────────────────┐
│           MEMORY ALLOCATION (8GB Pi5)          │
├────────────────────────────────────────────────┤
│ OS + System                         │   1.0 GB │
│ Python + FastAPI                    │   0.3 GB │
│ FAISS Vector Store                  │   0.5 GB │
│ Whisper.cpp (tiny model)            │   0.2 GB │
│ Piper TTS (model + runtime)         │   0.3 GB │
│ OpenAI/LangChain runtime            │   0.2 GB │
│ Audio buffers                       │   0.1 GB │
│ ─────────────────────────────────── │ ──────── │
│ Total Used                          │   2.6 GB │
│ Available Headroom                  │   5.4 GB │
└────────────────────────────────────────────────┘
```

### 6.5 Startup Configuration

```python
# config/voice_config.py

import os

VOICE_CONFIG = {
    "enabled": os.getenv("VOICE_ENABLED", "true").lower() == "true",

    "stt": {
        "primary": {
            "engine": "whisper.cpp",
            "model_path": os.getenv("WHISPER_MODEL_PATH", "/opt/coco/models/whisper/ggml-tiny.en.bin"),
            "threads": int(os.getenv("WHISPER_THREADS", "4")),  # RPi5 has 4 cores
        },
        "fallback": {
            "engine": "openai-whisper",
            "enabled": os.getenv("WHISPER_CLOUD_FALLBACK", "false").lower() == "true",
        },
        "thresholds": {
            "min_confidence": 0.7,
            "max_audio_duration": 30,
        }
    },

    "tts": {
        "primary": {
            "engine": "piper",
            "model_path": os.getenv("PIPER_MODEL_PATH", "/opt/coco/models/piper/en_US-amy-medium.onnx"),
        },
        "fallback": {
            "engine": "espeak-ng",
        },
        "max_response_chars": 500,
    },

    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "format": "wav",
        "temp_storage_ttl_seconds": 300,  # 5 minutes
    }
}
```

### 6.6 Systemd Service

```ini
# /etc/systemd/system/coco-voice.service

[Unit]
Description=CoCo Campus Kiosk with Voice
After=network.target sound.target

[Service]
Type=simple
User=coco
WorkingDirectory=/opt/coco/campus_rag_chatbot
Environment="VOICE_ENABLED=true"
Environment="WHISPER_MODEL_PATH=/opt/coco/models/whisper/ggml-tiny.en.bin"
Environment="PIPER_MODEL_PATH=/opt/coco/models/piper/en_US-amy-medium.onnx"
ExecStart=/opt/coco/venv/bin/python app.py
Restart=always
RestartSec=5

# Resource limits
MemoryMax=6G
CPUQuota=90%

[Install]
WantedBy=multi-user.target
```

---

## 7. Testing Strategy

### 7.1 Test Categories

```
tests/
├── voice/
│   ├── unit/
│   │   ├── test_stt_service.py       # STT service unit tests
│   │   ├── test_tts_service.py       # TTS service unit tests
│   │   ├── test_audio_utils.py       # Audio conversion tests
│   │   └── test_voice_orchestrator.py
│   ├── integration/
│   │   ├── test_voice_endpoints.py   # API integration tests
│   │   ├── test_voice_chat_flow.py   # End-to-end voice flow
│   │   └── test_engine_fallbacks.py  # Fallback behavior tests
│   ├── fixtures/
│   │   ├── audio_samples/            # Test audio files
│   │   │   ├── where_is_library.wav
│   │   │   ├── who_are_deans.wav
│   │   │   ├── noisy_query.wav
│   │   │   └── silence.wav
│   │   └── expected_outputs/
│   └── performance/
│       ├── test_latency.py           # Latency benchmarks
│       └── test_memory_usage.py      # Memory profiling
└── golden_tests_voice.json           # Voice-specific golden tests
```

### 7.2 Voice Golden Tests

```json
{
  "voice_tests": [
    {
      "id": "VOICE_001",
      "name": "Basic Directory Query",
      "audio_file": "fixtures/audio_samples/where_is_library.wav",
      "expected_transcription": "where is the library",
      "transcription_tolerance": 0.9,
      "expected_mode": ["directory", "clarification"],
      "verify_tts_generated": true
    },
    {
      "id": "VOICE_002",
      "name": "Enumeration Query",
      "audio_file": "fixtures/audio_samples/who_are_deans.wav",
      "expected_transcription": "who are the deans",
      "transcription_tolerance": 0.85,
      "expected_mode": "campus",
      "expected_contains": ["Dr.", "Dean"],
      "verify_tts_generated": true
    },
    {
      "id": "VOICE_003",
      "name": "Noisy Audio Fallback",
      "audio_file": "fixtures/audio_samples/noisy_query.wav",
      "expect_low_confidence": true,
      "expect_text_fallback_prompt": true
    },
    {
      "id": "VOICE_004",
      "name": "Silence Handling",
      "audio_file": "fixtures/audio_samples/silence.wav",
      "expect_error": true,
      "error_type": "no_speech_detected"
    }
  ]
}
```

### 7.3 Test Execution

```python
# tests/voice/integration/test_voice_chat_flow.py

import pytest
from pathlib import Path

class TestVoiceChatFlow:
    """Integration tests for complete voice interaction flow."""

    @pytest.fixture
    def audio_sample_path(self):
        return Path(__file__).parent.parent / "fixtures" / "audio_samples"

    async def test_basic_voice_query_preserves_grounding(self, client, audio_sample_path):
        """
        Verify that voice queries go through normal grounding validation.

        Critical: Voice must not bypass any RAG guarantees.
        """
        audio_file = audio_sample_path / "where_is_library.wav"

        with open(audio_file, "rb") as f:
            response = await client.post(
                "/voice/chat",
                files={"audio": ("test.wav", f, "audio/wav")},
                data={"session_id": "test-session"}
            )

        assert response.status_code == 200
        data = response.json()

        # Verify transcription worked
        assert data["transcription_confidence"] > 0.5
        assert "library" in data["transcribed_text"].lower()

        # Verify chat response went through normal pipeline
        assert data["mode"] in ["directory", "clarification", "campus"]
        assert data["confidence"] in ["HIGH", "Medium", "LOW"]

        # Verify TTS was generated
        assert data["audio_url"] is not None

    async def test_low_confidence_triggers_text_fallback(self, client, audio_sample_path):
        """Verify low STT confidence prompts text input."""
        audio_file = audio_sample_path / "noisy_query.wav"

        with open(audio_file, "rb") as f:
            response = await client.post(
                "/voice/chat",
                files={"audio": ("test.wav", f, "audio/wav")}
            )

        data = response.json()
        assert data["requires_text_confirmation"] == True

    async def test_voice_preserves_deterministic_extraction(self, client, audio_sample_path):
        """
        Verify voice queries to deterministic extractors work correctly.

        "Who are the deans?" should use Phase 18.2 deterministic extraction
        regardless of whether input was voice or text.
        """
        audio_file = audio_sample_path / "who_are_deans.wav"

        with open(audio_file, "rb") as f:
            response = await client.post(
                "/voice/chat",
                files={"audio": ("test.wav", f, "audio/wav")}
            )

        data = response.json()

        # Should get deterministic dean list
        assert "Dr." in data["answer"]
        assert data["answer"].count("Dean") >= 5  # Multiple deans listed
```

---

## 8. Phased Rollout Plan

### Phase 32: Voice Infrastructure Foundation

**Goal**: Backend voice services without UI integration

**Tasks**:
1. Create `voice/` package structure
2. Implement Whisper.cpp STT engine wrapper
3. Implement Piper TTS engine wrapper
4. Implement audio format conversion utilities
5. Create voice configuration system
6. Add `/voice/status` endpoint
7. Unit tests for all components

**Deliverables**:
- `voice/stt_service.py`, `voice/tts_service.py`
- `voice/engines/*.py`
- `voice/config.py`
- Unit test coverage >80%

**Acceptance Criteria**:
- STT transcribes test audio with >70% confidence
- TTS generates audio for sample text
- Both work offline on RPi5

---

### Phase 33: Voice API Layer

**Goal**: REST endpoints for voice operations

**Tasks**:
1. Implement `voice_routes.py` with all endpoints
2. Implement `voice_orchestrator.py`
3. Add temporary audio storage with TTL
4. Integrate with existing `event_tracker.py`
5. Add voice-specific error handling
6. Integration tests

**Deliverables**:
- `/voice/transcribe`, `/voice/synthesize`, `/voice/chat` endpoints
- Voice event logging
- Integration test suite

**Acceptance Criteria**:
- `/voice/chat` returns correct response for voice input
- All existing `/chat` behavior preserved
- Latency <10s on RPi5

---

### Phase 34: Frontend Voice UI

**Goal**: Browser-based voice capture and playback

**Tasks**:
1. Implement `VoiceModule.js` with state machine
2. Implement `AudioQueue.js` for playback
3. Add voice UI components (mic button, waveform, states)
4. Add mute/text-only mode toggle
5. Handle low-confidence fallback UX
6. Add accessibility features (visual feedback)
7. Cross-browser testing

**Deliverables**:
- `static/js/voice/*.js` modules
- Updated `index.html` with voice UI
- CSS animations for voice states

**Acceptance Criteria**:
- Voice capture works on Chrome, Firefox, Edge
- Clear visual feedback for all states
- Graceful fallback to text input

---

### Phase 35: Kiosk Hardening

**Goal**: Production readiness for physical kiosk

**Tasks**:
1. Hardware integration testing on RPi5
2. Wake word detection (optional: "Hey CoCo")
3. Ambient noise handling
4. Auto-recovery from audio device errors
5. Performance optimization
6. Security audit (audio data handling)
7. User acceptance testing

**Deliverables**:
- Optimized models for RPi5
- Hardware setup documentation
- Performance benchmarks

**Acceptance Criteria**:
- 95% uptime in 24-hour test
- <8s average response time
- No audio data persisted beyond session

---

### Phase 36: Multilingual Support (Future)

**Goal**: Support for Filipino and other languages

**Tasks**:
1. Evaluate multilingual Whisper models
2. Add language detection
3. Source Filipino TTS voices
4. Implement language switching UI
5. Test with Filipino campus terms

---

## 9. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **STT accuracy too low** | Users frustrated, abandon voice | Medium | 1. Use Whisper base instead of tiny<br>2. Domain-specific fine-tuning<br>3. Always offer text fallback |
| **Latency too high on RPi5** | Poor kiosk UX | Medium | 1. Async processing with progress indicator<br>2. Streaming TTS (sentence-by-sentence)<br>3. Model quantization |
| **Microphone hardware failures** | Voice unusable | Low | 1. Auto-detect mic availability<br>2. Graceful fallback to text-only<br>3. Health check endpoint |
| **Ambient noise in kiosk location** | Poor transcription | High | 1. Noise-suppressing microphone<br>2. Push-to-talk mode<br>3. Confidence threshold triggers text input |
| **Privacy concerns (audio recording)** | User distrust | Medium | 1. No audio persistence beyond request<br>2. Clear privacy indicator<br>3. Opt-out setting |
| **TTS voice quality** | Unprofessional impression | Low | 1. Test multiple Piper voices<br>2. Fall back to cloud TTS if needed<br>3. Allow text-only preference |
| **Model size exceeds RPi5 memory** | OOM crashes | Low | 1. Use quantized models<br>2. Lazy loading<br>3. Memory monitoring |
| **Voice bypasses grounding** | Hallucinated answers | Critical | 1. Voice is I/O only - all queries go through `/chat`<br>2. No special voice code paths in RAG<br>3. Extensive testing |

---

## 10. Security & Privacy Considerations

### 10.1 Audio Data Handling

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUDIO DATA LIFECYCLE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Microphone] ──► [Browser Memory] ──► [HTTPS Upload] ──►          │
│                        │                                            │
│                        │ (never written to disk)                   │
│                        ▼                                            │
│              [Backend RAM Buffer] ──► [STT Engine]                 │
│                        │                      │                     │
│                        │                      ▼                     │
│                        │               [Text Only]                  │
│                        │                      │                     │
│                        ▼                      │                     │
│              [DELETED immediately]            │                     │
│                                               ▼                     │
│                                   [Normal /chat flow]               │
│                                               │                     │
│                                               ▼                     │
│                                   [TTS Audio Generated]            │
│                                               │                     │
│                    (stored 5min max) ◄────────┘                    │
│                           │                                         │
│                           ▼                                         │
│                    [Auto-deleted]                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

GUARANTEES:
- Raw audio NEVER written to disk
- Raw audio NEVER logged
- Transcription text follows normal query logging (privacy-safe)
- TTS audio auto-deleted after 5 minutes
- No cloud services by default (offline STT/TTS)
```

### 10.2 Security Checklist

- [ ] Audio upload endpoint has rate limiting
- [ ] Audio file size limit enforced (10MB max)
- [ ] Audio format validation before processing
- [ ] No audio data in error logs
- [ ] TTS audio stored with random UUID, not query-based names
- [ ] HTTPS required for all voice endpoints
- [ ] Microphone permission clearly requested with explanation

---

## 11. Summary

This proposal outlines a **production-grade voice integration** for CoCo that:

1. **Preserves all existing guarantees** - Voice is purely an I/O modality layer; all RAG, grounding, and determinism rules remain unchanged
2. **Prioritizes offline operation** - Whisper.cpp and Piper TTS run entirely on RPi5
3. **Handles errors gracefully** - Low STT confidence triggers text fallback; TTS failures don't block text responses
4. **Respects privacy** - No audio persistence, no cloud by default
5. **Follows clean architecture** - Voice logic completely decoupled from RAG logic

**Recommended starting phase**: Phase 32 (Voice Infrastructure Foundation)

**Estimated timeline**: 4 phases, each approximately 1-2 weeks of focused development

---

## Appendix A: Library Installation Commands

```bash
# Whisper.cpp (ARM64 optimized)
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make -j4
./models/download-ggml-model.sh tiny.en

# Piper TTS
pip install piper-tts
# Download voice model
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/voice-en_US-amy-medium.tar.gz
tar -xzf voice-en_US-amy-medium.tar.gz -C models/piper/

# espeak-ng (fallback)
sudo apt-get install espeak-ng

# Python dependencies
pip install soundfile pydub numpy
```

## Appendix B: Quick Start Guide

```bash
# 1. Set environment variables
export VOICE_ENABLED=true
export WHISPER_MODEL_PATH=/opt/coco/models/whisper/ggml-tiny.en.bin
export PIPER_MODEL_PATH=/opt/coco/models/piper/en_US-amy-medium.onnx

# 2. Start the server
cd campus_rag_chatbot
python app.py

# 3. Test voice status
curl http://localhost:8000/voice/status

# 4. Test TTS
curl -X POST http://localhost:8000/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, welcome to CoCo!"}' \
  --output test.wav

# 5. Test STT
curl -X POST http://localhost:8000/voice/transcribe \
  -F "audio=@test_audio.wav"
```
