# Rebuttal evaluation harness

Measures how often a **"No Rebuttal"** flag is wrong, and whether a fix actually
improves it. Replays stored transcripts through the real detector — no audio, no
AssemblyAI, no cost per run.

Plan: `~/.claude/plans/the-ration-of-the-fluffy-popcorn.md`

## Run it

```bash
# 1. Pull a read-only sample (needs the Railway Postgres URL)
DATABASE_URL='postgresql://...' .venv/bin/python scripts/rebuttal_eval/pull_sample.py

# 2. Replay detection over it
.venv/bin/python scripts/rebuttal_eval/replay.py --variant baseline

# 3. Score against judge labels (after Phase 2)
.venv/bin/python scripts/rebuttal_eval/score.py \
    --replay eval_data/replay_baseline.jsonl \
    --compare eval_data/replay_llm.jsonl
```

`--variant` runs counterfactuals without touching app code: `baseline`,
`normalized` (rewrite `A:`/`B:` to `Agent:`/`Owner:` so the post-denial objection
gate can run at all), `threshold` (with `--threshold`), `llm` (needs `GROQ_API_KEY`).

## Read all four numbers, not just the first

`score.py` reports wrong-flag rate, recovery, **harm**, and control retention.
A change that never flags anything scores 0% wrong-flag and is useless — harm and
control retention are what catch that. Verified on the smoke sample: dropping the
semantic threshold to 0.55 improved recovery and simultaneously un-flagged an
agent who genuinely gave up mid-call.

## Smoke test (no database needed)

```bash
.venv/bin/python scripts/rebuttal_eval/make_smoke_sample.py
.venv/bin/python scripts/rebuttal_eval/replay.py --sample eval_data/smoke_sample.jsonl \
    --variant baseline --skip-database --out eval_data/replay_smoke_baseline.jsonl
.venv/bin/python scripts/rebuttal_eval/score.py --labels eval_data/labeled_smoke.jsonl \
    --replay eval_data/replay_smoke_baseline.jsonl
```

Six synthetic calls covering each known failure mode. Use it to check the harness
still works after changing the detector.

## Notes

- `eval_data/` is gitignored — it holds real call transcripts.
- `pull_sample.py` opens a **read-only** session. Nothing is ever written to Railway.
- Replay feeds the detector **agent-only** text as `transcript` with the dialogue
  passed separately, matching production (`lib/agent_only_detector.py:415`).
  Feeding the whole dialogue in as `transcript` would not reproduce production.
- The stored transcript is already accent-corrected, so correction is not re-applied.
