"""Second opinion on a "No Rebuttal" verdict, before it becomes a flag.

The phrase/regex/semantic matchers in rebuttal_detection.py answer "does the
agent's text match a known rebuttal phrase?". That question has two structural
blind spots this module targets:

  1. It never asks whether the owner objected in the first place. A call
     where nothing needed rebutting (wrong number, friendly answer, no pitch
     reached) gets the same "No" as a call where the agent genuinely gave up.
  2. It only catches rebuttals that match the phrase library. Indirect
     pushes ("do you have another one?"), interrupted attempts cut off by a
     hangup ("Not even..."), and ASR-mangled phrasing ("No profit easy be
     open to sellling at all" = "are you open to selling at all") all score
     zero even though the agent tried.

Both were measured against 198 real "No Rebuttal" calls, hand-labelled by
independent judges: 55% of wrong flags had no objection at all, 31% were
attempts the phrase matchers missed. See docs/REBUTTAL_FALSE_FLAGS.md for the
full analysis and docs/REBUTTAL_FALSE_FLAGS.md's measured numbers for this
exact rule set (16.7% wrong-flag rate on labelled calls with usable speaker
turns, recovering 30 of 39 correctly-flagged calls' worth of headroom while
losing none of them).

This module only ever runs on a verdict the matchers already called "No" --
it never overrides a "Yes", and it never invents a matched phrase.

2026-11-05: shipped 2026-09-02, then disabled 2026-11-03 (commit 1de3ac7)
because it was too generous -- it cleared calls where the agent genuinely
skipped a rebuttal. Mohamed identified two concrete gaps while reviewing:

1. "Wrong Number" was never treated as an objection needing a rebuttal at
   all, so `_owner_objection()` returned nothing and every wrong-number call
   got `no_objection` regardless of what the agent did next. Per Mohamed:
   the correct move on a wrong-number call is still to ask whether the
   person has (or knows of) any property for sale -- that's the rebuttal.
   Skipping it is still a miss. See `_WRONG_NUMBER_DENIAL`/`_WRONG_NUMBER_PIVOT`.
2. `unusable` (no parseable speaker turns) was computed but never excluded
   from the flagging query in the original wiring -- it only excluded
   `no_objection`. A blank transcript was still flagged as if the agent
   failed, even though there's no data to judge them on.

   First attempt at this fix excluded ALL unparseable transcripts, not just
   empty ones -- measured against the 198 labelled calls, that dropped fair
   flags kept from 41/52 to 29/52, because several non-empty transcripts
   with no "Agent:"/"Owner:" structure (flat text, or "Channel 1:"/
   "Channel 2:" from the diarization bug in docs/REBUTTAL_FALSE_FLAGS.md)
   were genuinely-fair flags a human could still read and confirm. Fixed:
   `unusable` is now ONLY a truly empty transcript; a non-empty one that
   just can't be parsed is `unparseable` and stays flagged by default (same
   as before this module existed) since there's no way to verify it's
   unfair.

Also added: `owner_ended_call` -- the owner objects and closes the call
("...not selling my house. Thank you. Goodbye.") with no further agent turn
at all. Narrow and literal on purpose (an explicit closing word, not just
"no agent reply"), same precision-first reasoning as everywhere else here --
the risk of making this verdict too generous is exactly the bug that got the
gate disabled the first time.

2026-11-05, later: the wrong-number denial list was too literal, so "I don't
own a house." and "Wrong phone number." came back `no_objection` and cleared
real misses. A phrase list can't cover every denial, so `evaluate()` now takes
the logged disposition. A Wrong Number call can only clear with an explicit
owner close, and only a real pivot counts as an attempt.
"""
from __future__ import annotations

import re
from typing import Optional, TypedDict


class ObjectionGateResult(TypedDict):
    verdict: str          # "no_objection" | "attempted" | "no_attempt" | "unusable"
                           # | "owner_ended_call" | "unparseable"
    objection_quote: Optional[str]
    reason: str


# --- turn parsing -----------------------------------------------------------
# Dialogue is "Agent: ...\nOwner: ..." (lib/assemblyai_transcription.py:553).
_TURN_RE = re.compile(r"^[ \t]*(Agent|Owner)[ \t]*:[ \t]*(.*)$", re.IGNORECASE | re.MULTILINE)


def _parse_turns(dialogue: str) -> list[tuple[str, str]]:
    if not dialogue:
        return []
    turns = []
    for m in _TURN_RE.finditer(dialogue):
        speaker = m.group(1).capitalize()
        text = m.group(2).strip()
        if text:
            turns.append((speaker, text))
    return turns


# --- objection cues, owner side ---------------------------------------------
_OBJECTION_STRONG = re.compile(
    r"\bnot\s+interest|\bno\s+interest|\bnot\s+for\s+sale\b|\bnot\s+sell"
    r"|\bdon'?t\s+want\s+to\s+sell|\bnot\s+planning\b|\bno\s+plans?\b"
    r"|\bnever\b|\babsolutely\s+not\b|\bnot\s+available\b"
    r"|\btake\s+(?:me|my\s+\w+|us)\s+(?:off|out)\b|\bremove\s+(?:me|my)\b"
    r"|\bsolicitation\b|\bstop\s+calling\b|\bdo\s+not\s+call\b|\bdon'?t\s+call\b"
    r"|\bleave\s+me\s+alone\b|\bharass|\bsue\b|\blawyer\b"
    r"|\bnot\s+getting\s+it\b|\btold\s+\w+\s+no\b"
    r"|\bcalled?\s+me\s+\w+\s+times\b|\bcalls?\s+a\s+day\b|\bridiculous\b"
    r"|\bemergency\s+line\b|\bcall\s+every\s+day\b|\bget\s+me\s+off\b"
    r"|\bbreaking\s+the\s+law\b|\bdon'?t\s+call\s+(?:me|her|here|anymore)\b"
    r"|\bwon'?t\s+sell\b"
    r"|\bfuck|\bshit\b|\bgoddamn\b|\bpiss(?:ed|ing)?\s+off\b|\bidiot\b"
    r"|\bi\s+rent\b|\brenting\b|\bi'?m\s+a\s+tenant\b",
    re.IGNORECASE,
)
_OBJECTION_SOFT = re.compile(
    r"\bno\b[\s,.!]+thanks?\b|\bno\b[\s,.!]+thank\s+you\b|\bnope\b|\bnah\b"
    r"|\bno\b[\s,.!]+i'?m\s+not\b|\bno\b[\s,.!]+i\s+don'?t\b"
    r"|\bno\b[\s,.!]+it'?s\s+not\b|\bno\b[\s,.!]+it\s+is\s?n'?t\b"
    r"|\bno\b[\s,.!]+no\b[\s,.!]+no\b|\bnot\s+yet\b|\bnot\s+right\s+now\b"
    r"|\bi'?m\s+busy\b|\bdon'?t\s+have\s+time\b|\bnot\s+available\b",
    re.IGNORECASE,
)
# A bare "no"/"nope"/"not" is only meaningful when it directly answers a
# pitch question -- the same token answering "are you the owner?" means
# nothing. The regex-detection layer's bare \bno\b (rebuttal_detection.py:2384)
# fires on almost every call precisely because it ignores this distinction.
_PITCH_KEYWORD = re.compile(r"sell|interest|consider|offer\b", re.IGNORECASE)
_BARE_DECLINE = re.compile(r"^\s*(?:no+|nope|not\b)", re.IGNORECASE)
# Naming a price, or asking for one, is engagement -- not a refusal -- even if
# a stray "no" appears elsewhere (rejecting a lowball offer isn't refusing to
# sell). A reschedule reads negative on the surface but is a soft lead too.
_POSITIVE_ENGAGEMENT = re.compile(
    r"\$\s?\d|\b\d{2,3}[,.]?\d{3}\b|\bhow\s+much\b|\bwhat.{0,15}offer(?:ing)?\b"
    r"|\bemail\s+me\b|\bbring\s+me\b|\bbottom\s+line\b|\bwe'?ll\s+talk\b"
    r"|\bcall\s+(?:me\s+)?back\s+in\b|\bcheck\s+back\b",
    re.IGNORECASE,
)

# "Wrong number" is its own objection type -- the correct agent response is a
# pivot ("do you know anyone with property to sell?"), not a free pass. Kept
# narrow and literal, mirroring lib/wrong_dispo_detector.py's
# WRONG_NUMBER_PHRASES (not imported directly -- that list is normalized-text
# substring matching, this is raw-text regex, same literal phrases either way).
_WRONG_NUMBER_DENIAL = re.compile(
    r"\bwrong\s+number\b|\bwrong\s+person\b"
    r"|\byou\s+have\s+the\s+wrong\s+(?:number|person)\b"
    r"|\byou'?ve\s+got\s+the\s+wrong\s+(?:number|person)\b"
    r"|\bnot\s+my\s+number\b"
    r"|\bnot\s+my\s+(?:property|house)\b|\bthis\s+is\s+not\s+my\s+(?:property|house)\b"
    r"|\bi\s+do\s*n'?t\s+own\s+(?:this|that|it)\b"
    r"|\bi'?m\s+not\s+the\s+owner\b",
    re.IGNORECASE,
)

# Explicit call-ending language only -- narrow on purpose. Used to tell "owner
# objected and hung up" from "owner objected and the agent just didn't
# respond" when no agent turn follows the objection at all.
_CLOSING_PHRASE = re.compile(
    r"\bgoodbye\b|\bgood\s*bye\b|\bbye\b|\bhave\s+a\s+good\s+(?:day|one|night)\b"
    r"|\bgotta\s+go\b|\bi'?m\s+hanging\s+up\b|\bi'?m\s+gonna\s+go\b",
    re.IGNORECASE,
)

# --- agent-side rebuttal-attempt cues ----------------------------------------
# Agent language that means "I agree with you / I'm backing off" -- a turn
# containing one of these is a surrender even mid-sentence, and must not
# count as an attempt just because it repeats a sales keyword from the
# owner's own objection ("I'm not interested" said BY THE AGENT is agreement,
# not a pitch).
_AGENT_SURRENDER_PATTERN = (
    r"\bi'?m\s+not\s+interest\w*\b|\byou'?re\s+right\b|\bi\s+understand\b"
    r"|\bno\s+worries\b|\bmy\s+apologies\b|\bmy\s+bad\b"
)
_AGENT_SURRENDER = re.compile(_AGENT_SURRENDER_PATTERN, re.IGNORECASE)
_REBUTTAL_OPENERS = re.compile(
    r"\bnot\s+even\b|\bhow\s+about\b|\bwhat\s+about\b"
    r"|\bwould\s+you\s+(?:be\s+)?(?:open|consider|interest)|\bare\s+you\s+open\b"
    r"|\bdo\s+you\s+have\s+(?:any\s+)?(?:other|another)\b"
    r"|\bi'?m\s+(?:just\s+)?asking\b|\bi\s+was\s+asking\b"
    r"|\bmaybe\s+(?:in|sometime|later|next)\b|\bdown\s+the\s+road\b"
    r"|\banytime\s+soon\b|\bin\s+the\s+(?:near\s+)?future\b"
    r"|\bbottom\s+line\b|\bare\s+you\s+(?:still\s+)?the\s+owner\b"
    r"|\bthinking\s+about\s+sell|\bopen\s+to\s+sell|\bconsider\s+sell"
    r"|\bby\s+the\s+end\s+of\s+the\s+year\b|\bcall\s+you\s+back\b"
    r"|\bany\s+other\s+one\b|\banother\s+one\b|\bmaybe\s+later\b"
    r"|\bthis\s+year\b|\bnext\s+year\b|\bend\s+of\s+(?:the\s+)?year\b"
    r"|\bthe\s+owner\??\s*$",
    re.IGNORECASE,
)
# The expected pivot after a wrong-number denial, per Mohamed: still ask
# whether they (or anyone they know) has property to sell.
_WRONG_NUMBER_PIVOT = re.compile(
    r"\bdo\s+you\s+(?:happen\s+to\s+)?know\s+(?:if\s+)?(?:the\s+owner|anyone|anybody)\b"
    r"|\byou\s+(?:happen\s+to\s+)?(?:have|own)\s+(?:any|another|other)\s+(?:other\s+)?"
    r"(?:propert\w*|houses?|homes?|one)\b"
    r"|\bany\s+propert\w*\s+(?:for\s+sale|you'?re\s+looking\s+to\s+sell|to\s+sell)\b"
    r"|\blooking\s+to\s+sell\w*\s+any\w*\s+propert\w*\b"
    r"|\bdo\s+you\s+know\s+(?:the\s+)?owner'?s?\s+(?:number|contact)\b"
    r"|\b(?:nothing|anything)\b.*\bsell"
    # The question was started and the recording cut off.
    r"|\b(?:do|would)\s+you\s+have\W*$",
    re.IGNORECASE,
)
# The agent had already given up, so an owner's "bye" after this isn't the owner
# ending the call on them.
_AGENT_WRAPPED_UP = re.compile(
    _AGENT_SURRENDER_PATTERN + r"|\bsorry\b|\bthank|" + _CLOSING_PHRASE.pattern,
    re.IGNORECASE,
)
_CLOSING_WORDS = {
    "oh", "ok", "okay", "yes", "yeah", "yep", "yup", "sure", "sir", "maam", "ma", "am", "mam",
    "thank", "thanks", "you", "your", "bye", "goodbye", "have", "a", "an", "the", "good",
    "great", "day", "night", "evening", "morning", "of", "course", "sorry", "apologies",
    "i", "im", "m", "my", "me", "we", "no", "not", "nope", "alright", "all", "right",
    "appreciate", "it", "understand", "understood", "problem", "worries", "care", "take",
    "hello", "hi", "hey", "well", "uh", "um", "mhm",
    "and", "so", "for", "but", "just", "really", "very", "that", "this", "then", "there",
}


def _owner_objection(turns: list[tuple[str, str]]) -> tuple[bool, Optional[str], int]:
    """(objection_found, quote, turn_index). turn_index is None if not found."""
    for i, (speaker, text) in enumerate(turns):
        if speaker != "Owner":
            continue
        strong = _OBJECTION_STRONG.search(text)
        soft = _OBJECTION_SOFT.search(text)
        wrong_number = _WRONG_NUMBER_DENIAL.search(text)
        bare = bool(
            _BARE_DECLINE.match(text.strip())
            and len(text.split()) <= 6
            and i > 0
            and turns[i - 1][0] == "Agent"
            and _PITCH_KEYWORD.search(turns[i - 1][1])
        )
        if (strong or soft or wrong_number or bare) and not _POSITIVE_ENGAGEMENT.search(text):
            return True, text.strip(), i
    return False, None, -1


def _agent_attempted(turns: list[tuple[str, str]], objection_idx: int) -> bool:
    """Does the agent's post-objection text carry real content, not just closers?"""
    after = [t for s, t in turns[objection_idx + 1:] if s == "Agent"]
    after = [t for t in after if not _AGENT_SURRENDER.search(t)]
    if not after:
        return False
    if any(_REBUTTAL_OPENERS.search(t) or _WRONG_NUMBER_PIVOT.search(t) for t in after):
        return True
    joined = " ".join(after)
    residual = [
        w for w in joined.split()
        if w.strip(".,!?'").lower() not in _CLOSING_WORDS
    ]
    return len(residual) >= 2


def _is_wrong_number(disposition: Optional[str]) -> bool:
    return " ".join((disposition or "").lower().split()) == "wrong number"


def _evaluate_wrong_number(turns: list[tuple[str, str]]) -> ObjectionGateResult:
    """A logged Wrong Number means the agent treated it as a denial, whatever
    words the owner used. The agent still owes a pivot, so this never returns
    `no_objection`, and the general word-count attempt rule doesn't apply."""
    found, quote, _ = _owner_objection(turns)

    last_agent_idx = max((i for i, (s, _) in enumerate(turns) if s == "Agent"), default=-1)
    trailing_owner = [t for _, t in turns[last_agent_idx + 1:]]
    agent_gave_up = last_agent_idx >= 0 and _AGENT_WRAPPED_UP.search(turns[last_agent_idx][1])
    if not agent_gave_up and any(_CLOSING_PHRASE.search(t) for t in trailing_owner):
        return {"verdict": "owner_ended_call", "objection_quote": quote or trailing_owner[-1],
                "reason": "owner closed the wrong-number call before the agent could pivot"}

    first_owner_idx = next((i for i, (s, _) in enumerate(turns) if s == "Owner"), len(turns))
    if any(s == "Agent" and _WRONG_NUMBER_PIVOT.search(t) for s, t in turns[first_owner_idx + 1:]):
        return {"verdict": "attempted", "objection_quote": quote,
                "reason": "agent asked about other property after the wrong-number call turned"}

    return {"verdict": "no_attempt", "objection_quote": quote,
            "reason": "wrong-number call with no question about other property"}


def evaluate(dialogue: str, disposition: Optional[str] = None) -> ObjectionGateResult:
    """Second-opinion evaluation of an existing "No Rebuttal" verdict.

    Call this only when the phrase/semantic/LLM matchers already returned
    "No". Never overrides a "Yes"; never invents a matched phrase -- callers
    decide how to translate the verdict into a stored result. `disposition` is
    what the agent logged; a Wrong Number call gets stricter rules.
    """
    if not dialogue or not dialogue.strip():
        # Truly nothing to judge -- excluded from flagging below. Keep this
        # distinct from "unparseable" (next check): measured against 198
        # labelled calls, several unparseable-but-non-empty transcripts were
        # genuinely-fair flags a human judge could still read and confirm --
        # see analyzer/objection_gate.py module docstring, 2026-11-05 note.
        return {"verdict": "unusable", "objection_quote": None,
                "reason": "empty transcript"}

    turns = _parse_turns(dialogue)
    if not turns:
        # Real text, just not in "Agent: ...\nOwner: ..." form (e.g. flat
        # text, or "Channel 1:"/"Channel 2:" from the diarization bug noted
        # in docs/REBUTTAL_FALSE_FLAGS.md). We cannot tell if this is fair or
        # not, so it is NOT excluded from flagging -- same conservative
        # default as before this module existed. Distinct from "unusable" so
        # a caller can still count how often this happens.
        return {"verdict": "unparseable", "objection_quote": None,
                "reason": "dialogue has content but no parseable Agent:/Owner: structure"}

    if _is_wrong_number(disposition):
        return _evaluate_wrong_number(turns)

    found, quote, idx = _owner_objection(turns)
    if not found:
        return {"verdict": "no_objection", "objection_quote": None,
                "reason": "owner never raised an objection -- nothing to rebut"}

    # No agent turn follows the objection at all -- narrow check for whether
    # the owner explicitly closed the call (not the agent's fault) before
    # falling through to the ordinary attempted/no_attempt logic below, which
    # would otherwise call this "no_attempt" by default.
    after_turns = turns[idx + 1:]
    if not any(s == "Agent" for s, _ in after_turns):
        owner_texts_after = [quote] + [t for s, t in after_turns if s == "Owner"]
        if any(_CLOSING_PHRASE.search(t) for t in owner_texts_after):
            return {"verdict": "owner_ended_call", "objection_quote": quote,
                    "reason": "owner objected and closed the call before the agent could respond"}

    if _agent_attempted(turns, idx):
        return {"verdict": "attempted", "objection_quote": quote,
                "reason": "agent's post-objection reply carries rebuttal content "
                          "the phrase library doesn't cover"}

    return {"verdict": "no_attempt", "objection_quote": quote,
            "reason": "owner objected and the agent did not push back"}
