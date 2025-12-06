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
from .audio_processor import AudioProcessor, RESULT_KEYS, convert_all_to_dataframe_format, convert_to_dataframe_format

__all__ = [
    "AudioProcessor",
    "RESULT_KEYS",
    "convert_to_dataframe_format",
    "convert_all_to_dataframe_format",
    "voice_activity_detection",
    "releasing_detection",
    "late_hello_detection",
    "debug_audio_analysis",
    "IntroductionClassifier",
    "app_settings",
]

