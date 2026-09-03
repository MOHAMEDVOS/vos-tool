"""Merge judge batch results into eval_data/labeled.jsonl and check inter-judge agreement."""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path

WRONG = {"wrong_agent_did_rebut", "wrong_no_objection", "unusable"}
VALID = {"flag_correct", "wrong_agent_did_rebut", "wrong_no_objection", "unusable"}


def read_jsonl(p: Path) -> list[dict]:
    out, bad = [], 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("```"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
            print(f"  !! {p.name}:{i} unparseable", file=sys.stderr)
    if bad:
        print(f"  !! {p.name}: {bad} bad lines", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-dir", required=True)
    ap.add_argument("--sample", default="eval_data/sample.jsonl")
    ap.add_argument("--out", default="eval_data/labeled.jsonl")
    args = ap.parse_args()

    jd = Path(args.judge_dir)
    sample = {json.loads(l)["id"]: json.loads(l)
              for l in Path(args.sample).read_text(encoding="utf-8").splitlines() if l.strip()}
    expected = {cid for cid, r in sample.items() if r["cohort"] == "no"}

    labels: dict[str, dict] = {}
    for f in sorted(jd.glob("result_*.jsonl")):
        rows = read_jsonl(f)
        print(f"{f.name}: {len(rows)} rows")
        for r in rows:
            cid = r.get("id")
            if cid in labels:
                print(f"  !! duplicate label for {cid}", file=sys.stderr)
            if r.get("verdict") not in VALID:
                print(f"  !! bad verdict {r.get('verdict')!r} on {cid}", file=sys.stderr)
                continue
            labels[cid] = r

    missing = expected - labels.keys()
    extra = labels.keys() - expected
    print(f"\nlabeled {len(labels)} / {len(expected)} expected")
    if missing:
        print(f"MISSING {len(missing)}: {sorted(missing)[:5]}")
    if extra:
        print(f"UNEXPECTED {len(extra)}: {sorted(extra)[:5]}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        for cid in sorted(labels):
            fh.write(json.dumps(labels[cid], ensure_ascii=False) + "\n")
    print(f"wrote -> {args.out}")

    counts = Counter(r["verdict"] for r in labels.values())
    total = sum(counts.values())
    wrong = sum(n for v, n in counts.items() if v in WRONG)
    print(f"\n{'verdict':<26} {'n':>4}   share")
    for v, n in counts.most_common():
        print(f"{v:<26} {n:>4}   {100.0*n/total:5.1f}%")
    print(f"\nWRONG FLAG RATE: {wrong}/{total} = {100.0*wrong/total:.1f}%   (target <= 20%)")

    conf = Counter(r.get("confidence") for r in labels.values())
    print(f"judge confidence: {dict(conf)}")

    # --- inter-judge agreement on any double-labeled batch ---
    for rf in sorted(jd.glob("recheck_*.jsonl")):
        second = {r["id"]: r for r in read_jsonl(rf)}
        both = [c for c in second if c in labels]
        if not both:
            continue
        agree = sum(1 for c in both if second[c]["verdict"] == labels[c]["verdict"])
        print(f"\n--- agreement check ({rf.name}) ---")
        print(f"both labeled: {len(both)}   exact agreement: {agree} ({100.0*agree/len(both):.1f}%)")
        # The decision that actually matters is wrong-vs-fair, not the exact bucket.
        bin_agree = sum(1 for c in both
                        if (second[c]["verdict"] in WRONG) == (labels[c]["verdict"] in WRONG))
        print(f"agreement on WRONG-vs-FAIR: {bin_agree} ({100.0*bin_agree/len(both):.1f}%)")
        for c in both:
            if second[c]["verdict"] != labels[c]["verdict"]:
                print(f"  {c[:14]}: judge1={labels[c]['verdict']:<24} judge2={second[c]['verdict']}")


if __name__ == "__main__":
    main()
