"""Candidate signals for two questions the current detector cannot answer:

  A. did the agent ATTEMPT a rebuttal (even indirect, or cut off by a hangup)?
  B. did the owner OBJECT at all (was there anything to rebut)?

Each rule is a pure function of the parsed dialogue, so every one can be scored
over the whole labelled set instead of eyeballed on a handful of calls.
"""
from __future__ import annotations
import re
from typing import Callable

# --- objection cues, owner side -------------------------------------------------
OBJECTION_STRONG = [
    # refusal to sell
    r"\bnot\s+interest", r"\bno\s+interest", r"\bnot\s+for\s+sale\b", r"\bnot\s+sell",
    r"\bdon'?t\s+want\s+to\s+sell", r"\bnot\s+planning\b", r"\bno\s+plans?\b",
    r"\bnever\b", r"\babsolutely\s+not\b", r"\bnot\s+available\b",
    # do-not-contact. "take me off" alone missed "take my number off" and
    # "take me out of your database" -- both real refusals in the sample.
    # Track B1/B2 (2026-09-02): this fires BEFORE any selling question is even
    # reached in several calls -- an owner objecting to being called at all is
    # still an objection, and the current bare-\bno\b code never distinguishes it.
    r"\btake\s+(?:me|my\s+\w+|us)\s+(?:off|out)\b", r"\bremove\s+(?:me|my)\b",
    r"\bsolicitation\b", r"\bstop\s+calling\b", r"\bdo\s+not\s+call\b",
    r"\bdon'?t\s+call\b", r"\bleave\s+me\s+alone\b", r"\bharass", r"\bsue\b",
    r"\blawyer\b", r"\bnot\s+getting\s+it\b", r"\btold\s+\w+\s+no\b",
    r"\bcalled?\s+me\s+\w+\s+times\b", r"\bcalls?\s+a\s+day\b", r"\bridiculous\b",
    r"\bemergency\s+line\b", r"\bcall\s+every\s+day\b", r"\bget\s+me\s+off\b",
    r"\bbreaking\s+the\s+law\b", r"\bdon'?t\s+call\s+(?:me|her|here|anymore)\b",
    r"\bwon'?t\s+sell\b",
    # hostility is an unambiguous refusal even when phrased in no standard way
    r"\bfuck", r"\bshit\b", r"\bgoddamn\b", r"\bpiss(?:ed|ing)?\s+off\b", r"\bidiot\b",
    # tenant / not the seller
    r"\bi\s+rent\b", r"\brenting\b", r"\bi'?m\s+a\s+tenant\b",
]

# Track B1/B2: a bare "no"/"nope"/"not" is only meaningful when it directly
# answers a selling question -- the SAME token answering "are you the owner?"
# means nothing. The existing code's bare \bno\b (rebuttal_detection.py:2385)
# fires on almost every call precisely because it ignores this. Substring match
# on the pitch keyword (not \b-bounded) deliberately catches ASR typos like
# "sellling"/"interestted" for free.
PITCH_KEYWORD = re.compile(r"sell|interest|consider|offer\b", re.I)
BARE_DECLINE = re.compile(r"^\s*(?:no+|nope|not\b)", re.I)
# An owner naming a price, or asking the price, is engaging with the deal --
# not objecting -- even if a stray "no" appears elsewhere in the same call
# (rejecting a low offer is not the same as refusing to sell).
POSITIVE_ENGAGEMENT = re.compile(
    r"\$\s?\d|\b\d{2,3}[,.]?\d{3}\b|\bhow\s+much\b|\bwhat.{0,15}offer(?:ing)?\b"
    r"|\bemail\s+me\b|\bbring\s+me\b|\bbottom\s+line\b|\bwe'?ll\s+talk\b"
    # Track B3: a reschedule is a soft lead, not a refusal, even if it reads
    # negative on the surface ("not right now, call back in six months").
    r"|\bcall\s+(?:me\s+)?back\s+in\b|\bcheck\s+back\b",
    re.I,
)
OBJECTION_SOFT = [
    r"\bno\b[\s,.!]+thanks?\b", r"\bno\b[\s,.!]+thank\s+you\b", r"\bnope\b", r"\bnah\b",
    r"\bno\b[\s,.!]+i'?m\s+not\b", r"\bno\b[\s,.!]+i\s+don'?t\b",
    r"\bno\b[\s,.!]+it'?s\s+not\b", r"\bno\b[\s,.!]+it\s+is\s?n'?t\b",
    r"\bno\b[\s,.!]+no\b[\s,.!]+no\b", r"\bnot\s+yet\b", r"\bnot\s+right\s+now\b",
    r"\bi'?m\s+busy\b", r"\bdon'?t\s+have\s+time\b", r"\bnot\s+available\b",
]
# Owner denies being the owner / wrong property. Whether this is an "objection"
# is the judgement call that separates the two groups, so keep it separate.
OWNERSHIP_DENIAL = [
    r"\bwrong\s+number\b", r"\bdon'?t\s+own\b", r"\bnot\s+the\s+owner\b",
    r"\bdon'?t\s+know\s+(?:anything\s+)?about\b", r"\bno\s+such\s+person\b",
]

# --- agent-side rebuttal attempt cues -------------------------------------------
# Openers an agent uses to push back. Deliberately allows a truncated tail, so a
# turn cut off by the owner hanging up still counts as an attempt.
REBUTTAL_OPENERS = [
    r"\bnot\s+even\b", r"\bhow\s+about\b", r"\bwhat\s+about\b",
    r"\bwould\s+you\s+(?:be\s+)?(?:open|consider|interest)", r"\bare\s+you\s+open\b",
    r"\bdo\s+you\s+have\s+(?:any\s+)?(?:other|another)\b",
    r"\bi'?m\s+(?:just\s+)?asking\b", r"\bi\s+was\s+asking\b",
    r"\bmaybe\s+(?:in|sometime|later|next)\b", r"\bdown\s+the\s+road\b",
    r"\banytime\s+soon\b", r"\bin\s+the\s+(?:near\s+)?future\b",
    r"\bbottom\s+line\b", r"\bare\s+you\s+(?:still\s+)?the\s+owner\b",
    r"\bthinking\s+about\s+sell", r"\bopen\s+to\s+sell", r"\bconsider\s+sell",
    r"\bby\s+the\s+end\s+of\s+the\s+year\b", r"\bcall\s+you\s+back\b",
    # From transcript analysis 2026-09-02 (Track A2/A3, docs/REBUTTAL_FALSE_FLAGS.md).
    # Zero hits on the 17-52 fair-flagged calls when scoped post-objection.
    r"\bany\s+other\s+one\b", r"\banother\s+one\b", r"\bmaybe\s+later\b",
    r"\bthis\s+year\b", r"\bnext\s+year\b", r"\bend\s+of\s+(?:the\s+)?year\b",
    r"\bthe\s+owner\??\s*$",  # "You not the owner?" cut short by a hangup
]

# Vocabulary that closes a call without adding anything: thanks, goodbyes,
# bare acknowledgments. Track A2's finding: real Group-1 (missed-rebuttal)
# calls always leave 2+ non-closing tokens in the agent's post-objection
# text; every correctly-flagged Group-2 call leaves 0-1. One-token margin,
# so this is a signal, not used alone (see post_objection_residual below).
CLOSING_WORDS = {
    "oh","ok","okay","yes","yeah","yep","yup","sure","sir","maam","ma","am","mam",
    "thank","thanks","you","your","bye","goodbye","have","a","an","the","good",
    "great","day","night","evening","morning","of","course","sorry","apologies",
    "i","im","m","my","me","we","no","not","nope","alright","all","right",
    "appreciate","it","understand","understood","problem","worries","care","take",
    "hello","hi","hey","well","uh","um","mhm",
    # connective filler -- carries no content on its own
    "and","so","for","but","just","really","very","that","this","then","there",
}
PITCH_CUES = [
    r"\bpropert", r"\bhouse\b", r"\bhome\b", r"\bsell", r"\bowner\b", r"\bbuy",
    r"\breal\s+estate\b", r"\boffer\b",
]
SALES_KEYWORDS = re.compile(
    r"\b(sell\w*|sold|sale|propert\w*|house|home|owner|own|interest\w*|"
    r"consider\w*|offer|price|cash|purchase|buy)\b", re.I
)
# Aux-inversion question fragment: "do you", "would you", "does it" -- the
# shape of a real rebuttal question, distinct from a declarative give-up.
# Track A1 caution: a bare "?" alone is not safe (Group 2's "Sure?" after
# being cursed at ends in "?" but isn't a rebuttal) -- always pair with this.
AUX_INVERSION = re.compile(
    r"\b(?:do|does|did|would|will|can|could|are|is|have|has)\s+"
    r"(?:you|it|he|she|they)\b", re.I
)

# Agent language that means "I agree with you / I'm backing off" -- distinct
# from REBUTTAL_OPENERS, which is the agent pushing. A turn containing one of
# these is a surrender even mid-sentence, and must not count as attempted
# content just because it happens to repeat a sales keyword from the owner's
# own objection ("I'm not interested" said BY THE AGENT is agreement, not a
# pitch). Bug found 2026-09-02: without this, 9542c58e and b5cdd17a -- both
# genuine give-ups -- were misread as rebuttal attempts. See
# docs/REBUTTAL_FALSE_FLAGS.md.
AGENT_SURRENDER = re.compile(
    r"\bi'?m\s+not\s+interest\w*\b|\byou'?re\s+right\b|\bi\s+understand\b"
    r"|\bno\s+worries\b|\bmy\s+apologies\b|\bmy\s+bad\b",
    re.I,
)

GIVE_UP_ONLY = re.compile(
    r"^(?:(?:okay|ok|alright|all\s+right|sure|no\s+problem|of\s+course|sorry|"
    r"thank\s+you|thanks|have\s+a\s+(?:good|nice|great)\s+(?:day|one)|bye|"
    r"bye\s+bye|goodbye|understood|got\s+it|yeah|yes|mm+|uh+|oh)[\s,.!?]*)+$",
    re.I,
)

# An agent turn that stops on an interrogative stem, with or without the "?".
TRUNCATED_STEM = re.compile(
    r"(?:\b(?:so|but|and|okay|ok)\b[\s,]*)?\b(?:do|are|would|did|have|is|can|could|"
    r"you|i'?m|i\s+was)\b[\w\s']{0,18}[.…]*\s*$",
    re.I,
)

C = lambda pats: [re.compile(p, re.I) for p in pats]
RX_STRONG, RX_SOFT, RX_OWN = C(OBJECTION_STRONG), C(OBJECTION_SOFT), C(OWNERSHIP_DENIAL)
RX_OPEN, RX_PITCH = C(REBUTTAL_OPENERS), C(PITCH_CUES)

def _any(rxs, text): return any(r.search(text) for r in rxs)


def features(turns: list[tuple[str, str]]) -> dict:
    """Structural + lexical features of one call. `turns` = [(speaker, text), ...]."""
    agent = [t for s, t in turns if s == "Agent"]
    owner = [t for s, t in turns if s == "Owner"]
    agent_text, owner_text = " ".join(agent), " ".join(owner)

    # index of the owner's first objection turn
    obj_idx = None
    for i, (s, t) in enumerate(turns):
        if s == "Owner" and (_any(RX_STRONG, t) or _any(RX_SOFT, t)):
            obj_idx = i
            break

    after_raw = [t for s, t in turns[obj_idx + 1:] if s == "Agent"] if obj_idx is not None else []
    # Drop surrender turns before counting content -- see AGENT_SURRENDER above.
    after = [t for t in after_raw if not AGENT_SURRENDER.search(t)]
    last_agent = agent[-1] if agent else ""

    # Bare "no" is only an objection when it directly answers a pitch question.
    bare_decline_after_pitch = False
    for i in range(1, len(turns)):
        spk, txt = turns[i]
        if spk == "Owner" and BARE_DECLINE.match(txt.strip()) and len(txt.split()) <= 6:
            prev = turns[i - 1]
            if prev[0] == "Agent" and PITCH_KEYWORD.search(prev[1]):
                bare_decline_after_pitch = True
                break

    return {
        "bare_decline_after_pitch": bare_decline_after_pitch,
        "positive_engagement": bool(POSITIVE_ENGAGEMENT.search(owner_text)),
        "n_turns": len(turns),
        "n_agent_turns": len(agent),
        "n_owner_turns": len(owner),
        "agent_words": len(agent_text.split()),
        "owner_words": len(owner_text.split()),
        "agent_spoke_last": bool(turns) and turns[-1][0] == "Agent",
        "objection_strong": _any(RX_STRONG, owner_text),
        "objection_soft": _any(RX_SOFT, owner_text),
        "ownership_denial": _any(RX_OWN, owner_text),
        "pitch_made": _any(RX_PITCH, agent_text),
        "objection_turn": obj_idx,
        "agent_turns_after_objection": len(after),
        "agent_words_after_objection": len(" ".join(after).split()),
        "question_after_objection": any("?" in t for t in after),
        "opener_after_objection": any(_any(RX_OPEN, t) for t in after),
        "opener_anywhere": _any(RX_OPEN, agent_text),
        # Interrupted attempt: agent's last turn opens a rebuttal and the call
        # stops there -- the owner hung up mid-push.
        "interrupted_attempt": bool(
            turns and turns[-1][0] == "Agent" and _any(RX_OPEN, last_agent)
        ),
        "last_agent_giveup_only": bool(last_agent and GIVE_UP_ONLY.match(last_agent.strip())),
        # The owner hung up mid-push: the agent's final turn trails off on an
        # interrogative stem ("Okay, but do you...", "So do you?"). ASR gives us
        # no hangup event, so the truncation itself is the signal.
        "truncated_question": bool(
            turns and turns[-1][0] == "Agent" and TRUNCATED_STEM.search(last_agent.strip())
        ),
        # From transcript analysis 2026-09-02 (Track A1/A2/A3, all three
        # independently converged on scoping to post-objection agent text --
        # matching pre-objection pitch language false-fires on fair flags).
        "aux_inversion_after_objection": bool(
            after and AUX_INVERSION.search(" ".join(after)) and "?" in " ".join(after)
        ),
        "sales_keyword_residual_after_objection": bool(
            after and SALES_KEYWORDS.search(
                " ".join(w for w in " ".join(after).split() if w.strip(".,!?").lower() not in CLOSING_WORDS)
            )
        ),
        "post_objection_content_words": len(
            [w for w in " ".join(after).split() if w.strip(".,!?'").lower() not in CLOSING_WORDS]
        ) if after else 0,
        "after_is_giveup_only": bool(after) and all(GIVE_UP_ONLY.match(t.strip()) for t in after),
    }


# ---- rules: attempted a rebuttal? (True = do NOT flag) -------------------------
RULES_ATTEMPT: dict[str, Callable[[dict], bool]] = {
    "A1_opener_after_objection":  lambda f: f["opener_after_objection"],
    "A2_interrupted_attempt":     lambda f: f["interrupted_attempt"],
    "A3_question_after_objection":lambda f: f["question_after_objection"] and not f["after_is_giveup_only"],
    "A4_substantive_after_obj":   lambda f: f["agent_words_after_objection"] >= 8 and not f["after_is_giveup_only"],
    "A5_opener_anywhere":         lambda f: f["opener_anywhere"],
    "A7_truncated_question":      lambda f: f["truncated_question"],
    "A8_opener_or_interrupted_or_truncated": lambda f: (
        f["opener_after_objection"] or f["interrupted_attempt"] or f["truncated_question"]
    ),
    "A9_aux_inversion":           lambda f: f["aux_inversion_after_objection"],
    "A10_sales_keyword_residual": lambda f: f["sales_keyword_residual_after_objection"],
    "A11_content_residual_ge2":   lambda f: f["post_objection_content_words"] >= 2,
    "A12_union_all": lambda f: (
        f["opener_after_objection"] or f["interrupted_attempt"] or f["truncated_question"]
        or f["aux_inversion_after_objection"] or f["sales_keyword_residual_after_objection"]
        or f["post_objection_content_words"] >= 2
    ),
}

# ---- rules: was there an objection? (False = do NOT flag) ----------------------
RULES_OBJECTION: dict[str, Callable[[dict], bool]] = {
    "B1_strong_only":        lambda f: f["objection_strong"],
    "B2_strong_or_soft":     lambda f: f["objection_strong"] or f["objection_soft"],
    "B3_strong_soft_or_own": lambda f: f["objection_strong"] or f["objection_soft"] or f["ownership_denial"],
    "B4_needs_pitch":        lambda f: (f["objection_strong"] or f["objection_soft"]) and f["pitch_made"],
    "B5_strong_needs_pitch": lambda f: f["objection_strong"] and f["pitch_made"],
    # Track B1/B2 (2026-09-02): the adjacency rule for bare "no", with a
    # positive-engagement guard so a rejected lowball offer doesn't count.
    "B6_strong_or_bare_decline": lambda f: (
        (f["objection_strong"] or f["bare_decline_after_pitch"]) and not f["positive_engagement"]
    ),
    "B7_strong_or_bare_or_soft": lambda f: (
        (f["objection_strong"] or f["objection_soft"] or f["bare_decline_after_pitch"])
        and not f["positive_engagement"]
    ),
}
