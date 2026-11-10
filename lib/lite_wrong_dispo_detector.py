"""Lite Audit Wrong Dispo check: was this actually a Dead Call or Unknown, whatever got logged?

Lite Audit has no transcript, so this looks at the audio only.

- A truly silent owner channel for the whole call is a Dead Call no matter what
  disposition the agent picked (Wrong Number, Not Interested, etc.) -- so that
  check applies to every disposition, not just "Dead Call" and "Unknown".
- A short call (<=7s) where the owner channel never reaches real speech but
  isn't silent either (just static/air noise) is an Unknown no matter what got
  logged, with the same exception: Mohamed asked to leave "Dead Call" out of
  this one, so a short, static-only "Dead Call" stays uncaught for now.
- The remaining direction (logged Dead Call but the owner clearly spoke, so it
  should've been Unknown) only makes sense when Dead Call was actually logged --
  generalizing it would flag almost every real conversation, since any call has
  well over 300ms of owner speech.

Thresholds were measured on 495 real recordings, see
docs/superpowers/plans/2026-11-05-lite-dead-vs-unknown-dispo.md.
"""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment

_FRAME_MS = 50
_SOUND_RMS = 150
# Many Dead Calls open with a phone-system beep of about 300 ms near 660 Hz on the
# owner channel. A frame with this share of its energy in a few frequency bins is
# a tone, not a person.
_TONE_ENERGY_SHARE = 0.9
_TONE_BINS = 5
# MP3 encoding leaves faint noise, so a silent channel is rarely exactly 0.
_SILENT_PEAK = 100
# A faint steady hiss from the owner's side means Unknown, not Dead Call, though it
# never reaches _SOUND_RMS. Mohamed listened to 11 flagged calls: the 2 he confirmed silent
# measured about 3 here, and 8 of the 9 with air sound measured 5.9 or more. Energy
# below 200 Hz is left out because the confirmed-silent calls can carry a line hum.
#
# 2026-11-09: lowered from 4.5 after Mohamed reviewed two flagged "Unknown"
# calls -- (317) 777-0900 and (317) 712-7437, both 12s, air_level 3.00-3.05 --
# and confirmed by ear it's line static, not dead silence. That readout sits
# right where the "confirmed silent" calibration above said ~3 was silent, so
# this call overrides that assumption rather than refining it: static this
# faint isn't worth flagging the agent over. Per Mohamed: don't be strict here,
# a bunch of invalid samples isn't acceptable. New ceiling sits below both
# measured values with a small margin.
_AIR_MIN_HZ = 200
_AIR_PERCENTILE = 90
_SILENT_AIR_LEVEL = 2.5
_MIN_OWNER_SOUND_MS = 300
# A call this short with no real owner speech (static/air noise only, not
# silence) is an Unknown regardless of what got logged -- past this length a
# quiet stretch could just be part of a longer real conversation.
_MAX_UNKNOWN_CALL_SECONDS = 7


def _owner_channel_levels(audio: AudioSegment) -> tuple[int, float, float]:
    """(ms of owner sound, loudest peak, air sound level), all outside tones and on a
    16-bit scale."""
    owner = audio.split_to_mono()[1]
    scale = 32768 / (1 << (8 * owner.sample_width - 1))
    samples = np.array(owner.get_array_of_samples(), dtype=np.float64) * scale

    frame_size = int(owner.frame_rate * _FRAME_MS / 1000)
    frame_count = len(samples) // frame_size
    if frame_count == 0:
        return 0, 0.0, 0.0
    frames = samples[: frame_count * frame_size].reshape(frame_count, frame_size)

    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    has_sound = rms >= _SOUND_RMS

    spectrum = np.abs(np.fft.rfft(frames * np.hanning(frame_size), axis=1)) ** 2
    top_bins = np.sort(spectrum, axis=1)[:, -_TONE_BINS:].sum(axis=1)
    is_tone = has_sound & (top_bins >= _TONE_ENERGY_SHARE * spectrum.sum(axis=1))

    # The frames either side of a tone hold its fade in and fade out.
    near_tone = is_tone | np.roll(is_tone, 1) | np.roll(is_tone, -1)
    if frame_count > 1:
        near_tone[0] = is_tone[0] or is_tone[1]
        near_tone[-1] = is_tone[-1] or is_tone[-2]

    outside_tone = ~near_tone
    sound_ms = int((has_sound & outside_tone).sum()) * _FRAME_MS
    if not outside_tone.any():
        return sound_ms, 0.0, 0.0
    peak = float(np.abs(frames[outside_tone]).max())

    freqs = np.fft.rfftfreq(frame_size, 1 / owner.frame_rate)
    total = spectrum.sum(axis=1)
    air_share = np.divide(
        spectrum[:, freqs >= _AIR_MIN_HZ].sum(axis=1), total,
        out=np.zeros(frame_count), where=total > 0,
    )
    air_level = np.sqrt(rms ** 2 * air_share)[outside_tone]
    return sound_ms, peak, float(np.percentile(air_level, _AIR_PERCENTILE))


def lite_wrong_dispo_detail(audio: AudioSegment, disposition: str | None) -> tuple[str, str | None]:
    """("Yes"|"No", reason). Only stereo calls can flag."""
    logged = " ".join((disposition or "").lower().split())
    if not logged or audio.channels != 2:
        return "No", None

    sound_ms, peak, air_level = _owner_channel_levels(audio)
    actually_dead = peak <= _SILENT_PEAK and air_level <= _SILENT_AIR_LEVEL
    if actually_dead and logged != "dead call":
        reason = "Unk instead of Dead" if logged == "unknown" else f"{(disposition or '').strip()} instead of Dead"
        return "Yes", reason

    has_real_speech = sound_ms >= _MIN_OWNER_SOUND_MS
    is_short_call = len(audio) <= _MAX_UNKNOWN_CALL_SECONDS * 1000
    if (not actually_dead and not has_real_speech and is_short_call
            and logged not in ("unknown", "dead call")):
        return "Yes", f"{(disposition or '').strip()} instead of Unknown"

    if logged == "dead call" and has_real_speech:
        return "Yes", "Dead instead of Unk"
    return "No", None
