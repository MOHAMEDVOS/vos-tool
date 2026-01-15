"""
FFmpeg converter setup utilities.
"""
from pathlib import Path
from config.constants import FileConfig


def maybe_set_ffmpeg_converter() -> bool:
    """
    Set FFmpeg path if available.
    
    Checks for bundled ffmpeg first, then system ffmpeg.
    
    Returns:
        bool: True if FFmpeg is available, False otherwise
    """
    try:
        from pydub import AudioSegment
        import shutil
        
        # Check for bundled ffmpeg
        if FileConfig.FFMPEG_BIN_PATH.exists():
            AudioSegment.converter = str(FileConfig.FFMPEG_BIN_PATH)
            return True
        
        # Check system ffmpeg
        if shutil.which("ffmpeg"):
            return True
    except Exception:
        return False
    return False
