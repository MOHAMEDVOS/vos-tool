"""Tests for the Lite Audit's Dead Call vs Unknown check. Synthetic audio, no DB, no network."""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from pydub import AudioSegment

from lib.dashboard_manager import DashboardManager
from lib.lite_wrong_dispo_detector import lite_wrong_dispo_detail
from processing.batch_engine import process_single_file_lite

RATE = 8000
SECONDS = 8


def _mono(samples):
    pcm = np.clip(samples, -32768, 32767).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=RATE, sample_width=2, channels=1)


def _silence(seconds=SECONDS):
    return np.zeros(int(RATE * seconds))


def _noise(seconds, loudness=1500, seed=1):
    return np.random.default_rng(seed).normal(0, loudness, int(RATE * seconds))


def _tone(seconds, hz=660, loudness=4000):
    return loudness * np.sin(2 * np.pi * hz * np.arange(int(RATE * seconds)) / RATE)


def _owner(*parts):
    """Place (start_second, samples) parts on a silent owner channel."""
    channel = _silence()
    for start, samples in parts:
        begin = int(RATE * start)
        channel[begin: begin + len(samples)] = samples
    return channel


def _call(owner_channel):
    agent = _mono(_owner((0.5, _noise(2, seed=2))))
    return AudioSegment.from_mono_audiosegments(agent, _mono(owner_channel))


# ── Spec table ───────────────────────────────────────────────────────────────

def test_unknown_with_silent_owner_flags():
    assert lite_wrong_dispo_detail(_call(_silence()), "Unknown") == ("Yes", "Unk instead of Dead")


def test_dead_call_with_owner_sound_flags():
    audio = _call(_owner((2, _noise(1))))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("Yes", "Dead instead of Unk")


def test_unknown_with_faint_but_audible_owner_sound_not_flagged():
    audio = _call(_owner((2, _noise(0.2, loudness=300))))
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("No", None)


def test_dead_call_with_silent_owner_not_flagged():
    assert lite_wrong_dispo_detail(_call(_silence()), "Dead Call") == ("No", None)


# ── Real-recording shapes ────────────────────────────────────────────────────

def test_codec_noise_counts_as_silent():
    audio = _call(_noise(SECONDS, loudness=2))
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("Yes", "Unk instead of Dead")
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)


def test_air_sound_on_the_owner_side_makes_unknown_valid():
    # Mohamed listened to these: a faint steady hiss still counts as Unknown.
    audio = _call(_noise(SECONDS, loudness=11))
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("No", None)


def test_air_sound_on_the_owner_side_makes_dead_call_wrong():
    audio = _call(_noise(SECONDS, loudness=11))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("Yes", "Dead instead of Unk")


def test_low_line_hum_alone_keeps_dead_call_valid():
    audio = _call(_tone(SECONDS, hz=60, loudness=10))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)


def test_air_sound_in_only_part_of_the_call_makes_unknown_valid():
    audio = _call(_owner((1, _noise(2, loudness=18))))
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("No", None)


def test_low_line_hum_alone_counts_as_silent():
    # Real recordings with no audible owner sound carry a faint hum under 200 Hz.
    audio = _call(_tone(SECONDS, hz=60, loudness=10))
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("Yes", "Unk instead of Dead")


def test_phone_system_beep_is_not_owner_sound():
    audio = _call(_owner((0.1, _tone(0.3))))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("Yes", "Unk instead of Dead")


def test_beep_plus_real_sound_on_a_dead_call_flags():
    audio = _call(_owner((0.1, _tone(0.3)), (3, _noise(0.6))))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("Yes", "Dead instead of Unk")


def test_brief_click_on_a_dead_call_is_too_little_to_flag():
    audio = _call(_owner((3, _noise(0.1))))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)


def test_between_silent_and_sound_flags_neither():
    audio = _call(_owner((3, _noise(0.1))))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)
    assert lite_wrong_dispo_detail(audio, "Unknown") == ("No", None)


def test_agent_channel_sound_is_ignored():
    agent = _mono(_noise(SECONDS))
    audio = AudioSegment.from_mono_audiosegments(agent, _mono(_silence()))
    assert lite_wrong_dispo_detail(audio, "Dead Call") == ("No", None)


# ── Scope ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("disposition", [
    "Decision Maker - NYI", "Wrong Number", "DNC - Unknown", "DNC - Decision Maker",
    "Voicemail", "Spanish Speaker", "", None,
])
def test_other_dispositions_are_never_flagged(disposition):
    assert lite_wrong_dispo_detail(_call(_silence()), disposition) == ("No", None)
    assert lite_wrong_dispo_detail(_call(_owner((2, _noise(1)))), disposition) == ("No", None)


@pytest.mark.parametrize("disposition", ["unknown", "  UNKNOWN ", "Unknown"])
def test_disposition_spelling_variants(disposition):
    assert lite_wrong_dispo_detail(_call(_silence()), disposition)[0] == "Yes"


def test_mono_recording_has_no_owner_channel_to_check():
    assert lite_wrong_dispo_detail(_mono(_silence()), "Unknown") == ("No", None)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def _write_call(tmp_path, disposition, owner_channel):
    path = tmp_path / f"Agent Name _ Nov 5, 2_18PM _ (516) 555-0100 _ {disposition}.mp3"
    _call(owner_channel).export(path, format="mp3")
    return path


def test_lite_pipeline_flags_a_real_mp3(tmp_path):
    result = process_single_file_lite(_write_call(tmp_path, "Unknown", _silence()))
    assert result["Wrong Dispo Detection"] == "Yes"
    assert result["Wrong Dispo Reason"] == "Unk instead of Dead"


def test_lite_pipeline_leaves_other_dispositions_alone(tmp_path):
    result = process_single_file_lite(_write_call(tmp_path, "Wrong Number", _silence()))
    assert result["Wrong Dispo Detection"] == "No"
    assert result["Wrong Dispo Reason"] == ""


def test_lite_pipeline_skips_campaign_audits(tmp_path):
    path = _write_call(tmp_path, "Unknown", _silence())
    result = process_single_file_lite(path, additional_metadata={"Campaign Name": "Test"})
    assert result["Wrong Dispo Detection"] == "No"


def test_lite_pipeline_survives_a_check_failure(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("bad audio")

    monkeypatch.setattr("lib.lite_wrong_dispo_detector.lite_wrong_dispo_detail", boom)
    result = process_single_file_lite(_write_call(tmp_path, "Unknown", _silence()))
    assert result["Wrong Dispo Detection"] == "No"
    assert result["Releasing Detection"] in ("Yes", "No")


# ── Saved and read back ──────────────────────────────────────────────────────

class _FakeDb:
    def __init__(self):
        self.rows = []

    def execute_values_batch(self, query, params_list, page_size=100):
        for username, agent_name, file_name, file_path, results in params_list:
            self.rows.append({
                "username": username, "agent_name": agent_name, "file_name": file_name,
                "file_path": file_path, "detection_results": results, "created_at": None,
            })
        return len(params_list)

    def execute_query(self, query, params=None, fetch=False):
        return self.rows


def _manager():
    manager = object.__new__(DashboardManager)
    manager._db_manager = _FakeDb()
    manager.get_shared_users = lambda username: [username]
    return manager


def _lite_row(**extra):
    return {
        "Agent Name": "Agent", "File Name": "a.mp3", "File Path": "a.mp3",
        "Releasing Detection": "No", "Late Hello Detection": "No", **extra,
    }


def test_flag_survives_save_and_read():
    manager = _manager()
    row = _lite_row(**{"Wrong Dispo Detection": "Yes", "Wrong Dispo Reason": "Unk instead of Dead"})
    manager.save_lite_audit_results(pd.DataFrame([row]), "tester")
    stored = json.loads(manager._db_manager.rows[0]["detection_results"])
    assert stored["wrong_dispo_detection"] == "Yes"

    loaded = manager.get_combined_lite_audit_data("tester").iloc[0]
    assert loaded["Wrong Dispo Detection"] == "Yes"
    assert loaded["Wrong Dispo Reason"] == "Unk instead of Dead"


def test_rows_without_the_check_read_back_as_not_flagged():
    manager = _manager()
    manager.save_lite_audit_results(pd.DataFrame([_lite_row()]), "tester")
    loaded = manager.get_combined_lite_audit_data("tester").iloc[0]
    assert loaded["Wrong Dispo Detection"] == "No"
    assert loaded["Wrong Dispo Reason"] == ""
