"""Replay the REAL production code path: detect_rebuttals() -> objection_gate.evaluate().

This is not a parallel re-implementation like rules.py/test_rules.py -- it
imports and calls the actual production modules, so it measures exactly what
the app would do. Costs real Groq money when --llm is passed (roughly
$0.0015/call, only for calls where the phrase/semantic stages score <0.70).

Usage:
    .venv/bin/python scripts/rebuttal_eval/replay_production.py --llm
    .venv/bin/python scripts/rebuttal_eval/replay_production.py   # LLM off, free
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dialogue_utils import normalize_dialogue, agent_text  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="eval_data/sample.jsonl")
    ap.add_argument("--labels", default="eval_data/labeled.jsonl")
    ap.add_argument("--llm", action="store_true", help="enable the Groq LLM stage (costs money)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if not args.llm:
        os.environ["LLM_FALLBACK_ENABLED"] = "false"
    elif not os.getenv("GROQ_API_KEY"):
        sys.exit("--llm requires GROQ_API_KEY in the environment.")

    from analyzer.rebuttal_detection import KeywordRepository, SemanticDetectionEngine
    from analyzer import objection_gate

    repo = KeywordRepository(skip_database=True)
    engine = SemanticDetectionEngine(repo)
    llm_live = bool(engine.llm_fallback_enabled and engine.llm_evaluator)
    print(f"phrases={sum(len(v) for v in repo.get_all_phrases().values())} "
          f"llm={'ON (' + engine.llm_evaluator.client.model + ')' if llm_live else 'OFF'}", flush=True)
    if args.llm and not llm_live:
        sys.exit("Requested --llm but the evaluator failed to initialize -- check GROQ_API_KEY.")

    records = [json.loads(l) for l in Path(args.sample).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        records = records[: args.limit]

    out_path = Path(args.out) if args.out else Path(f"eval_data/replay_production_{'llm' if args.llm else 'nollm'}.jsonl")
    results = []
    started = time.time()
    llm_calls = 0
    for i, rec in enumerate(records, 1):
        dialogue = normalize_dialogue(rec.get("dialogue") or "")
        a_text = agent_text(rec.get("dialogue") or "")
        transcript = a_text if a_text else dialogue

        matches, feedback = engine.detect_rebuttals(transcript, dialogue=dialogue)
        if any(m.get("match_type") == "llm_evaluation" for m in matches) or \
           (not matches and feedback.get("llm_reasoning")):
            llm_calls += 1

        if matches:
            result = "Yes"
            best = matches[0]
            match_type = best.get("match_type")
            phrase = best.get("phrase")
        else:
            result = "No"
            match_type = None
            phrase = None
            gate = objection_gate.evaluate(dialogue)
            if gate["verdict"] == "no_objection":
                result = "N/A"
            elif gate["verdict"] == "attempted":
                result = "Yes"
                match_type = "objection_gate"
                phrase = gate["objection_quote"]

        results.append({
            "id": rec["id"], "cohort": rec.get("cohort"),
            "stored_verdict": rec.get("stored_verdict"),
            "replay_verdict": result, "replay_match_type": match_type, "replay_phrase": phrase,
        })
        if i % 20 == 0 or i == len(records):
            print(f"  {i}/{len(records)}  ({time.time()-started:.0f}s, {llm_calls} LLM calls so far)", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(results)} rows -> {out_path}  ({llm_calls} calls used the LLM stage, "
          f"~${llm_calls*0.0015:.3f} est.)")

    labels_path = Path(args.labels)
    if labels_path.exists():
        score(results, labels_path)


def score(results: list[dict], labels_path: Path) -> None:
    labels = {json.loads(l)["id"]: json.loads(l) for l in labels_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    WRONG = {"wrong_agent_did_rebut", "wrong_no_objection", "unusable"}
    by_id = {r["id"]: r for r in results}

    no_cohort = [(cid, lab) for cid, lab in labels.items() if cid in by_id]
    still_flagged = [(c, l) for c, l in no_cohort if by_id[c]["replay_verdict"] == "No"]
    wrong = [c for c, l in still_flagged if l["verdict"] in WRONG]
    fair_total = sum(1 for _, l in no_cohort if l["verdict"] == "flag_correct")
    fair_kept = sum(1 for c, l in still_flagged if l["verdict"] == "flag_correct")

    print(f"\n=== scored against {len(no_cohort)} labelled calls ===")
    print(f"still flagged 'No': {len(still_flagged)}   wrong: {len(wrong)}   "
          f"rate: {100.0*len(wrong)/len(still_flagged):.1f}%   fair kept: {fair_kept}/{fair_total}")

    controls = [r for r in results if r["cohort"] == "yes_control"]
    kept = sum(1 for r in controls if r["replay_verdict"] == "Yes")
    print(f"'Yes' control retention: {kept}/{len(controls)}")

    resolved_by_llm = [c for c, l in still_flagged if False]  # placeholder, see match_type below
    llm_recoveries = [r for r in results if r["replay_match_type"] == "llm_evaluation"]
    gate_recoveries = [r for r in results if r["replay_match_type"] == "objection_gate"]
    print(f"resolved via LLM stage: {len(llm_recoveries)}   via objection gate: {len(gate_recoveries)}")


if __name__ == "__main__":
    main()
