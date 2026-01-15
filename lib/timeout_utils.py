"""
Timeout calculation utilities for progressive timeouts based on file duration.
"""
from typing import Optional
from config.constants import ProcessingConfig


def calculate_rebuttal_timeout(audio_duration_seconds: Optional[float] = None) -> int:
    """
    Calculate appropriate timeout for rebuttal detection based on audio duration.
    
    For short files (30-60s), uses shorter timeout (180s = 3 min).
    For longer files, scales up proportionally.
    
    Formula: max(MIN, min(BASE + (duration_minutes * PER_MINUTE), MAX))
    
    Args:
        audio_duration_seconds: Duration of audio file in seconds (optional)
        
    Returns:
        Timeout in seconds
    """
    if audio_duration_seconds is None:
        # Default to base timeout if duration unknown
        return ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_BASE
    
    duration_minutes = audio_duration_seconds / 60.0
    
    # Calculate progressive timeout
    timeout = (
        ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_BASE +
        (duration_minutes * ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_PER_MINUTE)
    )
    
    # Apply min/max bounds
    timeout = max(ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_MIN, timeout)
    timeout = min(timeout, ProcessingConfig.REBUTTAL_DETECTION_TIMEOUT_MAX)
    
    return int(timeout)


def calculate_transcription_timeout(audio_duration_seconds: Optional[float] = None) -> int:
    """
    Calculate appropriate timeout for transcription based on audio duration.
    
    Args:
        audio_duration_seconds: Duration of audio file in seconds (optional)
        
    Returns:
        Timeout in seconds
    """
    if audio_duration_seconds is None:
        return ProcessingConfig.TRANSCRIPTION_TIMEOUT_BASE
    
    duration_minutes = audio_duration_seconds / 60.0
    
    timeout = (
        ProcessingConfig.TRANSCRIPTION_TIMEOUT_BASE +
        (duration_minutes * ProcessingConfig.TRANSCRIPTION_TIMEOUT_PER_MINUTE)
    )
    
    timeout = max(ProcessingConfig.TRANSCRIPTION_TIMEOUT_MIN, timeout)
    timeout = min(timeout, ProcessingConfig.TRANSCRIPTION_TIMEOUT_MAX)
    
    return int(timeout)
