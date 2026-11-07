"""
Audio pipeline package consolidating audio processing, detection, and transcription logic.
"""

from .detections import (
    app_settings,
    voice_activity_detection,
    releasing_detection,
    late_hello_detection,
    debug_audio_analysis,
    IntroductionClassifier,
)
from .audio_processor import AudioProcessor, RESULT_KEYS

__all__ = [
    "AudioProcessor",
    "RESULT_KEYS",
    "voice_activity_detection",
    "releasing_detection",
    "late_hello_detection",
    "debug_audio_analysis",
    "IntroductionClassifier",
    "app_settings",
]

