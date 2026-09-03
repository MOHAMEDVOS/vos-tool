"""Shared helpers for splitting stored call dialogue back into its speakers.

`agent_audit_results.transcript` holds the accent-corrected dialogue for BOTH
speakers, formatted by `format_as_dialogue` (lib/assemblyai_transcription.py:553).
Two label styles exist in the wild:

    intended     -> "Agent: ...\nOwner: ..."      (channel-based, reliable)
    diarization  -> "A: ...\nB: ..."              (positional guess, may be swapped)
    ACTUAL       -> "Channel 1: ...\nChannel 2: ..."

The third is what production really produces, on every call. AssemblyAI returns
`channel` as the STRINGS '1'/'2', but format_as_dialogue
(lib/assemblyai_transcription.py:587) compares to the INTEGERS 0/1, so both
branches miss and every utterance falls through to f"Channel {channel}".
The same type mismatch in extract_speaker_transcript (:621) makes
agent_transcript and owner_transcript come back empty -- verified against live
data. Channel 1 is the agent, Channel 2 the owner (the 1-indexed 0/1).

Production feeds the detector agent-only text as `transcript` and the full
dialogue separately as `dialogue`. A replay that feeds the whole thing in as
`transcript` does NOT reproduce production, so everything goes through here.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# "Agent:" / "Owner:" / "A:" / "B:" / "Speaker A:" at the start of a line.
TURN_RE = re.compile(
    r'^[ \t]*(?P<speaker>Agent|Owner|Channel\s+\d+|Speaker\s+[AB]|[AB])[ \t]*:[ \t]*(?P<text>.*)$',
    re.IGNORECASE | re.MULTILINE,
)

AGENT_LABELS = {"agent", "a", "speaker a", "channel 1", "channel 0"}
OWNER_LABELS = {"owner", "b", "speaker b", "channel 2"}


def parse_turns(dialogue: str) -> List[Tuple[str, str]]:
    """Return [(normalized_speaker, text), ...]. Empty list if unparseable."""
    if not dialogue:
        return []
    turns = []
    for m in TURN_RE.finditer(dialogue):
        raw = " ".join(m.group("speaker").split()).lower()
        text = m.group("text").strip()
        if not text:
            continue
        if raw in AGENT_LABELS:
            turns.append(("Agent", text))
        elif raw in OWNER_LABELS:
            turns.append(("Owner", text))
    return turns


def label_style(dialogue: str) -> str:
    """Which label convention this transcript uses.

    'named'   -> Agent:/Owner:. What the code intends to emit; not seen in practice.
    'channel' -> Channel 1:/Channel 2:. What production ACTUALLY emits. Identity is
                trustworthy (real audio channels) but no downstream code parses it.
    'letter' -> A:/B:, from diarization. Identity is a positional guess and may
                be inverted whenever the callee speaks first.
    'none'   -> no speaker structure at all; the objection-context logic in
                _extract_post_denial_agent_segments cannot work on this.
    """
    if not dialogue:
        return "none"
    if re.search(r'^[ \t]*(Agent|Owner)[ \t]*:', dialogue, re.IGNORECASE | re.MULTILINE):
        return "named"
    if re.search(r'^[ \t]*Channel\s+\d+[ \t]*:', dialogue, re.IGNORECASE | re.MULTILINE):
        return "channel"
    if re.search(r'^[ \t]*(Speaker\s+)?[AB][ \t]*:', dialogue, re.MULTILINE):
        return "letter"
    return "none"


def agent_text(dialogue: str) -> str:
    """Agent-only text, matching what production passes as `transcript`."""
    return " ".join(t for s, t in parse_turns(dialogue) if s == "Agent").strip()


def owner_text(dialogue: str) -> str:
    return " ".join(t for s, t in parse_turns(dialogue) if s == "Owner").strip()


def normalize_dialogue(dialogue: str) -> str:
    """Rewrite A:/B: to Agent:/Owner: .

    _extract_post_denial_agent_segments (analyzer/rebuttal_detection.py:2376)
    matches ONLY literal Agent:/Owner:. On a diarization transcript its regex
    finds nothing and it bails to `return [transcript]` -- the whole unfiltered
    both-speaker text. Normalizing lets the replay measure that gate as it was
    intended to work, so we can separate "the gate is wrong" from "the gate
    never ran".
    """
    turns = parse_turns(dialogue)
    if not turns:
        return dialogue or ""
    return "\n".join(f"{s}: {t}" for s, t in turns)
