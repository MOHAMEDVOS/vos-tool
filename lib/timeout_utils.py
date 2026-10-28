"""
Timeout calculation utilities for progressive timeouts based on file duration.
"""
from typing import Optional
from config import ProcessingConfig


def _calculate_timeout(
    audio_duration_seconds: Optional[float],
    base_timeout: int,
    per_minute: int,
    minimum: int,
    maximum: int,
) -> int:
    if audio_duration_seconds is None:
        return base_timeout

    duration_minutes = audio_duration_seconds / 60.0
    timeout = base_timeout + (duration_minutes * per_minute)
    return int(min(max(minimum, timeout), maximum))


def calculate_rebuttal_timeout(audio_duration_seconds: Optional[float] = None) -> int:
    """Calculate the rebuttal detection timeout from audio duration."""
    return _calculate_timeout(
        audio_duration_seconds,
        ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_BASE,
        ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE,
        ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_MIN,
        ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_MAX,
    )


def calculate_transcription_timeout(audio_duration_seconds: Optional[float] = None) -> int:
    """Calculate the transcription timeout from audio duration."""
    return _calculate_timeout(
        audio_duration_seconds,
        ProcessingConfig.TRANSCRIPTION_TIMEOUT_BASE,
        ProcessingConfig.TRANSCRIPTION_TIMEOUT_PER_MINUTE,
        ProcessingConfig.TRANSCRIPTION_TIMEOUT_MIN,
        ProcessingConfig.TRANSCRIPTION_TIMEOUT_MAX,
    )
