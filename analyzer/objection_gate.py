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
"""
from __future__ import annotations

import re
from typing import Optional, TypedDict


class ObjectionGateResult(TypedDict):
    verdict: str          # "no_objection" | "attempted" | "no_attempt" | "unusable"
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

# --- agent-side rebuttal-attempt cues ----------------------------------------
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
# Agent language that means "I agree with you / I'm backing off" -- a turn
# containing one of these is a surrender even mid-sentence, and must not
# count as an attempt just because it repeats a sales keyword from the
# owner's own objection ("I'm not interested" said BY THE AGENT is agreement,
# not a pitch).
_AGENT_SURRENDER = re.compile(
    r"\bi'?m\s+not\s+interest\w*\b|\byou'?re\s+right\b|\bi\s+understand\b"
    r"|\bno\s+worries\b|\bmy\s+apologies\b|\bmy\s+bad\b",
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
        bare = bool(
            _BARE_DECLINE.match(text.strip())
            and len(text.split()) <= 6
            and i > 0
            and turns[i - 1][0] == "Agent"
            and _PITCH_KEYWORD.search(turns[i - 1][1])
        )
        if (strong or soft or bare) and not _POSITIVE_ENGAGEMENT.search(text):
            return True, text.strip(), i
    return False, None, -1


def _agent_attempted(turns: list[tuple[str, str]], objection_idx: int) -> bool:
    """Does the agent's post-objection text carry real content, not just closers?"""
    after = [t for s, t in turns[objection_idx + 1:] if s == "Agent"]
    after = [t for t in after if not _AGENT_SURRENDER.search(t)]
    if not after:
        return False
    if any(_REBUTTAL_OPENERS.search(t) for t in after):
        return True
    joined = " ".join(after)
    residual = [
        w for w in joined.split()
        if w.strip(".,!?'").lower() not in _CLOSING_WORDS
    ]
    return len(residual) >= 2


def evaluate(dialogue: str) -> ObjectionGateResult:
    """Second-opinion evaluation of an existing "No Rebuttal" verdict.

    Call this only when the phrase/semantic/LLM matchers already returned
    "No". Never overrides a "Yes"; never invents a matched phrase -- callers
    decide how to translate the verdict into a stored result.
    """
    turns = _parse_turns(dialogue)
    if not turns:
        return {"verdict": "unusable", "objection_quote": None,
                "reason": "no parseable speaker turns"}

    found, quote, idx = _owner_objection(turns)
    if not found:
        return {"verdict": "no_objection", "objection_quote": None,
                "reason": "owner never raised an objection -- nothing to rebut"}

    if _agent_attempted(turns, idx):
        return {"verdict": "attempted", "objection_quote": quote,
                "reason": "agent's post-objection reply carries rebuttal content "
                          "the phrase library doesn't cover"}

    return {"verdict": "no_attempt", "objection_quote": quote,
            "reason": "owner objected and the agent did not push back"}
