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


def test_dnc_unknown_is_not_treated_as_correct():
    # Per spec: only "DNC - Decision Maker" counts as correct. "DNC - Unknown"
    # still gets flagged when a clear DNC phrase is present.
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


# ── Check 3: Decision Maker - NYI used as a dumping ground ──────────────────

def test_nyi_contradiction_phrase_with_nyi_disposition_flags():
    transcript = "Owner: yes I'm interested, send me the offer."
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_nyi_contradiction_phrase_dash_variant_flags():
    transcript = "Owner: I want to sell, when can we close?"
    assert wrong_dispo_detection(transcript, "Decision Maker – NYI") == "Yes"


def test_nyi_contradiction_phrase_only_fires_for_nyi_disposition():
    # Same contradicting phrase, but the disposition isn't NYI -- check 3
    # is scoped specifically to "Decision Maker - NYI", not any disposition.
    transcript = "Owner: yes I'm interested, send me the offer."
    assert wrong_dispo_detection(transcript, "Decision Maker") == "No"
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"


# ── Tier 2: semantic paraphrase matching ─────────────────────────────────────
# Fast, no real model: a tiny fake encoder maps "signal_dnc" / "signal_wn" /
# "signal_nyi" markers to one-hot vectors, matched against one-hot phrase
# embeddings for the same three categories. Cosine similarity is then either
# ~1.0 (marker present) or ~0 (absent) -- deterministic, no network/model load.

class _FakeEncoder:
    _DIMS = {"dnc": 0, "wrong_number": 1, "nyi": 2}
    _MARKERS = {"signal_dnc": "dnc", "signal_wn": "wrong_number", "signal_nyi": "nyi"}

    def encode(self, texts, **kwargs):
        import numpy as np
        vectors = []
        for text in texts:
            vec = [0.0, 0.0, 0.0]
            lowered = text.lower()
            for marker, category in self._MARKERS.items():
                if marker in lowered:
                    vec[self._DIMS[category]] = 1.0
            if vec == [0.0, 0.0, 0.0]:
                vec = [0.01, 0.01, 0.01]  # near-zero on every axis, stays under threshold
            vectors.append(vec)
        return np.array(vectors)


def _fake_phrase_embeddings():
    import numpy as np
    return {
        "dnc": np.array([[1.0, 0.0, 0.0]]),
        "wrong_number": np.array([[0.0, 1.0, 0.0]]),
        "nyi": np.array([[0.0, 0.0, 1.0]]),
    }


def _enable_fake_semantic_tier(monkeypatch):
    monkeypatch.setattr(
        wrong_dispo_detector, "_get_semantic_resources",
        lambda: (_FakeEncoder(), _fake_phrase_embeddings()),
    )


def test_semantic_paraphrase_flags_when_tier_1_would_have_missed_it(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Caller: honestly signal_dnc, please understand."
    assert wrong_dispo_detection(transcript, "Wrong Number") == "Yes"


def test_semantic_dnc_still_wins_over_wrong_number(monkeypatch):
    # Both category markers present; DNC takes precedence, same as Tier 1.
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Caller: signal_dnc signal_wn"
    assert wrong_dispo_detection(transcript, "DNC - Decision Maker") == "No"


def test_semantic_wrong_number_category_skipped_when_dispo_already_correct(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Caller: signal_wn"
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"


def test_semantic_nyi_only_applies_to_nyi_disposition(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: signal_nyi"
    assert wrong_dispo_detection(transcript, "Decision Maker - NYI") == "Yes"
    assert wrong_dispo_detection(transcript, "Wrong Number") == "No"


def test_semantic_irrelevant_transcript_not_flagged(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Caller: nothing relevant here at all."
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


def test_reason_nyi_check_has_no_single_correct_disposition_to_name():
    # Check 3 only knows NYI is contradicted, not what it should be instead --
    # see _CHECK_TARGET_LABEL's comment.
    transcript = "Owner: yes I'm interested, send me the offer."
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of Interested"


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


def test_semantic_reason_reported_for_tier_2_matches(monkeypatch):
    _enable_fake_semantic_tier(monkeypatch)
    transcript = "Owner: signal_nyi"
    assert wrong_dispo_reason(transcript, "Decision Maker - NYI") == "NYI instead of Interested"


def test_semantic_real_model_loads_and_scores_sanely(monkeypatch):
    # Integration smoke test against the real sentence-transformers model --
    # NOT a pass/fail paraphrase check. Measured similarity scores for real
    # DNC/Wrong Number/NYI paraphrases against this model land mostly in the
    # 0.48-0.80 range (see chat / plan doc "threshold finding" note), with no
    # clean gap from some false-signal sentences -- so this only confirms the
    # pipeline runs end to end, not that any fixed threshold is safe yet.
    # Skips cleanly if the model can't load in this environment.
    monkeypatch.setattr(wrong_dispo_detector, "_get_semantic_resources", _REAL_GET_SEMANTIC_RESOURCES)
    model, embeddings = wrong_dispo_detector._get_semantic_resources()
    if model is None:
        pytest.skip("semantic model not available in this environment")
    assert wrong_dispo_detector._semantic_category_match(
        "Caller: can you take my number off whatever list this is.", "dnc", model, embeddings,
    ) in (True, False)  # runs without error; see note above on threshold reliability
