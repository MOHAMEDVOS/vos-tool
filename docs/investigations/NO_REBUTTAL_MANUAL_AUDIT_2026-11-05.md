# Manual audit: "No Rebuttal" flagged calls (2026-11-05)

## What this is

Mohamed asked for a human read of the Agent Audit Dashboard's "No Rebuttal"
flags — not a re-run of the detector, an independent judgment call on what's
actually happening in these calls.

**Population**: 198 calls currently flagged `Rebuttal Detection = No` across
3 accounts (ayasamir 136, mohamedabdo 54, zeinab 8).

**Sample**: the 30 most recent No-Rebuttal calls, pulled read-only with the
existing `scripts/rebuttal_eval/pull_sample.py` (data retrieval only — the
detector itself was never invoked; every call below was read and judged by
hand). All 30 happen to be one agent/dialer (Belal Shaban Abdelrazek Hassan
Ashry, dialer "resva", Nov 4 run) since the pull is newest-first — this is a
recency sample, not a cross-agent one. Raw sample:
`scripts/rebuttal_eval/pull_sample.py --no-count 30 --yes-count 0`.

## Correction (same day, after Mohamed read this)

I got one category wrong below: **"Wrong Number" is not automatically exempt.**
The correct agent move on a wrong-number call is still to ask whether the
person (or anyone they know) has property to sell — skipping that is still a
miss. I'd assumed "wrong person on the line" meant "nothing to rebut," which
isn't right. The breakdown and percentages below are left as originally
written for the record, but treat the "Wrong Number" row as "needs the same
scrutiny as any other call," not "doesn't apply." See
[[objection-gate-not-wired-into-flagging]] for what changed as a result.

## Headline

**In 30 calls, zero show an agent clearly ignoring a real objection while the
conversation kept going.** The flag is overwhelmingly firing on calls that
never got far enough to have anything to rebut. This matches what's already
in memory from the last time this was reviewed ("90% not valid").

## Breakdown

| category | count | what it means |
|---|---:|---|
| Empty transcript | 6 (20%) | Nothing to judge — audio never got transcribed, or came back blank. Flagging these as a rebuttal failure blames the agent for a data gap, not a behavior. |
| No real objection raised | ~14 (47%) | Call ends mid-pitch, or the owner says nothing beyond "hello"/"who's this" before hanging up. There was nothing *to* rebut. |
| Wrong Number | ~4 (13%) | The person on the line explicitly isn't the target owner. "Rebuttal" doesn't apply — there's no owner objection to handle. |
| Owner objected, then hung up immediately | ~3 (10%) | A real objection ("not selling my house... goodbye"), but the owner ends the call in the same breath — the agent has no window to respond. Not a fair miss. |
| Owner objected, agent visibly started responding, cut off | 2 (7%) | The only cases that look like genuine detector misses — the agent *is* mid-rebuttal ("Yeah, I'm just saying, Barbara...") when the transcript/call cuts off. Likely the phrase-matcher needs a complete sentence it never got, not an agent who did nothing. |

Percentages don't round to a clean 100 — a few calls arguably straddle two
buckets (e.g. a wrong-number call with no speaker labels at all).

## Representative examples

**Empty transcript** (disposition "Wrong Number", logged as No-Rebuttal with
nothing to analyze):
> `dialogue: ""` — call ad2dff78... duration not even recorded.

**No objection, call never got there:**
> Agent: Hello?\
> Owner: Hello?\
> Agent: Hey, Mrs. Allison.\
> Owner: May I ask who's calling?\
> Agent: Yeah. Hello, ma'am. This is Daniel speaking. I just believe on a
> property at voltage drive. 67, 65. Am I right?\
> Agent: Am I right?

Transcript just stops. The owner never objects to anything — there's no
rebuttal to score here, favorable or not.

**Owner objected and hung up, agent had no chance:**
> Owner: I'm sorry. Right now I've been sitting on the side of a road with a
> blown tire waiting for a [wrecker]. I am not selling my house. Thank you.
> Goodbye.

That's the entire remainder of the call. Flagging the agent for "not
rebutting" this is flagging them for the owner hanging up.

**The closest thing to a real miss (and it's a stretch):**
> Owner: No, we're not interested. That's where I live. That's not for sale.\
> Agent: Yeah, I'm sure Mrs. Brown, have you...

The agent *is* rebutting — the sentence just gets cut off before it resolves
into something the phrase library recognizes. This reads like a transcription
cutoff, not an agent failure.

## Two things I noticed that aren't about this sample specifically

1. **The audio/transcription quality looks rough across the board** — "I just
   believe on a property" instead of (almost certainly) "I'm calling about a
   property," garbled addresses, agent names that come out differently in
   different calls (Danny Freeman / Daniel / Blake / Danny Raymond — probably
   one agent's cold-call alias, not a misattribution, but worth confirming).
   Bad transcription degrades every text-based detector riding on it, not
   just this one.
2. **`analyzer/objection_gate.py` already computes exactly this distinction**
   (`verdict`: `no_objection` / `attempted` / `no_attempt` / `unusable`) and
   it's stored per-call (`Objection Gate` column, `objection_gate_verdict` in
   the metadata). But nothing in the actual flagging logic
   (`backend/services/dashboard_service.py::get_flagged_calls`, or the
   webapp's own counts in `ActionsPage.tsx`/`CallReviewPage.tsx`/
   `utils/audit.ts`) reads it — flagging is still a flat
   `Rebuttal Detection == "No"` check. The infrastructure to exclude
   `no_objection`/`unusable` calls from this flag already exists and isn't
   wired in.

## Not a recommendation, just what I'd ask before changing anything

Wiring the Objection Gate into the flagging query would cut this flag's
volume a lot based on this sample — but per [[rebuttal-flag-polarity]], any
change that makes detection more lenient needs to be checked against a
stored-"Yes" control group too, not just measured by how many fewer flags it
produces. That's what `scripts/rebuttal_eval/` already exists for.
