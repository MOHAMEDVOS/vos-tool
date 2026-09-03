"""Replay rebuttal detection over stored transcripts. No audio, no AssemblyAI, no cost.

Calls the same text entry point production uses --
SemanticDetectionEngine.detect_rebuttals(transcript, dialogue=) at
analyzer/rebuttal_detection.py:2063 -- so results are comparable to the stored
verdict. The stored transcript is already accent-corrected, so correction is
NOT re-applied.

Variants let us ask counterfactuals without touching app code:

    baseline    exactly as production ran it
    normalized  rewrite A:/B: -> Agent:/Owner: so the post-denial objection gate
                can actually run (on diarization calls it currently never does)
    threshold   lower the semantic cutoff
    llm         allow the Groq stage (needs GROQ_API_KEY)

Usage:
    .venv/bin/python scripts/rebuttal_eval/replay.py --variant baseline
    .venv/bin/python scripts/rebuttal_eval/replay.py --variant threshold --threshold 0.55
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dialogue_utils import agent_text, normalize_dialogue, owner_text  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


def build_engine(skip_database: bool, threshold: float | None, allow_llm: bool,
                 extra_phrases: str | None = None):
    from analyzer.rebuttal_detection import KeywordRepository, SemanticDetectionEngine

    if not allow_llm:
        # Force the stage off deterministically rather than relying on a missing key.
        os.environ["LLM_FALLBACK_ENABLED"] = "false"

    repo = KeywordRepository(skip_database=skip_database)

    if extra_phrases:
        # Candidate phrases under test. Injected into the live repo so the real
        # matching code path is exercised -- no app code is modified.
        import json as _json
        extra = _json.loads(Path(extra_phrases).read_text(encoding="utf-8"))
        base = repo.get_all_phrases()
        added = 0
        for cat, phrases in extra.items():
            bucket = base.setdefault(cat, [])
            for ph in phrases:
                if ph not in bucket:
                    bucket.append(ph)
                    added += 1
        repo.get_all_phrases = lambda _b=base: _b
        print(f"injected {added} candidate phrases from {extra_phrases}", flush=True)

    engine = SemanticDetectionEngine(repo)
    if threshold is not None:
        engine.semantic_threshold = max(0.0, min(threshold, 1.0))

    phrase_count = sum(len(v) for v in repo.get_all_phrases().values())
    print(
        f"engine ready | phrases={phrase_count} "
        f"| semantic_threshold={engine.semantic_threshold} "
        f"| llm={'ON' if engine.llm_fallback_enabled and engine.llm_evaluator else 'OFF'}",
        flush=True,
    )
    if allow_llm and not (engine.llm_fallback_enabled and engine.llm_evaluator):
        print("  WARNING: --variant llm requested but GROQ_API_KEY is not set; stage stays off.", flush=True)
    return engine


def detect(engine, transcript: str, dialogue: str) -> dict:
    """One detection pass, flattened to the fields we compare on."""
    if not transcript.strip():
        return {"verdict": "No", "confidence": 0.0, "match_type": None, "phrase": None, "n_matches": 0}
    matches, _feedback = engine.detect_rebuttals(transcript, dialogue=dialogue)
    if not matches:
        return {"verdict": "No", "confidence": 0.0, "match_type": None, "phrase": None, "n_matches": 0}
    best = matches[0]
    return {
        "verdict": "Yes",
        "confidence": round(float(best.get("confidence", 0.0)), 4),
        "match_type": best.get("match_type"),
        "phrase": best.get("phrase"),
        "n_matches": len(matches),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="eval_data/sample.jsonl")
    ap.add_argument("--out", default=None, help="default: eval_data/replay_<variant>.jsonl")
    ap.add_argument("--variant", default="baseline", choices=["baseline", "normalized", "threshold", "llm"])
    ap.add_argument("--extra-phrases", default=None, help="JSON {category: [phrase,...]} of candidate phrases to add")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--skip-database", action="store_true",
                    help="use hardcoded phrases only; default queries the DB so the phrase set matches production")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-swap-test", action="store_true", help="skip the speaker-swap probe (it doubles runtime)")
    args = ap.parse_args()

    sample_path = Path(args.sample)
    if not sample_path.exists():
        sys.exit(f"{sample_path} not found -- run pull_sample.py first.")

    records = [json.loads(line) for line in sample_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    engine = build_engine(
        skip_database=args.skip_database,
        threshold=args.threshold if args.variant == "threshold" else None,
        allow_llm=(args.variant == "llm"),
        extra_phrases=args.extra_phrases,
    )

    out_path = Path(args.out) if args.out else Path(f"eval_data/replay_{args.variant}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    results = []
    for i, rec in enumerate(records, 1):
        dialogue_raw = rec.get("dialogue") or ""
        a_text = agent_text(dialogue_raw)
        o_text = owner_text(dialogue_raw)

        if args.variant == "normalized":
            # The counterfactual: what detection would see if the channel type bug
            # (assemblyai_transcription.py:587,621) were fixed -- agent-only text
            # as `transcript`, and Agent:/Owner: labels the objection gate can parse.
            dialogue = normalize_dialogue(dialogue_raw)
            transcript = a_text if a_text else dialogue_raw
        else:
            # Faithful to production. agent_transcript came back EMPTY for every
            # call, so agent_only_detector.py:239 fell back to the full
            # both-speaker transcript, and the dialogue string it passed said
            # "Channel N:" which _extract_post_denial_agent_segments cannot parse.
            dialogue = dialogue_raw
            transcript = dialogue_raw

        row = {
            "id": rec["id"],
            "cohort": rec.get("cohort"),
            "variant": args.variant,
            "stored_verdict": rec.get("stored_verdict"),
            "transcript_empty": rec.get("transcript_empty"),
            "label_style": rec.get("label_style"),
            "first_speaker": rec.get("first_speaker"),
        }
        row.update({f"replay_{k}": v for k, v in detect(engine, transcript, dialogue).items()})

        # Speaker-swap probe: does detection fire on the OWNER half but not the
        # AGENT half? That is the signature of A/B being inverted -- the real
        # agent's rebuttal sitting in the slot we labelled 'Owner'.
        #
        # Only meaningful on 'letter' (diarization) transcripts. Multichannel
        # assigns speakers from the actual audio channel
        # (lib/assemblyai_transcription.py:587), so a swap cannot happen there
        # and any hit on the owner half is just the library over-matching
        # ordinary customer speech -- noise, not evidence.
        swap_eligible = (not args.no_swap_test) and o_text and rec.get("label_style") in ("letter", "channel")
        if swap_eligible:
            swap = detect(engine, o_text, dialogue)
            row["swap_verdict"] = swap["verdict"]
            row["swap_phrase"] = swap["phrase"]
            row["swap_confidence"] = swap["confidence"]
            row["swap_indicated"] = bool(
                row["replay_verdict"] == "No" and swap["verdict"] == "Yes"
            )
        else:
            row["swap_verdict"] = None
            row["swap_phrase"] = None
            row["swap_confidence"] = None
            row["swap_indicated"] = False

        results.append(row)
        if i % 25 == 0 or i == len(records):
            print(f"  {i}/{len(records)} ({time.time() - started:.0f}s)", flush=True)

    with out_path.open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nwrote {len(results)} rows -> {out_path}")
    report(results)


def report(rows: list[dict]) -> None:
    no_rows = [r for r in rows if r["cohort"] == "no"]
    yes_rows = [r for r in rows if r["cohort"] == "yes_control"]

    if no_rows:
        agree = sum(1 for r in no_rows if r["replay_verdict"] == "No")
        print(f"\n'No' cohort ({len(no_rows)}): replay reproduces 'No' on {agree} "
              f"({100.0 * agree / len(no_rows):.1f}%)")
        swap = sum(1 for r in no_rows if r.get("swap_indicated"))
        print(f"  speaker-swap indicated (fires on owner half, not agent half): {swap} "
              f"({100.0 * swap / len(no_rows):.1f}%)")
        empty = sum(1 for r in no_rows if r.get("transcript_empty"))
        print(f"  empty transcript (never analysed):                           {empty} "
              f"({100.0 * empty / len(no_rows):.1f}%)")

    if yes_rows:
        agree = sum(1 for r in yes_rows if r["replay_verdict"] == "Yes")
        print(f"\n'Yes' control ({len(yes_rows)}): replay reproduces 'Yes' on {agree} "
              f"({100.0 * agree / len(yes_rows):.1f}%)")

    types: dict[str, int] = {}
    for r in rows:
        if r["replay_verdict"] == "Yes":
            k = str(r.get("replay_match_type"))
            types[k] = types.get(k, 0) + 1
    if types:
        print("\nwhich stage resolved the 'Yes' verdicts:")
        for k, n in sorted(types.items(), key=lambda kv: -kv[1]):
            print(f"  {k:>16} : {n}")


if __name__ == "__main__":
    main()
