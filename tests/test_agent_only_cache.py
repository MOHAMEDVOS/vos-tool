"""Tests for lib/agent_only_detector.py's cache hit and objection-gate wiring. No audio or API calls."""

import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import lib.agent_only_detector as detector_module
from lib.agent_only_detector import AgentOnlyRebuttalDetector, AgentOnlyTranscriptionEngine

DIALOGUE = "Agent: Is this right?\nOwner: No.\nAgent: You don't own a property?"
CACHED = {
    "transcript": "Is this right? No. You don't own a property?",
    "agent_transcript": "Is this right? You don't own a property?",
    "owner_transcript": "No.",
    "dialogue": DIALOGUE,
    "speakers": ["A", "B"],
    "utterances": [{"text": "Is this right?"}],
}


def _engine_with_cache(entry):
    engine = object.__new__(AgentOnlyTranscriptionEngine)
    cache = SimpleNamespace(get=lambda path: entry)
    engine.local_engine = SimpleNamespace(assemblyai_engine=SimpleNamespace(cache=cache))
    return engine


def test_cache_hit_matches_a_fresh_transcription():
    result = _engine_with_cache(CACHED).transcribe_agent_only("call.mp3", timeout=10)
    assert result["dialogue"] == DIALOGUE
    assert result["transcript"] == CACHED["agent_transcript"]
    assert result["full_transcript"] == CACHED["transcript"]
    assert result["owner_transcript"] == "No."
    assert result["transcription_method"] == "assemblyai_api_cached"


def test_cache_hit_on_an_old_entry_falls_back_to_the_full_text():
    old_entry = {"transcript": "Is this right? No.", "speakers": [], "utterances": []}
    result = _engine_with_cache(old_entry).transcribe_agent_only("call.mp3", timeout=10)
    assert result["transcript"] == "Is this right? No."
    assert result["dialogue"] == ""
    assert result["owner_transcript"] == ""


def _detector(dialogue):
    detector = object.__new__(AgentOnlyRebuttalDetector)
    detector.transcription_engine = SimpleNamespace(transcribe_agent_only=lambda *a, **k: {
        "transcript": "Is this right?", "dialogue": dialogue, "processing_time_ms": 1,
    })
    detector.egyptian_corrector = SimpleNamespace(apply_corrections=lambda text: (text, []))
    detector.semantic_engine = SimpleNamespace(detect_rebuttals=lambda *a, **k: ([], {}))
    detector.formatter = SimpleNamespace(format_result=lambda **kwargs: kwargs)
    return detector


def test_detector_passes_the_disposition_to_the_gate(monkeypatch):
    seen = []

    def fake_evaluate(dialogue, disposition=None):
        seen.append((dialogue, disposition))
        return {"verdict": "no_attempt", "objection_quote": None, "reason": "test"}

    monkeypatch.setattr(detector_module.objection_gate, "evaluate", fake_evaluate)
    _detector(DIALOGUE).detect_rebuttals_in_audio("call.mp3", disposition="Wrong Number")
    assert seen == [(DIALOGUE, "Wrong Number")]


@pytest.mark.parametrize("disposition,verdict", [
    ("Wrong Number", "no_attempt"),
    ("Decision Maker - NYI", "no_objection"),
])
def test_detector_stores_the_gate_verdict_for_the_disposition(disposition, verdict):
    result = _detector(DIALOGUE).detect_rebuttals_in_audio("call.mp3", disposition=disposition)
    assert result["metadata"]["objection_gate_verdict"] == verdict
