"""Phase 3: attribute wrong flags to causes, and rank what to fix.

    .venv/bin/python scripts/rebuttal_eval/analyze.py
"""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

WRONG = {"wrong_agent_did_rebut", "wrong_no_objection", "unusable"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def bar(n, total, width=34):
    filled = int(round(width * n / total)) if total else 0
    return "█" * filled + "·" * (width - filled)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="eval_data/labeled.jsonl")
    ap.add_argument("--sample", default="eval_data/sample.jsonl")
    ap.add_argument("--replay", default="eval_data/replay_baseline.jsonl")
    ap.add_argument("--out", default="docs/REBUTTAL_FALSE_FLAGS.md")
    a = ap.parse_args()

    labels = {r["id"]: r for r in load(a.labels)}
    sample = {r["id"]: r for r in load(a.sample)}
    replay = {r["id"]: r for r in load(a.replay)}
    total = len(labels)
    wrong = [c for c, r in labels.items() if r["verdict"] in WRONG]
    counts = Counter(r["verdict"] for r in labels.values())

    L = []
    def w(s=""):
        L.append(s)
        print(s)

    w("# Why calls are wrongly flagged \"No Rebuttal\"")
    w()
    w(f"Sample: **{total}** calls that production flagged `No Rebuttal`, "
      f"pulled from the audit database and judged against the rule: *a flag is fair "
      f"only if the owner objected AND the agent made no attempt to overcome it.*")
    w()
    w(f"## Headline: {len(wrong)}/{total} flags are wrong = **{100.0*len(wrong)/total:.1f}%**")
    w()
    w("| verdict | n | share | |")
    w("|---|---:|---:|---|")
    for v, n in counts.most_common():
        tag = "WRONG" if v in WRONG else "fair"
        w(f"| `{v}` ({tag}) | {n} | {100.0*n/total:.1f}% | {bar(n,total)} |")
    w()

    # --- cause attribution ---
    w("## What each wrong flag is caused by")
    w()
    causes = Counter()
    for cid in wrong:
        v = labels[cid]["verdict"]
        s = sample.get(cid, {})
        if v == "unusable" or s.get("transcript_empty"):
            causes["transcript unusable / never analysed"] += 1
        elif v == "wrong_no_objection":
            causes["no objection occurred - flag logic, not detection"] += 1
        elif v == "wrong_agent_did_rebut":
            causes["real rebuttal the detector missed"] += 1
    for c, n in causes.most_common():
        w(f"- **{n}** ({100.0*n/len(wrong):.0f}% of wrong flags) — {c}")
    w()

    # --- structural context ---
    w("## Structural context")
    w()
    styles = Counter(sample[c]["label_style"] for c in labels if c in sample)
    w("Speaker-label format of the stored transcripts:")
    for s, n in styles.most_common():
        note = {"channel": "`Channel 1:/2:` - the objection gate cannot parse this",
                "none": "no speaker structure at all",
                "named": "`Agent:/Owner:` - the only format the gate understands",
                "letter": "`A:/B:`"}.get(s, "")
        w(f"- `{s}`: {n} ({100.0*n/total:.0f}%) — {note}")
    w()

    # --- missed rebuttals: what did the agent actually say? ---
    missed = [labels[c] for c in wrong if labels[c]["verdict"] == "wrong_agent_did_rebut"]
    if missed:
        w(f"## The {len(missed)} rebuttals the detector missed")
        w()
        w("What the agent actually said (these are the phrases detection needs to catch):")
        w()
        for r in missed[:22]:
            att = (r.get("agent_attempt") or "").strip().replace("\n", " ")
            if att:
                w(f"- \"{att[:118]}\"")
        w()

    # --- no-objection cases ---
    noobj = [c for c in wrong if labels[c]["verdict"] == "wrong_no_objection"]
    if noobj:
        w(f"## The {len(noobj)} calls where nothing was there to rebut")
        w()
        disp = Counter(sample[c].get("disposition") for c in noobj if c in sample)
        w("By dialer disposition:")
        for d, n in disp.most_common(8):
            w(f"- `{d}`: {n}")
        w()
        w("These are flagged by `rebuttal_issue = (Rebuttal Detection == 'No')` in "
          "`backend/services/dashboard_service.py:217`, which never checks whether the "
          "customer objected. No amount of detection tuning fixes them.")
        w()

    # --- ceiling analysis ---
    w("## What the fixes can actually achieve")
    w()
    fair = total - len(wrong)
    det_only = len([c for c in wrong if labels[c]["verdict"] == "wrong_agent_did_rebut"])
    rest = len(wrong) - det_only
    w(f"- Perfect detection (never miss a rebuttal) removes **{det_only}** wrong flags. "
      f"Remaining rate: {100.0*rest/(total-det_only):.1f}% — still above the 20% target.")
    w(f"- Also not flagging calls with no objection removes **{len(noobj)}** more. "
      f"Remaining: {100.0*(rest-len(noobj))/max(1,total-det_only-len(noobj)):.1f}%.")
    w()
    w("**Both changes are needed to reach 20%.** Detection tuning alone cannot get there.")
    w()

    conf = Counter(r.get("confidence") for r in labels.values())
    w(f"Judge confidence across labels: {dict(conf)}")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n\nwrote -> {a.out}")


if __name__ == "__main__":
    main()
