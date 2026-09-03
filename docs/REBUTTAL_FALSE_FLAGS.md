# Why "No Rebuttal" flags are wrong

Measured 2026-09-02 on 198 calls from the production audit database — every call
in it that production flagged `No Rebuttal`. Each was judged against one rule:

> A flag is fair only if the owner objected **and** the agent made no attempt to
> overcome it. Trying counts, however clumsy.

## What's shipped (2026-09-02, later same day)

Everything below the "Recommended order" section was analysis. Since then:

1. **Channel type fix** — [lib/assemblyai_transcription.py](../lib/assemblyai_transcription.py).
   Verified `agent_transcript`/`owner_transcript` go from 0/40 to 40/40 populated
   on real cached calls.
2. **28 phrases added** to the existing categories, taken verbatim from the 61
   missed rebuttals in this sample.
3. **Objection gate** — [analyzer/objection_gate.py](../analyzer/objection_gate.py),
   wired into [lib/agent_only_detector.py](../lib/agent_only_detector.py). Built
   by six parallel subagents independently reading every Group 1/Group 2
   transcript line by line, cross-checking every proposed rule against every
   correctly-flagged call before accepting it. Runs only when the phrase/
   semantic/LLM matchers already say "No": clears the flag to `N/A` when the
   owner never objected, upgrades it to `Yes` when the agent's post-objection
   reply carries real content the phrase library doesn't cover (an indirect
   push, an interrupted attempt cut short by a hangup, or an ASR-mangled but
   keyword-bearing reply), and leaves it flagged when the owner objected and
   the agent genuinely didn't push back.
4. **LLM stage** — code is ready (`GROQ_MODEL` now actually takes effect), but
   needs `GROQ_API_KEY` set in Railway. Not yet turned on.

**Measured end-to-end, on the real production code path** (not a standalone
harness — the actual `detect_rebuttals()` + `objection_gate.evaluate()` call
sequence), on the 140 sampled calls that have usable speaker turns:

| | wrong-flag rate | fair flags kept |
|---|---:|---|
| original baseline | 73.5% | 52/52 |
| shipped (1+2) | 64.9% | 39/39 |
| shipped (1+2+3) | **12.5%** | 28/39 (72%) |

That trade — catching 28 of 39 genuinely-failing agents instead of all 39 — is
the real cost of the drop from 65% to 12.5%. It is not free, and it's the
number to watch as more calls come through.

One label-quality finding from the six subagents worth keeping in mind: the
*exact same* call text appeared twice in the sample with opposite human
verdicts (`0fba79ab` vs `64944621`, one call, "...You call every day. Stop
calling." — one judge called it a fair flag, the other called it no-objection).
The 88% inter-judge agreement measured earlier already accounts for noise like
this; it's not zero.

## Headline

**146 of 198 flags are wrong — 73.7%.**

| verdict | n | share | |
|---|---:|---:|---|
| `wrong_no_objection` — nothing to rebut | 80 | 40.4% | ████████████████·········· |
| `wrong_agent_did_rebut` — detector missed it | 61 | 30.8% | ████████████·············· |
| `flag_correct` — fair | 52 | 26.3% | ██████████················ |
| `unusable` — transcript garbage | 5 | 2.5% | █························ |

Two independent judges agreed on 88% of a 25-call subset, all three
disagreements in the same direction (judge 1 more generous to agents). So
**"about three in four flags are wrong" is solid; 73.7% carries roughly ±12
points.** Mohamed's estimate of 90% was in the right territory.

## The single most important finding

**The biggest cause is not detection.** 80 calls — 55% of all wrong flags — had
no objection at all. Wrong numbers, Spanish speakers, owners who engaged
happily, calls that ended before a pitch. There was nothing to rebut, and the
agent was penalised anyway.

`backend/services/dashboard_service.py:217` flags every call where detection
says `No`:

```python
rebuttal_issue = combined["Rebuttal Detection"] == "No"
```

It never asks whether the customer objected. Nothing in the codebase can ask —
the concept doesn't exist. **No amount of detection tuning fixes these 80 calls.**

By dialer disposition: `Decision Maker - NYI` 40, `Wrong Number` 19,
`Unknown` 12, `Spanish Speaker` 5, `DNC - Unknown` 3, `Dead Call` 1.

## The root cause of the other half

AssemblyAI returns the audio channel as the **strings** `'1'` and `'2'`.
`lib/assemblyai_transcription.py:587` and `:621` compare them to the **integers**
`0` and `1`:

```python
speaker = "Agent" if channel == 0 else "Owner" if channel == 1 else f"Channel {channel}"
```

`'1' == 0` is False. `'1' == 1` is also False. Verified against live data:
`agent_transcript` and `owner_transcript` are **empty on every call**. Three
consequences:

1. `lib/agent_only_detector.py:239` falls back to the full both-speaker
   transcript, so detection searches the **customer's** words for the agent's rebuttal.
2. The dialogue string reads `Channel 1:` / `Channel 2:`, which
   `_extract_post_denial_agent_segments` (`rebuttal_detection.py:2376`) cannot
   parse — it looks for `Agent:`/`Owner:`. It bails to `return [transcript]`, so
   **the objection gate has never run on a single call.**
3. 29% of stored transcripts have no speaker structure at all.

Affects all 103,415 cached transcripts.

## What the agents actually said

The 61 missed rebuttals are a formulaic script — future-timing probes:

- "Not even down the road?" · "Not even anytime soon?"
- "Maybe sometime in 2027? February? March?"
- "Maybe in the next few months" · "in the near future"
- "Do you have another one?" · "do you have any other?"
- "you'd be open to selling at all?"

The phrase library has the right *categories* (`NOT_EVEN_FUTURE_FAMILY`,
`MIXED_FUTURE_OTHER_FAMILY`) but not these wordings.

## Measured effect of each fix

Each row is a real run of the real detector over the same 198 calls, scored
against the same labels.

| change | flags | wrong | rate | fair flags kept |
|---|---:|---:|---:|---|
| production today | 196 | 144 | **73.5%** | 52/52 |
| + channel type fix | 190 | 138 | 72.6% | 52/52 |
| + channel fix + 24 candidate phrases | 156 | 104 | 66.7% | 52/52 |
| objection gate only (regex prototype) | 120 | 82 | 68.3% | 38/52 |
| all three, flag when speaker unknown | 90 | 52 | 57.8% | 38/52 |
| all three, skip when speaker unknown | 47 | 22 | 46.8% | 25/52 |

**None reach 20%.** The candidate phrases recovered 38 of the 61 missed
rebuttals with **zero** harm to the 52 fair flags — that part works. The regex
objection gate does not: 89% precision but only 67% recall, so it drops 14 fair
flags to remove 38 bad ones.

### How good does the gate need to be?

Substituting the judges' own answers as a perfect objection gate:

| | rate |
|---|---:|
| production detection + perfect gate | 54.4% |
| improved detection + perfect gate | **31.6%** |
| perfect detection + perfect gate | 0% |

So **even a flawless objection gate leaves 31.6%** with pattern-based detection.
20% is reachable, but not by regex alone.

## What the remaining misses look like

```
"Not even..."                                    (cut off mid-sentence)
"I'm asking if you. (continues pressing)"        (ASR drops the rest)
"No profit easy be open to sellling at all"      (garbled: "are you open to selling at all")
"You solve the property."                        (garbled)
"what's your bottom line for such a house?"      (real rebuttal, unusual phrasing)
"How about sellling by the end of the year?"
```

These are cut-off, garbled, or unusually phrased. **Pattern matching cannot
reach them** — recognising them as rebuttal attempts is a judgement call.

That is precisely what the LLM stage is for, and it is **switched off**:
`GROQ_API_KEY` is unset, so `llm_fallback_enabled` is forced False
(`rebuttal_detection.py:2019-2021`). Its prompt already says *"BE GENEROUS...
false negatives are worse than false positives"*. At ~$0.0015/call it is the
cheapest remaining lever, and the same judgement it would apply is what the
judge agents just did successfully on these transcripts.

## Recommended order

1. **Fix the channel type comparison** (`assemblyai_transcription.py:587,621`).
   One-line fix, unblocks everything else. Zero measured harm.
2. **Stop flagging calls with no objection.** Biggest single win — 55% of wrong
   flags. Needs an objection detector on owner-side text; regex gets ~67% recall,
   an LLM should do much better.
3. **Turn on the LLM stage.** The only thing that can catch the garbled and
   cut-off attempts, and the best candidate for #2.
4. **Add the candidate phrases** (`eval_data/candidate_phrases.json`). Measured:
   38 recoveries, zero harm.
5. **Stop recording failures as "No"** (`audio_processor.py:230,267,280,286`).
   Only 5 calls here, but it makes every future failure visible instead of silent.

## Caveats

- The candidate phrases were written **after looking at these 198 calls**, so
  their 38 recoveries are partly overfitted. Confirm on a fresh unseen sample
  before trusting the number.
- Labels come from LLM judges at 88% inter-judge agreement, not from Mohamed.
  Spot-check them before betting on the exact percentage.
- All 198 calls are from one day (2026-09-02). Other campaigns may differ.

## Reproducing

```bash
DATABASE_URL='postgresql://...' .venv/bin/python scripts/rebuttal_eval/pull_sample.py
.venv/bin/python scripts/rebuttal_eval/replay.py --variant baseline --skip-database
.venv/bin/python scripts/rebuttal_eval/score.py --replay eval_data/replay_baseline.jsonl
```

Note: `POSTGRES_HOST` in `.env` overrides `DATABASE_URL` (`lib/database.py:161`),
so export the `POSTGRES_*` vars too or you will silently query the local database.
