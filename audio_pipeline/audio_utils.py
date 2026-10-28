"""Shared audio-channel helpers for the single-file processors."""

from pathlib import Path

from pydub import AudioSegment


def extract_agent_audio(audio: AudioSegment) -> AudioSegment:
    """Return the agent channel, converting audio with more than two channels to mono."""
    if audio.channels == 1:
        return audio

    if audio.channels == 2:
        return audio.split_to_mono()[0]

    return audio.set_channels(1)


def extract_basic_file_metadata(file_path: Path) -> tuple[str, str, str, str]:
    """Parse the filename fields used by the fast, optimized, and semantic processors."""
    stem = file_path.stem
    parts = stem.split(" _ ")

    if len(parts) == 4:
        agent_name_raw, timestamp, phone_number, disposition = parts
    elif len(parts) == 2:
        agent_name_raw, phone_number = parts
        timestamp = ""
        disposition = ""
    else:
        agent_name_raw = stem
        phone_number = ""
        timestamp = ""
        disposition = ""

    agent_name_raw = agent_name_raw.replace("-", "").replace(".", "")
    agent_name = agent_name_raw.replace("([a-z])([A-Z])", r"\1 \2")
    return agent_name, phone_number, timestamp, disposition
