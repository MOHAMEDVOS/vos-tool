"""Score a replay against the human/judge labels.

    .venv/bin/python scripts/rebuttal_eval/score.py \
        --labels eval_data/labeled.jsonl \
        --replay eval_data/replay_baseline.jsonl \
        [--compare eval_data/replay_llm.jsonl]

Reports four numbers, because the headline one alone is misleading:

  wrong-flag rate   share of still-flagged calls that shouldn't be. TARGET <= 20%
  recovery          wrongly-flagged calls the change un-flagged. The win.
  harm              genuinely-failed calls the change ALSO un-flagged. The cost.
  control retention stored-'Yes' calls still coming back Yes.

A change that drives wrong-flag rate to zero by never flagging anything scores
perfectly on the first number and destroys the other two. Read them together.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Judge verdicts that mean "this call should not have been flagged".
WRONG = {"wrong_agent_did_rebut", "wrong_no_objection", "unusable"}
CORRECT = {"flag_correct"}


def load(path: Path) -> dict[str, dict]:
    if not path.exists():
        sys.exit(f"{path} not found.")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


def pct(n: int, d: int) -> str:
    return f"{n:>4} / {d:<4} ({100.0 * n / d:5.1f}%)" if d else f"{n:>4} / 0    (  n/a )"


def evaluate(labels: dict, replay: dict, name: str) -> dict:
    # A call remains flagged if detection still says 'No'.
    no_cohort = [
        (cid, lab) for cid, lab in labels.items()
        if replay.get(cid) and replay[cid].get("cohort") == "no"
    ]
    if not no_cohort:
        sys.exit("no overlapping 'no'-cohort calls between labels and replay.")

    still_flagged = [(c, l) for c, l in no_cohort if replay[c]["replay_verdict"] == "No"]
    unflagged = [(c, l) for c, l in no_cohort if replay[c]["replay_verdict"] == "Yes"]

    wrong_still = [c for c, l in still_flagged if l["verdict"] in WRONG]
    recovered = [c for c, l in unflagged if l["verdict"] in WRONG]
    harmed = [c for c, l in unflagged if l["verdict"] in CORRECT]

    total_wrong = sum(1 for _, l in no_cohort if l["verdict"] in WRONG)
    total_correct = sum(1 for _, l in no_cohort if l["verdict"] in CORRECT)

    controls = [
        cid for cid, r in replay.items()
        if r.get("cohort") == "yes_control"
    ]
    controls_kept = [c for c in controls if replay[c]["replay_verdict"] == "Yes"]

    print(f"\n=== {name} ===")
    print(f"labeled 'No' calls          : {len(no_cohort)}  "
          f"({total_wrong} wrongly flagged, {total_correct} correctly flagged)")
    print(f"still flagged               : {len(still_flagged)}")
    print(f"  wrong-flag rate  TARGET<=20% : {pct(len(wrong_still), len(still_flagged))}")
    print(f"  recovery  (wrong un-flagged) : {pct(len(recovered), total_wrong)}")
    print(f"  harm      (right un-flagged) : {pct(len(harmed), total_correct)}")
    print(f"  control retention            : {pct(len(controls_kept), len(controls))}")

    if len(still_flagged):
        rate = 100.0 * len(wrong_still) / len(still_flagged)
        print(f"  -> {'PASS' if rate <= 20.0 else 'FAIL'} on wrong-flag rate ({rate:.1f}%)")

    breakdown: dict[str, int] = {}
    for c, l in still_flagged:
        breakdown[l["verdict"]] = breakdown.get(l["verdict"], 0) + 1
    if breakdown:
        print("  remaining flags by judge verdict:")
        for k, n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<26} {n}")

    return {
        "name": name,
        "wrong_rate": (100.0 * len(wrong_still) / len(still_flagged)) if still_flagged else 0.0,
        "recovered": len(recovered),
        "harmed": len(harmed),
        "controls_kept": len(controls_kept),
        "controls_total": len(controls),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="eval_data/labeled.jsonl")
    ap.add_argument("--replay", default="eval_data/replay_baseline.jsonl")
    ap.add_argument("--compare", default=None, help="a second replay to diff against the first")
    args = ap.parse_args()

    labels = load(Path(args.labels))
    base = evaluate(labels, load(Path(args.replay)), Path(args.replay).stem)

    if args.compare:
        other = evaluate(labels, load(Path(args.compare)), Path(args.compare).stem)
        print("\n=== change ===")
        print(f"wrong-flag rate : {base['wrong_rate']:.1f}%  ->  {other['wrong_rate']:.1f}%  "
              f"({other['wrong_rate'] - base['wrong_rate']:+.1f} pts)")
        print(f"recovered       : {base['recovered']}  ->  {other['recovered']}")
        print(f"harm            : {base['harmed']}  ->  {other['harmed']}"
              f"{'   <-- WATCH THIS' if other['harmed'] > base['harmed'] else ''}")
        print(f"controls kept   : {base['controls_kept']}/{base['controls_total']}"
              f"  ->  {other['controls_kept']}/{other['controls_total']}")


if __name__ == "__main__":
    main()
