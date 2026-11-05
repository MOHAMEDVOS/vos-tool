"""
Pure Wrong Dispo flagger for the heavy-audit pipeline.
No I/O, no dependencies beyond stdlib. Runs on the already-transcribed call,
same spirit as ``lib/campaign_audit_detector.py``.

Flags a disposition mismatch between what the transcript actually shows and
what the agent logged. Three checks, each narrow and literal on purpose -- a
false positive here falsely accuses an agent of mis-logging a call, so
precision beats recall throughout. Widen the phrase lists as real misses
turn up, same as the original DNC check.

1. DNC: the homeowner clearly asked not to be contacted again, but the
   disposition isn't "DNC - Decision Maker".
2. Wrong Number: the person on the call clearly denied being the
   owner/right number, but the disposition is neither "Wrong Number" nor
   "DNC - Decision Maker" (DNC always wins over Wrong Number when both
   signals are present -- see docs/superpowers/plans/
   2026-11-05-wrong-dispo-wider-coverage.md).
3. Decision Maker - NYI: the disposition is specifically "Decision Maker -
   NYI", but the transcript has a clear acceptance/commitment phrase that
   contradicts "not yet interested".

Each of those is Tier 1: an exact (normalized) phrase match. Tier 2, added
2026-11-05, only runs for a category Tier 1 found nothing in -- it embeds the
transcript's sentences and the category's phrase list with the same
sentence-transformers model rebuttal detection already loads, and flags a
paraphrase that clears a conservative similarity threshold. See
docs/superpowers/plans/2026-11-05-wrong-dispo-semantic-layer.md. Tier 2
degrades silently (falls back to Tier 1 only) if the model isn't available --
same "silent miss over false positive" rule as everywhere else in this file.
"""

from __future__ import annotations

import logging
import os
import re
import threading

# Explicit, unambiguous "don't contact me again" statements only. Kept
# narrow on purpose -- see module docstring. Matched after _normalize() so
# apostrophes/dashes/case/spacing don't matter.
#
# _normalize() strips apostrophes (doesn't insert a space), so a spoken
# contraction normalizes differently from its spelled-out form -- "don't"
# becomes "dont" (one word), not "do not" (two words). Both spellings are
# realistic transcript output, so contraction-bearing phrases are listed
# twice on purpose; this is not duplication to clean up.
DNC_PHRASES = [
    "do not call me again", "dont call me again",
    "do not call again", "dont call again",
    "do not call this number again", "dont call this number again",
    "do not call me anymore", "dont call me anymore",
    "do not call anymore", "dont call anymore",
    "never call me again",
    "never call this number again",
    "stop calling me",
    "stop calling this number",
    "quit calling me",
    "quit calling this number",
    "do not contact me again", "dont contact me again",
    "stop contacting me",
    "i do not want to be contacted", "i dont want to be contacted",
    "i do not want to be contacted again", "i dont want to be contacted again",
    "i do not want to be called again", "i dont want to be called again",
    "take me off your list",
    "take me off the list",
    "remove me from your list",
    "remove my number",
    "remove this number",
    "lose my number",
    "put me on the do not call list", "put me on the dont call list",
    "put this number on the do not call list", "put this number on the dont call list",
]

# Literal identity/ownership denial only -- NOT things like "wrong address"
# (could just be a mailing-address correction from the same owner, not a
# denial of who they are). Listed post-_normalize() (apostrophes stripped,
# so "I'm" -> "im", "you've" -> "youve"), with both contracted and spelled
# forms for the same reason DNC_PHRASES lists both.
WRONG_NUMBER_PHRASES = [
    "wrong number",
    "wrong person",
    "you have the wrong number", "youve got the wrong number",
    "you have the wrong person", "youve got the wrong person",
    "this is the wrong number",
    "not my number",
    "not my property", "not my house",
    "this is not my property", "this isnt my property",
    "this is not my house", "this isnt my house",
    "i do not own this property", "i dont own this property",
    "i do not own this house", "i dont own this house",
    "i do not own this", "i dont own this",
    "i am not the owner", "im not the owner",
]

# Literal, unambiguous acceptance/commitment phrases that contradict
# "not yet interested". Listed post-_normalize() same as above.
NYI_CONTRADICTION_PHRASES = [
    "yes im interested", "yes i am interested",
    "i want to sell",
    "im ready to sell", "i am ready to sell",
    "im interested in selling", "i am interested in selling",
    "lets move forward",
    "lets do it",
    "i agree to sell",
    "i accept the offer",
    "send me the offer", "send me the contract",
    "when can we close", "when can we sign",
]

# Hyphen plus the unicode dash variants seen in this codebase's own disposition
# strings (e.g. "Decision Maker - NYI" in backend/api/scoring.py vs
# "Decision Maker – NYI" in lib/dashboard_manager.py).
_DASH_RE = re.compile(r"[‐-―\-]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """lowercase, drop apostrophes, collapse dash variants to '-', squash whitespace."""
    text = (text or "").lower()
    text = text.replace("’", "").replace("'", "")
    text = _DASH_RE.sub("-", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _is_dnc_decision_maker(disposition: str) -> bool:
    """True only for a disposition that normalizes to "dnc - decision maker".

    Prefix/contains matching (not an exact-string compare) so it survives the
    dash inconsistency above. "DNC - Unknown" is deliberately NOT treated as
    correct here -- see the plan doc's "Assumption to flag" note.
    """
    norm = _normalize(disposition)
    return norm.startswith("dnc") and "decision maker" in norm


def _is_wrong_number(disposition: str) -> bool:
    """True only for a disposition that normalizes to "wrong number"."""
    return _normalize(disposition) == "wrong number"


def _is_decision_maker_nyi(disposition: str) -> bool:
    """True for a disposition that normalizes to "decision maker - nyi"
    (contains-based, not exact, same dash-tolerant style as
    _is_dnc_decision_maker -- survives "Decision Maker - NYI" vs
    "Decision Maker – NYI")."""
    norm = _normalize(disposition)
    return "decision maker" in norm and "nyi" in norm


# ── Tier 2: semantic paraphrase matching ────────────────────────────────────
# Catches a paraphrase of a Tier-1 phrase ("I'd rather you guys didn't reach
# out again") that isn't a literal substring match. See the module docstring
# and docs/superpowers/plans/2026-11-05-wrong-dispo-semantic-layer.md.

logger = logging.getLogger(__name__)

_PHRASE_LISTS = {
    "dnc": DNC_PHRASES,
    "wrong_number": WRONG_NUMBER_PHRASES,
    "nyi": NYI_CONTRADICTION_PHRASES,
}

_SEMANTIC_ENABLED = os.getenv("WRONG_DISPO_SEMANTIC_ENABLED", "true").lower() == "true"

# Stricter than rebuttal detection's 0.68 -- a bad semantic match here IS the
# false positive this flag exists to avoid, so Tier 2 would rather miss a
# paraphrase than invent one. Clamped same way rebuttal's threshold is.
_SEMANTIC_THRESHOLD = max(0.65, min(
    float(os.getenv("WRONG_DISPO_SEMANTIC_THRESHOLD", "0.80")), 0.95
))

_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")

_semantic_model = None
_phrase_embeddings = None
_semantic_lock = threading.Lock()


def _split_into_sentences(text: str) -> list[str]:
    """Stdlib sentence splitter. Simplified version of the rebuttal
    detector's -- Wrong Dispo doesn't need its question-chunking, just short
    text segments to embed."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if len(s.strip()) >= 3]


def _get_semantic_resources():
    """Lazy singleton: (model, {category: phrase_embeddings}), or (None, None)
    if the semantic tier is disabled or the model isn't available. Reuses the
    same sentence-transformers singleton rebuttal detection loads
    (models/manager.py) -- never loads a second copy of the model -- but
    builds its own phrase embeddings from this file's own phrase lists.
    Never raises: a missing/slow model just means Tier 2 is skipped and
    Tier 1's result stands.
    """
    global _semantic_model, _phrase_embeddings

    if not _SEMANTIC_ENABLED:
        return None, None
    if _semantic_model is not None and _phrase_embeddings is not None:
        return _semantic_model, _phrase_embeddings

    with _semantic_lock:
        if _semantic_model is not None and _phrase_embeddings is not None:
            return _semantic_model, _phrase_embeddings
        try:
            from models.manager import get_semantic_model
            model, _rebuttal_embeddings = get_semantic_model()
            if model is None:
                return None, None
            embeddings = {
                category: model.encode(phrases, show_progress_bar=False)
                for category, phrases in _PHRASE_LISTS.items()
            }
            _semantic_model = model
            _phrase_embeddings = embeddings
        except Exception as e:
            logger.warning(f"Wrong Dispo semantic tier unavailable: {e}")
            return None, None

    return _semantic_model, _phrase_embeddings


def _semantic_category_match(transcript: str, category: str, model, phrase_embeddings: dict) -> bool:
    """True if any sentence in the transcript is a close paraphrase of a
    phrase in `category`. `model`/`phrase_embeddings` are passed explicitly
    (not looked up internally) so tests can inject a fake encoder instead of
    loading the real model."""
    sentences = _split_into_sentences(transcript)
    if not sentences:
        return False

    category_embeddings = phrase_embeddings.get(category)
    if category_embeddings is None or len(category_embeddings) == 0:
        return False

    from sklearn.metrics.pairwise import cosine_similarity

    sentence_embeddings = model.encode(sentences, show_progress_bar=False)
    similarities = cosine_similarity(sentence_embeddings, category_embeddings)
    return bool(similarities.size) and float(similarities.max()) >= _SEMANTIC_THRESHOLD


# ── Short reason labels, for the UI ("WN instead of DNC") ──────────────────
# Added 2026-11-05 so the flagged-calls list can show which check fired and
# what was actually logged, not just "Wrong Dispo". Purely cosmetic -- never
# changes whether something flags, only how the flag is described.

_CHECK_TARGET_LABEL = {
    "dnc": "DNC",
    "wrong_number": "WN",
    # Check 3 doesn't have one "correct" disposition to point to (unlike DNC/
    # WN) -- it only knows the transcript contradicts "not yet interested".
    "nyi": "Interested",
}

# Common dispositions -> short label. Anything not listed here falls back to
# the raw disposition text as typed (see _abbreviate_disposition) rather than
# guessing an abbreviation for a value we don't recognize.
_DISPOSITION_ABBREVIATIONS = {
    "dnc-decision maker": "DNC",
    "dnc-unknown": "DNC-Unk",
    "wrong number": "WN",
    "decision maker-nyi": "NYI",
    "decision maker-lead": "Lead",
    "decision maker": "DM",
    "unknown": "Unk",
    "influencer": "Infl",
    "voicemail": "VM",
    "prank voicemail": "Prank VM",
    "agent": "Agent",
    "callback": "CB",
    "spanish speaker": "Spanish",
    "dead call": "Dead",
    "listed property": "Listed",
    "sold": "Sold",
}


def _abbreviate_disposition(disposition: str) -> str:
    """Short label for whatever the agent actually logged. _normalize()
    collapses dash variants to a plain "-", so the lookup key below strips
    spaces around it too (e.g. "DNC - Decision Maker" -> "dnc-decision
    maker"). Falls back to the disposition as typed if it's not a
    disposition we recognize -- better an unabbreviated label than a wrong
    guess."""
    norm = _normalize(disposition).replace(" - ", "-").replace("- ", "-").replace(" -", "-")
    return _DISPOSITION_ABBREVIATIONS.get(norm, disposition.strip() or "Unknown")


def wrong_dispo_detail(transcript: str, disposition: str) -> tuple[str, str | None]:
    """(("Yes"|"No"), reason). reason is a short "<logged> instead of
    <category>" string (e.g. "WN instead of DNC") when flagged, else None.
    Single source of truth for both wrong_dispo_detection() and
    wrong_dispo_reason() below, and the only place that should be called
    when you need both -- calling them separately runs every check (and the
    semantic model) twice for the same transcript.

    See the module docstring for the checks this runs (Tier 1: exact phrase
    match; Tier 2: semantic paraphrase match, only for a category Tier 1
    found nothing in)."""
    if not transcript or not disposition:
        return "No", None

    norm_transcript = _normalize(transcript)
    logged_label = _abbreviate_disposition(disposition)

    # Each "_applicable" flag mirrors the disposition guard Tier 1 already
    # uses for that category -- Tier 2 only gets a turn where Tier 1 could
    # have fired too.
    dnc_applicable = not _is_dnc_decision_maker(disposition)
    wrong_number_applicable = not _is_wrong_number(disposition) and not _is_dnc_decision_maker(disposition)
    nyi_applicable = _is_decision_maker_nyi(disposition)

    def _reason(category: str) -> str:
        return f"{logged_label} instead of {_CHECK_TARGET_LABEL[category]}"

    # Check 1: DNC phrase present, disposition isn't "DNC - Decision Maker".
    if dnc_applicable:
        for phrase in DNC_PHRASES:
            if phrase in norm_transcript:
                return "Yes", _reason("dnc")

    # Check 2: Wrong Number phrase present, disposition is neither
    # "Wrong Number" nor "DNC - Decision Maker" (DNC wins over Wrong Number
    # when both signals are present).
    if wrong_number_applicable:
        for phrase in WRONG_NUMBER_PHRASES:
            if phrase in norm_transcript:
                return "Yes", _reason("wrong_number")

    # Check 3: disposition is specifically "Decision Maker - NYI" but the
    # transcript has a clear acceptance phrase contradicting "not yet
    # interested".
    if nyi_applicable:
        for phrase in NYI_CONTRADICTION_PHRASES:
            if phrase in norm_transcript:
                return "Yes", _reason("nyi")

    # Tier 2: paraphrase of a Check 1/2/3 phrase, for whichever category
    # Tier 1 didn't already rule out or already search literally.
    model, phrase_embeddings = _get_semantic_resources()
    if model is not None and phrase_embeddings is not None:
        if dnc_applicable and _semantic_category_match(transcript, "dnc", model, phrase_embeddings):
            return "Yes", _reason("dnc")
        if wrong_number_applicable and _semantic_category_match(transcript, "wrong_number", model, phrase_embeddings):
            return "Yes", _reason("wrong_number")
        if nyi_applicable and _semantic_category_match(transcript, "nyi", model, phrase_embeddings):
            return "Yes", _reason("nyi")

    return "No", None


def wrong_dispo_detection(transcript: str, disposition: str) -> str:
    """"Yes" when the transcript clearly contradicts the logged disposition;
    "No" otherwise (including when either input is missing -- a silent
    miss, not a false accusation). See wrong_dispo_detail() for the checks
    this runs; call that directly instead if you also need the reason, to
    avoid running the checks twice."""
    return wrong_dispo_detail(transcript, disposition)[0]


def wrong_dispo_reason(transcript: str, disposition: str) -> str | None:
    """Short reason like "WN instead of DNC" when wrong_dispo_detection()
    would return "Yes"; None otherwise. See wrong_dispo_detail() for the
    checks this runs; call that directly instead if you also need the Yes/No
    result, to avoid running the checks twice."""
    return wrong_dispo_detail(transcript, disposition)[1]
