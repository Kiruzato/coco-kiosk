"""
Audio Utilities
===============

Phase 32: Voice Infrastructure Foundation

Audio format conversion, normalization, and validation utilities.
Supports conversion between common audio formats for STT/TTS processing.

Supported Input Formats:
- WAV (PCM)
- WebM/Opus (browser recording)
- MP3

Output Format:
- WAV (16kHz mono for STT, 22.05kHz mono for TTS playback)
"""

import io
import wave
import struct
import logging
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioInfo:
    """Metadata about an audio file."""
    sample_rate: int
    channels: int
    duration_seconds: float
    format: str
    sample_width: int  # bytes per sample


class AudioConversionError(Exception):
    """Raised when audio conversion fails."""
    pass


class AudioValidationError(Exception):
    """Raised when audio validation fails."""
    pass


def detect_audio_format(audio_data: bytes) -> str:
    """
    Detect audio format from file header.

    Args:
        audio_data: Raw audio bytes

    Returns:
        Format string: 'wav', 'webm', 'mp3', 'ogg', or 'unknown'
    """
    if len(audio_data) < 12:
        return 'unknown'

    # WAV: starts with "RIFF" and contains "WAVE"
    if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
        return 'wav'

    # WebM: starts with EBML header (0x1A 0x45 0xDF 0xA3)
    if audio_data[:4] == b'\x1a\x45\xdf\xa3':
        return 'webm'

    # MP3: starts with ID3 tag or frame sync
    if audio_data[:3] == b'ID3' or (audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0):
        return 'mp3'

    # OGG: starts with "OggS"
    if audio_data[:4] == b'OggS':
        return 'ogg'

    return 'unknown'


def get_audio_info(audio_data: bytes) -> AudioInfo:
    """
    Get metadata from WAV audio data.

    Args:
        audio_data: Raw WAV bytes

    Returns:
        AudioInfo with sample rate, channels, duration, etc.
    """
    fmt = detect_audio_format(audio_data)

    if fmt != 'wav':
        raise AudioValidationError(f"Cannot get info for format: {fmt}. Convert to WAV first.")

    try:
        with io.BytesIO(audio_data) as f:
            with wave.open(f, 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                duration = frames / float(rate)

                return AudioInfo(
                    sample_rate=rate,
                    channels=channels,
                    duration_seconds=duration,
                    format='wav',
                    sample_width=sample_width
                )
    except Exception as e:
        raise AudioValidationError(f"Failed to read WAV info: {e}")


def validate_audio(audio_data: bytes, max_duration_seconds: int = 30, max_size_mb: int = 10) -> AudioInfo:
    """
    Validate audio data for processing.

    Args:
        audio_data: Raw audio bytes
        max_duration_seconds: Maximum allowed duration
        max_size_mb: Maximum file size in MB

    Returns:
        AudioInfo if valid

    Raises:
        AudioValidationError: If audio is invalid or exceeds limits
    """
    # Check size
    size_mb = len(audio_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise AudioValidationError(f"Audio file too large: {size_mb:.1f}MB (max {max_size_mb}MB)")

    # Detect format
    fmt = detect_audio_format(audio_data)
    if fmt == 'unknown':
        raise AudioValidationError("Unknown audio format. Supported: WAV, WebM, MP3, OGG")

    # For WAV, we can check duration directly
    if fmt == 'wav':
        info = get_audio_info(audio_data)
        if info.duration_seconds > max_duration_seconds:
            raise AudioValidationError(
                f"Audio too long: {info.duration_seconds:.1f}s (max {max_duration_seconds}s)"
            )
        return info

    # For other formats, return basic info (duration check happens after conversion)
    return AudioInfo(
        sample_rate=0,  # Unknown until converted
        channels=0,
        duration_seconds=0,
        format=fmt,
        sample_width=0
    )


def normalize_audio(
    audio_data: bytes,
    target_sample_rate: int = 16000,
    target_channels: int = 1
) -> bytes:
    """
    Normalize audio to target format for STT processing.

    Converts audio to:
    - WAV format
    - Specified sample rate (default 16kHz for Whisper)
    - Mono channel

    Args:
        audio_data: Raw audio bytes (any supported format)
        target_sample_rate: Target sample rate in Hz
        target_channels: Target number of channels (1 for mono)

    Returns:
        Normalized WAV audio bytes
    """
    fmt = detect_audio_format(audio_data)
    logger.info(f"[AUDIO] Input format: {fmt}, size: {len(audio_data)} bytes")

    if fmt == 'wav':
        normalized = _normalize_wav(audio_data, target_sample_rate, target_channels)
    elif fmt in ('webm', 'ogg', 'mp3'):
        # These formats require external libraries (pydub/ffmpeg)
        # For now, we'll try to use pydub if available
        normalized = _convert_with_pydub(audio_data, fmt, target_sample_rate, target_channels)
    else:
        raise AudioConversionError(f"Cannot convert format: {fmt}")

    # Trim leading silence to reduce unnecessary STT processing
    return trim_leading_silence(normalized)


def _normalize_wav(
    audio_data: bytes,
    target_sample_rate: int,
    target_channels: int
) -> bytes:
    """Normalize WAV audio to target format."""
    try:
        with io.BytesIO(audio_data) as f:
            with wave.open(f, 'rb') as wav:
                current_rate = wav.getframerate()
                current_channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())

        # If already at target format, return as-is
        if current_rate == target_sample_rate and current_channels == target_channels:
            return audio_data

        # Convert to target format
        # Note: This is a basic implementation. For production, use scipy or pydub
        # for proper resampling with anti-aliasing.

        # Convert stereo to mono if needed
        if current_channels == 2 and target_channels == 1:
            frames = _stereo_to_mono(frames, sample_width)
            current_channels = 1

        # Resample if needed (basic linear interpolation)
        if current_rate != target_sample_rate:
            frames = _resample_linear(frames, current_rate, target_sample_rate, sample_width)

        # Write output WAV
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav_out:
            wav_out.setnchannels(target_channels)
            wav_out.setsampwidth(sample_width)
            wav_out.setframerate(target_sample_rate)
            wav_out.writeframes(frames)

        return output.getvalue()

    except Exception as e:
        raise AudioConversionError(f"WAV normalization failed: {e}")


def _stereo_to_mono(frames: bytes, sample_width: int) -> bytes:
    """Convert stereo audio to mono by averaging channels."""
    if sample_width == 2:  # 16-bit
        fmt = '<h'
        samples = struct.unpack(f'<{len(frames) // 2}h', frames)
        mono_samples = []
        for i in range(0, len(samples), 2):
            avg = (samples[i] + samples[i + 1]) // 2
            mono_samples.append(avg)
        return struct.pack(f'<{len(mono_samples)}h', *mono_samples)
    else:
        # For other bit depths, just take left channel
        step = sample_width * 2
        return b''.join(frames[i:i + sample_width] for i in range(0, len(frames), step))


def _resample_linear(frames: bytes, src_rate: int, dst_rate: int, sample_width: int) -> bytes:
    """
    Basic linear interpolation resampling.

    Note: This is a simplified implementation. For production quality,
    use scipy.signal.resample or pydub which handle anti-aliasing properly.
    """
    if sample_width != 2:
        raise AudioConversionError("Resampling only supports 16-bit audio")

    samples = struct.unpack(f'<{len(frames) // 2}h', frames)
    ratio = dst_rate / src_rate
    new_length = int(len(samples) * ratio)

    resampled = []
    for i in range(new_length):
        src_idx = i / ratio
        idx_low = int(src_idx)
        idx_high = min(idx_low + 1, len(samples) - 1)
        frac = src_idx - idx_low

        # Linear interpolation
        sample = int(samples[idx_low] * (1 - frac) + samples[idx_high] * frac)
        resampled.append(max(-32768, min(32767, sample)))

    return struct.pack(f'<{len(resampled)}h', *resampled)


def _convert_with_pydub(
    audio_data: bytes,
    fmt: str,
    target_sample_rate: int,
    target_channels: int
) -> bytes:
    """
    Convert audio using pydub (requires ffmpeg).

    Falls back gracefully if pydub/ffmpeg not available.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        raise AudioConversionError(
            f"Cannot convert {fmt} format: pydub not installed. "
            "Install with: pip install pydub"
        )

    try:
        logger.info(f"[AUDIO] Converting {fmt} with pydub, input size: {len(audio_data)} bytes")

        # Load audio
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format=fmt)

        logger.info(f"[AUDIO] Loaded: channels={audio.channels}, rate={audio.frame_rate}, "
                   f"duration={len(audio)/1000:.2f}s, dBFS={audio.dBFS:.1f}, "
                   f"sample_width={audio.sample_width}")

        # Convert to mono if needed
        if target_channels == 1 and audio.channels > 1:
            audio = audio.set_channels(1)

        # Resample if needed
        if audio.frame_rate != target_sample_rate:
            audio = audio.set_frame_rate(target_sample_rate)

        # CRITICAL: Ensure 16-bit audio (Whisper requires 16-bit PCM)
        if audio.sample_width != 2:
            logger.info(f"[AUDIO] Converting from {audio.sample_width*8}-bit to 16-bit")
            audio = audio.set_sample_width(2)

        # Export as WAV (16-bit PCM)
        output = io.BytesIO()
        audio.export(output, format='wav')
        result = output.getvalue()

        logger.info(f"[AUDIO] Converted to WAV: {len(result)} bytes, 16-bit")
        return result

    except Exception as e:
        logger.error(f"[AUDIO] pydub conversion failed: {e}")
        raise AudioConversionError(f"pydub conversion failed: {e}")


def trim_leading_silence(
    audio_data: bytes,
    threshold_rms: float = 500.0,
    consecutive_windows: int = 3,
    buffer_ms: int = 200,
    window_ms: int = 20,
) -> bytes:
    """
    Trim silence from the beginning of WAV audio.

    Scans the audio in small windows and finds the point where RMS
    exceeds the threshold for several consecutive windows (sustained
    speech, not a brief noise spike).  Keeps a safety buffer before
    that point to avoid clipping the onset of speech.

    Args:
        audio_data: WAV audio bytes (16-bit PCM)
        threshold_rms: RMS amplitude that indicates speech.
                       16-bit PCM range is -32768..32767; ambient noise
                       with browser noise suppression is typically 100-400
                       RMS, speech onset is ~500+.
        consecutive_windows: Number of consecutive windows above threshold
                             required to confirm speech (avoids false
                             triggers from brief noise spikes).
        buffer_ms: Milliseconds of audio to keep before detected speech
        window_ms: Size of each analysis window in milliseconds

    Returns:
        WAV audio bytes with leading silence removed
    """
    try:
        with io.BytesIO(audio_data) as f:
            with wave.open(f, 'rb') as wav:
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                n_frames = wav.getnframes()
                frames = wav.readframes(n_frames)

        if sample_width != 2 or channels != 1:
            logger.info("[AUDIO] Silence trim skipped: audio is not 16-bit mono")
            return audio_data

        samples = struct.unpack(f'<{len(frames) // 2}h', frames)
        window_size = int(sample_rate * window_ms / 1000)
        original_duration = len(samples) / sample_rate

        # Scan windows and find sustained speech start
        above_count = 0
        speech_start_sample = None

        for i in range(0, len(samples) - window_size, window_size):
            window = samples[i:i + window_size]
            rms = (sum(s * s for s in window) / len(window)) ** 0.5

            if rms >= threshold_rms:
                above_count += 1
                if above_count >= consecutive_windows:
                    # Speech confirmed — mark the start of the first
                    # above-threshold window in this consecutive run
                    speech_start_sample = i - (consecutive_windows - 1) * window_size
                    break
            else:
                above_count = 0

        if speech_start_sample is None:
            logger.info(
                f"[AUDIO] Silence trim: no sustained speech detected in "
                f"{original_duration:.2f}s audio (threshold={threshold_rms}). "
                f"Sending full audio to STT."
            )
            return audio_data

        # Apply safety buffer (go back buffer_ms before speech start)
        buffer_samples = int(sample_rate * buffer_ms / 1000)
        trim_sample = max(0, speech_start_sample - buffer_samples)

        if trim_sample == 0:
            logger.info(
                f"[AUDIO] Silence trim: speech starts at "
                f"{speech_start_sample / sample_rate:.2f}s, within buffer "
                f"({buffer_ms}ms). No trimming needed for "
                f"{original_duration:.2f}s audio."
            )
            return audio_data

        trimmed_frames = frames[trim_sample * sample_width:]
        trimmed_duration = (len(samples) - trim_sample) / sample_rate
        trimmed_amount = original_duration - trimmed_duration

        logger.info(
            f"[AUDIO] Trimmed {trimmed_amount:.2f}s of leading silence "
            f"({original_duration:.2f}s -> {trimmed_duration:.2f}s)"
        )

        # Write trimmed WAV
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav_out:
            wav_out.setnchannels(channels)
            wav_out.setsampwidth(sample_width)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(trimmed_frames)

        return output.getvalue()

    except Exception as e:
        logger.warning(f"[AUDIO] Leading silence trim failed, using original: {e}")
        return audio_data


def create_wav_header(
    sample_rate: int,
    channels: int,
    sample_width: int,
    data_length: int
) -> bytes:
    """
    Create a WAV file header.

    Args:
        sample_rate: Sample rate in Hz
        channels: Number of channels
        sample_width: Bytes per sample
        data_length: Length of audio data in bytes

    Returns:
        WAV header bytes (44 bytes)
    """
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        data_length + 36,  # File size - 8
        b'WAVE',
        b'fmt ',
        16,  # Subchunk1 size
        1,   # Audio format (1 = PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        sample_width * 8,  # Bits per sample
        b'data',
        data_length
    )
    return header


def pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2
) -> bytes:
    """
    Convert raw PCM data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz
        channels: Number of channels
        sample_width: Bytes per sample (2 for 16-bit)

    Returns:
        Complete WAV file bytes
    """
    header = create_wav_header(sample_rate, channels, sample_width, len(pcm_data))
    return header + pcm_data
