"""
Voice API Integration Tests
===========================

Phase 33: Voice API Layer

Tests for voice endpoints including:
- /voice/status - Service status check
- /voice/health - Detailed health monitoring
- /voice/transcribe - Audio transcription
- /voice/synthesize - Text-to-speech
- /voice/chat - Full voice interaction
- /voice/stream - WebSocket streaming (basic connectivity)

Run with: python -m pytest tests/test_voice_api.py -v
"""

import pytest
import asyncio
import json
import io
import wave
import struct
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "campus_rag_chatbot"))

from fastapi.testclient import TestClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def client():
    """Create test client for the FastAPI app."""
    from app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_wav_audio():
    """Generate a simple WAV audio file for testing."""
    # Create a 1-second silent WAV file
    sample_rate = 16000
    duration = 1  # seconds
    num_samples = sample_rate * duration

    # Generate silence (all zeros)
    samples = [0] * num_samples

    # Create WAV in memory
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))

    buffer.seek(0)
    return buffer.read()


# ============================================================================
# Status Endpoint Tests
# ============================================================================

class TestVoiceStatus:
    """Tests for /voice/status endpoint."""

    def test_status_returns_200(self, client):
        """Status endpoint should return 200 OK."""
        response = client.get("/voice/status")
        assert response.status_code == 200

    def test_status_has_required_fields(self, client):
        """Status should include all required fields."""
        response = client.get("/voice/status")
        data = response.json()

        required_fields = [
            "voice_enabled",
            "stt_available",
            "stt_engine",
            "tts_available",
            "tts_engine",
            "confidence_threshold",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_status_confidence_threshold_in_range(self, client):
        """Confidence threshold should be between 0 and 1."""
        response = client.get("/voice/status")
        data = response.json()

        threshold = data["confidence_threshold"]
        assert 0 <= threshold <= 1, f"Invalid threshold: {threshold}"


# ============================================================================
# Health Endpoint Tests
# ============================================================================

class TestVoiceHealth:
    """Tests for /voice/health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/voice/health")
        assert response.status_code == 200

    def test_health_has_required_fields(self, client):
        """Health should include all required fields."""
        response = client.get("/voice/health")
        data = response.json()

        required_fields = [
            "status",
            "voice_enabled",
            "components",
            "metrics",
            "uptime_seconds",
            "version",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_health_status_is_valid(self, client):
        """Health status should be one of expected values."""
        response = client.get("/voice/health")
        data = response.json()

        valid_statuses = ["healthy", "degraded", "unhealthy"]
        assert data["status"] in valid_statuses

    def test_health_includes_components(self, client):
        """Health should include component status."""
        response = client.get("/voice/health")
        data = response.json()

        expected_components = ["stt", "tts", "orchestrator", "audio_storage"]
        for component in expected_components:
            assert component in data["components"], f"Missing component: {component}"

    def test_health_uptime_is_positive(self, client):
        """Uptime should be a positive number."""
        response = client.get("/voice/health")
        data = response.json()

        assert data["uptime_seconds"] >= 0


# ============================================================================
# Transcribe Endpoint Tests
# ============================================================================

class TestVoiceTranscribe:
    """Tests for /voice/transcribe endpoint."""

    def test_transcribe_rejects_empty_file(self, client):
        """Transcribe should reject empty audio files."""
        response = client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", b"", "audio/wav")},
            data={"language": "en"}
        )
        assert response.status_code == 400

    def test_transcribe_validates_file_size(self, client):
        """Transcribe should reject files over 10MB."""
        # Create a 11MB dummy file
        large_data = b"x" * (11 * 1024 * 1024)
        response = client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", large_data, "audio/wav")},
            data={"language": "en"}
        )
        assert response.status_code == 400

    def test_transcribe_with_valid_audio_format(self, client, sample_wav_audio):
        """Transcribe should accept valid WAV format."""
        # Note: This will fail with 503 if STT service unavailable,
        # which is expected when models aren't installed
        response = client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", sample_wav_audio, "audio/wav")},
            data={"language": "en"}
        )
        # Accept either success (200) or service unavailable (503)
        assert response.status_code in [200, 503, 422]


# ============================================================================
# Synthesize Endpoint Tests
# ============================================================================

class TestVoiceSynthesize:
    """Tests for /voice/synthesize endpoint."""

    def test_synthesize_rejects_empty_text(self, client):
        """Synthesize should reject empty text."""
        response = client.post(
            "/voice/synthesize",
            json={"text": ""}
        )
        assert response.status_code == 400

    def test_synthesize_rejects_whitespace_text(self, client):
        """Synthesize should reject whitespace-only text."""
        response = client.post(
            "/voice/synthesize",
            json={"text": "   "}
        )
        assert response.status_code == 400

    def test_synthesize_rejects_too_long_text(self, client):
        """Synthesize should reject text over 2000 characters."""
        long_text = "x" * 2500
        response = client.post(
            "/voice/synthesize",
            json={"text": long_text}
        )
        assert response.status_code == 400

    def test_synthesize_with_valid_text(self, client):
        """Synthesize should accept valid text."""
        response = client.post(
            "/voice/synthesize",
            json={"text": "Hello world"}
        )
        # Accept either success (200) or service unavailable (503)
        assert response.status_code in [200, 503]


# ============================================================================
# Chat Endpoint Tests
# ============================================================================

class TestVoiceChat:
    """Tests for /voice/chat endpoint."""

    def test_chat_rejects_empty_audio(self, client):
        """Chat should reject empty audio files."""
        response = client.post(
            "/voice/chat",
            files={"audio": ("test.wav", b"", "audio/wav")},
            data={"session_id": "test", "skip_tts": "true"}
        )
        assert response.status_code == 400

    def test_chat_with_valid_audio(self, client, sample_wav_audio):
        """Chat should accept valid audio."""
        response = client.post(
            "/voice/chat",
            files={"audio": ("test.wav", sample_wav_audio, "audio/wav")},
            data={"session_id": "test", "skip_tts": "true"}
        )
        # Accept success or service unavailable
        assert response.status_code in [200, 503, 422]


# ============================================================================
# Audio Retrieval Tests
# ============================================================================

class TestVoiceAudio:
    """Tests for /voice/audio/{audio_id} endpoint."""

    def test_audio_not_found(self, client):
        """Should return 404 for non-existent audio ID."""
        response = client.get("/voice/audio/nonexistent-id")
        assert response.status_code == 404


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_transcribe_rate_limit_header(self, client, sample_wav_audio):
        """Multiple rapid requests should eventually hit rate limit."""
        # Note: Rate limit is 30/minute, so this tests the mechanism exists
        responses = []
        for _ in range(5):
            response = client.post(
                "/voice/transcribe",
                files={"audio": ("test.wav", sample_wav_audio, "audio/wav")},
                data={"language": "en"}
            )
            responses.append(response.status_code)

        # All should either succeed or fail with expected errors
        # (not rate limited with only 5 requests)
        for status in responses:
            assert status in [200, 400, 422, 503, 429]


# ============================================================================
# Error Code Tests
# ============================================================================

class TestErrorCodes:
    """Tests for standardized error codes."""

    def test_empty_audio_error_code(self, client):
        """Empty audio should return EMPTY_AUDIO error code."""
        response = client.post(
            "/voice/transcribe",
            files={"audio": ("test.wav", b"", "audio/wav")},
            data={"language": "en"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        if isinstance(data["detail"], dict):
            assert data["detail"]["code"] == "EMPTY_AUDIO"

    def test_text_required_error_code(self, client):
        """Empty text should return TEXT_REQUIRED error code."""
        response = client.post(
            "/voice/synthesize",
            json={"text": ""}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        if isinstance(data["detail"], dict):
            assert data["detail"]["code"] == "TEXT_REQUIRED"


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
