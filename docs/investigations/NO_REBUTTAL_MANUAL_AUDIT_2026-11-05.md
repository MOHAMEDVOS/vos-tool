# Manual audit: "No Rebuttal" flagged calls (2026-11-05)

## What this is

Mohamed asked for a human read of the Agent Audit Dashboard's "No Rebuttal"
flags: an independent judgment on what happens in these calls, not a re-run of
the detector.

**Population at the time**: 198 calls flagged `Rebuttal Detection = No` across
3 accounts (ayasamir 136, mohamedabdo 54, zeinab 8), out of 568 audit rows in
the local database. The same database later held 441 rows, all dated Nov 4. The
audit's queries were read-only and the cause of the drop is unknown.

**Sample**: the 30 newest No-Rebuttal calls, pulled read-only with
`scripts/rebuttal_eval/pull_sample.py --no-count 30 --yes-count 0`. The detector
was not run on them; each call was read and judged by hand. All 30 are one agent
and dialer (Belal Shaban Abdelrazek Hassan Ashry, dialer "resva", Nov 4 calls),
so this sample can't support conclusions about other agents.

## Corrected after Mohamed's review

The first version of this doc said no call in the sample was a fair flag. That
was wrong under two rules Mohamed confirmed:

1. **Wrong-number calls still need a rebuttal.** The agent should still ask
   whether the person or the owner has any property for sale.
2. **A call that ends right after an owner objection counts as No Rebuttal.** A
   transcript can't show who hung up, so the flag stands. The current gate still
   exempts a call when the owner explicitly closes it, for example "Goodbye".

Under those rules, at least 5 of the 30 are fair flags: 2 calls that end on an
objection with no closing word, and 3 wrong-number calls with no visible pivot.
The wrong-number transcripts have no speaker labels, so those 3 are less certain.

## Breakdown

Each call is counted once, by what its transcript shows.

| category | count | reading under the corrected rules |
|---|---:|---|
| Empty transcript | 6 | Nothing to judge. |
| No objection in the transcript | 14 | Call stops mid-pitch or the owner gives no pushback. Nothing visible to rebut. |
| Wrong Number disposition | 4 | 3 show a denial with no pivot and count as flags. 1 is a bad connection with no denial. |
| Call ends on an owner objection | 3 | 2 have no closing word and count as flags. 1 ends with "Goodbye" and is exempt. |
| Agent replies after the objection, then the transcript stops | 2 | Garbled or cut off, so it's unclear whether this was a rebuttal. |
| Owner's words cut off | 1 | "I'm not." Too little text to judge. |

## Examples (verbatim from the stored transcripts)

**Empty transcript**: call `c6322411`, disposition "Wrong Number", `dialogue: ""`.

**No objection in the transcript** (call `8db7100e`):
> Agent: Hello?\
> Owner: Hello?\
> Agent: Hey. Mrs. Allison.\
> Owner: May I ask who's calling?\
> Agent: Yeah. Hello, ma'. Am. This is daniel speaking. I just believe on a
> property at voltage drive. 67, 65. Am I right?\
> Agent: Am I right?

**Ends on an objection with an explicit close, exempt** (call `e8bdad31`):
> Owner: I'm sorry. Right now I've been sitting on the side of a road with a
> blown tire waiting for a rucker. I am not sellling my house. Thank you.
> Goodbye.

**Ends on an objection with no close, counts as a flag** (call `2dfc21e3`):
> Owner: No, not interestted.

**Agent replies, then the transcript stops** (call `e62a418b`):
> Owner: No, we're not interestted. That's where I live. That's not for sale.\
> Agent: Yeah, I'm same Mrs. Brown, have you.

## Other observations

1. **Transcription looks rough in this sample.** The agent's opener repeatedly
   comes out as "I just believe on a property", addresses are garbled, and the
   agent's spoken name varies (Danny Freeman, Daniel, Blake, Danny Raymond). The
   names may be a calling alias, which isn't confirmed. Bad transcription affects
   every text-based detector.
2. **The objection gate was not running when this audit was done.** Commit
   `1de3ac7` removed it on 2026-11-03 because it cleared calls where agents had
   skipped the rebuttal. The first version of this doc wrongly said it was
   computed but unused. It was rebuilt and re-enabled in commit `c9fc844`, so it
   only applies to calls audited after that code is deployed.
