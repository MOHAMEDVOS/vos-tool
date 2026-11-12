"""Unit tests for lib/wrong_dispo_detector.py — pure logic, no DB, no I/O."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import lib.wrong_dispo_detector as wrong_dispo_detector
from lib.wrong_dispo_detector import wrong_dispo_detection, wrong_dispo_detail, wrong_dispo_reason

# Tier 2 (semantic) is enabled by default and would otherwise try to load the
# real sentence-transformers model on every "No" test below (any test where
# Tier 1 finds nothing falls through to it). Force it off for every test
# except the ones that explicitly want it -- they re-patch it themselves,
# which overrides this for just that test.
_REAL_GET_SEMANTIC_RESOURCES = wrong_dispo_detector._get_semantic_resources


@pytest.fixture(autouse=True)
def _disable_semantic_tier_by_default(monkeypatch):
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", lambda: (None, None))


def test_clear_dnc_phrase_with_wrong_number_flags():
    transcript = "Caller: please do not call me again, I'm not interested."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "Yes"


def test_clear_dnc_phrase_with_decision_maker_nyi_flags():
    transcript = "Owner: stop calling me, I already told you no."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_contraction_phrasing_matches_too():
    transcript = "Owner: don't call me again, please."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "Yes"


def test_correct_dnc_decision_maker_disposition_not_flagged():
    transcript = "Owner: do not call me again."
    assert wrong_dispo_detection(transcript, "DNC - Decision Maker") == "No"


def test_dnc_decision_maker_matches_regardless_of_dash_style_and_case():
    transcript = "Owner: stop calling this number."
    # hyphen (backend/api/scoring.py style)
    assert wrong_dispo_detection(transcript, "DNC - Decision Maker") == "No"
    # en-dash (lib/dashboard_manager.py style)
    assert wrong_dispo_detection(transcript, "DNC – Decision Maker") == "No"
    # case-insensitive
    assert wrong_dispo_detection(transcript, "dnc - decision maker") == "No"


def test_dnc_unknown_is_not_treated_as_correct_without_a_denial():
    # "DNC - Unknown" only counts as correct when the person says they aren't the
    # owner. See test_dnc_unknown_is_correct_for_a_non_owner.
    transcript = "Owner: take me off your list."
    assert wrong_dispo_detection(transcript, "DNC - Unknown") == "Yes"


def test_no_dnc_phrase_not_flagged():
    transcript = "Owner: can you call me back next week? I'm busy right now."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"


def test_ambiguous_objection_not_flagged():
    # "call me later" / "not interested right now" are not explicit DNC
    # requests -- precision over recall, see module docstring.
    transcript = "Owner: not interested right now, maybe call me later."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


def test_missing_transcript_not_flagged():
    assert wrong_dispo_detection("", "Wrong Number") == "No"
    assert wrong_dispo_detection(None, "Wrong Number") == "No"


def test_missing_disposition_not_flagged():
    assert wrong_dispo_detection("Owner: do not call me again.", "") == "No"
    assert wrong_dispo_detection("Owner: do not call me again.", None) == "No"


# ── Check 2: Wrong Number ────────────────────────────────────────────────────

def test_wrong_number_phrase_with_decision_maker_nyi_flags():
    transcript = "Caller: sorry, you have the wrong number."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_wrong_number_phrase_contraction_matches():
    transcript = "Caller: I'm not the owner, you've got the wrong person."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_wrong_number_phrase_with_wrong_number_disposition_not_flagged():
    transcript = "Caller: sorry, this is the wrong number."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"


def test_wrong_number_phrase_with_dnc_disposition_not_flagged():
    # DNC always wins over Wrong Number when both signals are present.
    transcript = "Caller: wrong number, and don't call me again."
    assert wrong_dispo_detection(transcript, "DNC - Decision Maker") == "No"


def test_wrong_address_alone_not_treated_as_wrong_number():
    # Deliberately excluded -- could be a mailing-address correction from
    # the same owner, not an identity denial.
    transcript = "Owner: that's the wrong address for mailing, use my PO box."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


def test_nyi_with_acceptance_phrase_not_flagged():
    # The NYI-vs-acceptance check was removed 2026-11-08 ("Interested" isn't a real disposition).
    transcript = "Owner: yes I'm interested, send me the offer."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


# ── Tier 2: semantic paraphrase matching ─────────────────────────────────────
# Fast, no real model: a tiny fake encoder maps "signal_dnc" / "signal_wn"
# markers to one-hot vectors, matched against one-hot phrase embeddings for
# the same two categories. Cosine similarity is then either ~1.0 (marker
# present) or ~0 (absent) -- deterministic, no network/model load.

class _FakeEncoder:
    _DIMS = {"dnc": 0, "wrong_number": 1}
    _MARKERS = {"signal_dnc": "dnc", "signal_wn": "wrong_number"}

    def encode(self, texts, **kwargs):
        import numpy as np
        vectors = []
        for text in texts:
            vec = [0.0, 0.0]
            lowered = text.lower()
            for marker, category in self._MARKERS.items():
                if marker in lowered:
                    vec[self._DIMS[category]] = 1.0
            if vec == [0.0, 0.0]:
                vec = [0.01, 0.01]  # near-zero on every axis, stays under threshold
            vectors.append(vec)
        return np.array(vectors)


def _fake_phrase_embeddings():
    import numpy as np
    return {
        "dnc": np.array([[1.0, 0.0]]),
        "wrong_number": np.array([[0.0, 1.0]]),
    }


def _enable_fake_semantic_tier(monkeypatch):
    monkeypatch.setattr(
        wrong_dispo_detector, "_get_semantic_resources",
        lambda: (_FakeEncoder(), _fake_phrase_embeddings()),
    )


def test_semantic_paraphrase_flags_when_tier_1_would_have_missed_it(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: honestly signal_dnc, please understand."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "Yes"


def test_semantic_dnc_still_wins_over_wrong_number(monkeypatch):
    # Both category markers present; DNC takes precedence, same as Tier 1.
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: signal_dnc signal_wn"
    assert wrong_dispo_detection(transcript, "DNC - Decision Maker") == "No"


def test_semantic_wrong_number_category_skipped_when_dispo_already_correct(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: not signal_wn"
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_semantic_wrong_number_needs_a_denial_word(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection("Owner: signal_wn", "Decision Maker - NYI") == "No"


@pytest.mark.parametrize("sentence", [
    "that is not signal_wn",
    "that's not signal_wn",
    "I don't signal_wn",
    "this isn't signal_wn",
    "you have the wrong signal_wn",
    "I no longer signal_wn",
])
def test_semantic_wrong_number_denial_words_count(monkeypatch, sentence):
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection(f"Owner: {sentence}", "Decision Maker - NYI") == "Yes"


def test_semantic_denial_word_in_another_sentence_does_not_count(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: signal_wn.\nAgent: Have you thought about selling?\nOwner: No, not for sale."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


def test_semantic_denial_word_rule_only_applies_to_wrong_number(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection("Owner: signal_dnc", "Decision Maker - NYI") == "Yes"


def test_semantic_irrelevant_transcript_not_flagged(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: nothing relevant here at all."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"


def test_semantic_resources_unavailable_falls_back_to_tier_1_only(monkeypatch):
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", lambda: (None, None))
    transcript = "Caller: do not call me again."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "Yes"


# ── Short reason labels ("WN instead of DNC") ────────────────────────────────

def test_reason_is_none_when_not_flagged():
    transcript = "Owner: can you call me back next week, I'm busy right now."
    assert wrong_dispo_reason(transcript, "Wrong Number") is None


def test_reason_dnc_check_shows_logged_disposition_instead_of_dnc():
    transcript = "Caller: please do not call me again, I'm not interested."
    assert wrong_dispo_reason(transcript, "Wrong Number") == "WN instead of DNC"


def test_reason_wrong_number_check_shows_logged_disposition_instead_of_wn():
    transcript = "Caller: sorry, you have the wrong number."
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of WN"


def test_reason_falls_back_to_raw_disposition_when_unrecognized():
    transcript = "Caller: do not call me again."
    assert wrong_dispo_reason(transcript, "Some Custom Dispo") == "Some Custom Dispo instead of DNC"


def test_reason_matches_detection_result_via_shared_detail_call():
    # wrong_dispo_detection() and wrong_dispo_reason() must never disagree --
    # they're both thin wrappers over wrong_dispo_detail().
    transcript = "Caller: do not call me again."
    result, reason = wrong_dispo_detail(transcript, "Wrong Number")
    assert result == wrong_dispo_detection(transcript, "Wrong Number")
    assert reason == wrong_dispo_reason(transcript, "Wrong Number")
    assert result == "Yes" and reason == "WN instead of DNC"


# ── Owner lines only ─────────────────────────────────────────────────────────

def test_phrase_said_by_agent_not_flagged():
    transcript = "Agent: Is this the wrong number?\nOwner: No, this is me. Not selling, thanks."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


def test_phrase_said_by_owner_flagged_in_labelled_transcript():
    transcript = "Agent: Is this Mrs. Lewis?\nOwner: You have the wrong number."
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of WN"


def test_phrase_cannot_match_across_two_owner_turns():
    transcript = "Owner: That is the wrong\nAgent: Sorry?\nOwner: number of times you called."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


def test_labelled_transcript_with_no_owner_lines_not_flagged():
    assert wrong_dispo_detection("Agent: do not call me again", "Wrong Number") == "No"


def test_semantic_tier_only_sees_owner_text_without_labels(monkeypatch):
    seen = []

    class RecordingEncoder(_FakeEncoder):
        def encode(self, texts, **kwargs):
            seen.extend(texts)
            return super().encode(texts, **kwargs)

    monkeypatch.setattr(
        wrong_dispo_detector, "_get_semantic_resources",
        lambda: (RecordingEncoder(), _fake_phrase_embeddings()),
    )
    transcript = "Agent: signal_dnc from the agent\nOwner: I am busy today"
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"
    assert seen and all("signal_dnc" not in t and "Owner" not in t for t in seen)


def test_semantic_tier_skipped_when_transcript_has_no_labels(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection("honestly signal_dnc, please understand.", "Wrong Number") == "No"


def test_real_model_agent_asking_about_property_not_flagged(monkeypatch):
    # Real false flag: "This is your property?" scored 0.888 against
    # "this is not my property" while the owner was keeping the property.
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", _REAL_GET_SEMANTIC_RESOURCES)
    model, _ = wrong_dispo_detector._get_semantic_resources()
    if model is None:
        pytest.skip("semantic model not available in this environment")
    transcript = (
        "Owner: Hello.\n"
        "Agent: I'm calling about the property at 382. This is your property?\n"
        "Owner: This is ye.\n"
        "Agent: I'm just asking if you think about selling the property at 382.\n"
        "Owner: No, we're not. It's a family property that's owned, and we're going to keep it in the family.\n"
        "Agent: That's fine. Have a good one.\n"
        "Owner: All right. Bye. Bye."
    )
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"


@pytest.mark.parametrize("owner_line", [
    "This is my house.",
    "I own a property? Yes.",
    "I own property. Yes, I do.",
])
def test_real_model_owner_confirming_ownership_not_flagged(monkeypatch, owner_line):
    # Real false flags: "This is my house" scored 0.900 against "this is not my
    # house", because the embedding barely registers the word "not".
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", _REAL_GET_SEMANTIC_RESOURCES)
    model, _ = wrong_dispo_detector._get_semantic_resources()
    if model is None:
        pytest.skip("semantic model not available in this environment")
    assert wrong_dispo_detection(f"Owner: {owner_line}", "Decision Maker - NYI") == "No"


@pytest.mark.parametrize("owner_text", [
    "Sorry, I got the wrong number.",
    "I think I put the wrong number.",
    "I must have dialed the wrong number.",
    "Sorry. I\nAgent: Gerald.\nOwner: got the wrong number.",
])
def test_speaker_saying_they_made_the_mistake_is_not_a_wrong_number(owner_text):
    assert wrong_dispo_detection(f"Owner: {owner_text}", "Decision Maker - NYI") == "No"


@pytest.mark.parametrize("owner_text", [
    "No, you got the wrong number.",
    "I think you got the wrong number.",
    "Wrong number.",
    "I got the wrong number. Actually you have the wrong number.",
])
def test_owner_telling_the_agent_it_is_a_wrong_number_still_flags(owner_text):
    assert wrong_dispo_reason(f"Owner: {owner_text}", "Decision Maker - NYI") == "NYI instead of WN"


def test_own_mistake_phrase_does_not_affect_the_dnc_check():
    transcript = "Owner: I got the wrong number. Stop calling me."
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of DNC"


@pytest.mark.parametrize("owner_text", [
    "I don't own the property on Trotter Drive. Take me off your call list and never call me again.",
    "I haven't owned it for years. Stop calling me.",
    "You have the wrong number. Stop calling me.",
    "That's not my house. Don't call me again.",
    "I'm not the owner. Remove my number.",
    "We don't own that. Stop calling me.",
    "I don't have any property. Stop calling me.",
])
def test_dnc_unknown_is_correct_for_a_non_owner(owner_text):
    assert wrong_dispo_detail(f"Owner: {owner_text}", "DNC - Unknown") == ("No", None)


@pytest.mark.parametrize("owner_text", [
    "Stop calling me.",
    "Yes, that's my house. Don't call me again.",
    "I got the wrong number. Stop calling me.",
])
def test_dnc_unknown_still_flags_without_a_denial(owner_text):
    assert wrong_dispo_reason(f"Owner: {owner_text}", "DNC - Unknown") == "DNC-Unk instead of DNC"


def test_dnc_unknown_ignores_a_denial_said_by_the_agent():
    transcript = "Agent: So you don't own the property? I don't own it either.\nOwner: Stop calling me."
    assert wrong_dispo_reason(transcript, "DNC - Unknown") == "DNC-Unk instead of DNC"


def test_non_owner_who_asked_not_to_be_called_still_flags_on_other_dispositions():
    transcript = "Owner: I don't own the property. Never call me again."
    assert wrong_dispo_reason(transcript, "Wrong Number") == "WN instead of DNC"
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of DNC"


def test_semantic_wrong_number_ignores_talk_of_other_property(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection("Owner: I don't have any other signal_wn", "Decision Maker - NYI") == "No"
    assert wrong_dispo_detection("Owner: I don't own another signal_wn", "Decision Maker - NYI") == "No"


def test_semantic_wrong_number_ignores_own_mistake(monkeypatch):
    # With the phrase left in, "wrong" would count as the sentence's denial word.
    _enable_fake_semantic_tier(monkeypatch)
    assert wrong_dispo_detection("Owner: I got the wrong number signal_wn", "Decision Maker - NYI") == "No"


def test_real_model_owner_with_no_other_property_not_flagged(monkeypatch):
    # Real false flag: an owner who had just confirmed owning the house.
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", _REAL_GET_SEMANTIC_RESOURCES)
    model, _ = wrong_dispo_detector._get_semantic_resources()
    if model is None:
        pytest.skip("semantic model not available in this environment")
    transcript = (
        "Agent: I believe you own a property on 161.\nOwner: Yeah.\n"
        "Agent: Would you consider selling?\nOwner: No, I'm not. I don't plan on selling it. And\n"
        "Agent: Oh,\nOwner: I don't have any other property."
    )
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "No"
