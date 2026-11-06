# Lite Audit Wrong Dispo: Dead Call vs Unknown

## Goal

Flag a Lite Audit call when the owner channel's audio clearly contradicts the
logged disposition. Lite Audit has no transcript, so this uses audio only.

| Logged | Owner channel | Result | Reason label |
|---|---|---|---|
| Unknown | silent | Wrong Dispo | `Unk instead of Dead` |
| Dead Call | sound | Wrong Dispo | `Dead instead of Unk` |
| Anything else | not checked | no flag | none |

Heavy Audit and Campaign Audit are unchanged, and audio between "silent" and
"sound" is never flagged.

## Measured on 495 recordings (right channel = owner)

Recordings were dated 2026-11-05: 199 Dead Call and 296 Unknown.

- A plain "any sound" rule doesn't work. Many Dead Calls have a beep of about
  300 ms near 660 Hz at the start of the call, which is a phone-system tone rather
  than the owner.
- MP3 encoding leaves faint noise, so "zero sound" can't mean a sample value of
  exactly 0. Only 29 of 199 Dead Calls are exactly 0, and 153 peak at 100 or below
  (out of 32,768) before tones are removed.

Rules, using 50 ms frames:

- Sound frame: loudness (RMS) of at least 150, and not a tone. A tone is a frame
  where 90% or more of the energy sits in 5 frequency bins. The frames on either
  side of a tone are dropped too.
- Silent: peak of 100 or below outside tones.
- Sound: at least 300 ms of sound frames.

The thresholds came from those 495 files. New recordings arrived while this was
being built, so the shipped code was then replayed on all 615 Dead Call and Unknown
files through `process_single_file_lite`:

| Logged | Calls | Flagged |
|---|---:|---:|
| Dead Call | 240 | 4 (1.7%) |
| Unknown | 375 | 23 (6.1%) |

A sample of 100 Wrong Number and Decision Maker - NYI calls produced no flags.

## Update after listening

Mohamed listened to 11 flagged Unknown calls from one agent. Only 2 were really
silent. The other 9 had air sound on the owner side, which he counts as a valid
Unknown. Those calls never reached the loudness limit above, so "silent" now also
needs an air sound level of 4.5 or below. That level is the 90th percentile, across
the call's frames, of the energy above 200 Hz.

| Call | Mohamed | Air level |
|---|---|---:|
| 2 calls | silent | 2.6, 3.06 |
| 1 call | air sound | 3.05 |
| 8 calls | air sound | 5.9 to 18 |

The one air-sound call at 3.05 measures the same as a confirmed-silent call, so it
stays flagged. Needs a second listen.

Mohamed then confirmed the other side of the rule: air sound is not a valid Dead
Call, because a Dead Call means close to nothing. A Dead Call now also flags when its
air level is above 4.5.

## Not verified

- The air limit rests on 11 Unknown calls from one agent, so other agents and dialers
  are untested.
- Mohamed spot-checked the flagged Dead Calls and said they sound right. That was a
  sample of the 76, not all of them.

## Scope

- New `lib/lite_wrong_dispo_detector.py`, called from `process_single_file_lite`
  for those two dispositions only, so other calls cost nothing extra.
- Stored in `detection_results` and read back as the existing `Wrong Dispo
  Detection` and `Wrong Dispo Reason` columns. The Lite dashboard tile, Actions and
  Call Review already show those.
- Existing rows change only if they are re-audited.
