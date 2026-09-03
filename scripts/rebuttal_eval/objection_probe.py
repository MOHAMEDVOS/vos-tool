"""Does an objection detector on the OWNER side agree with the human judges?

The judges recorded, per call, whether the owner actually objected (an `objection`
quote, or null). That is ground truth for the one question the codebase never asks:
was there anything to rebut at all?
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dialogue_utils import owner_text, parse_turns

# Owner-side objection cues. Deliberately NOT bare r'\bno\b' -- that is the
# existing bug in _extract_post_denial_agent_segments (rebuttal_detection.py:2385),
# which matches nearly every call and so gates nothing.
OBJECTION_PATTERNS = [
    # explicit refusals
    r"\bnot\s+interest", r"\bno\s+interest", r"\bnot\s+for\s+sale\b", r"\bnot\s+sell",
    r"\bdon'?t\s+want\s+to\s+sell", r"\bnot\s+available\b", r"\bnot\s+yet\b",
    # wrong person / wrong property
    r"\bwrong\s+number\b", r"\bdon'?t\s+own\b", r"\bnot\s+the\s+owner\b",
    r"\bi\s+rent\b", r"\brenting\b", r"\bi'?m\s+a\s+tenant\b",
    # do-not-contact
    r"\btake\s+me\s+off\b", r"\bremove\s+me\b", r"\bstop\s+calling\b",
    r"\bdo\s+not\s+call\b", r"\bdon'?t\s+call\b", r"\bleave\s+me\s+alone\b",
    r"\bharass", r"\bsue\b", r"\blawyer\b",
    # brush-offs
    r"\bnot\s+right\s+now\b", r"\bi'?m\s+busy\b", r"\bdon'?t\s+have\s+time\b",
    r"\bnot\s+planning\b", r"\bno\s+plans?\b", r"\bwe'?re\s+good\b", r"\bnever\b",
    # short negative replies. Punctuation-tolerant: "No, thank you" / "No. I'm not"
    # must match. A BARE \bno\b is still excluded -- that is the existing bug at
    # rebuttal_detection.py:2385, where it matches nearly every call and gates nothing.
    r"\bno\b[\s,.!]+thanks?\b", r"\bno\b[\s,.!]+thank\s+you\b",
    r"\bnope\b", r"\bnah\b",
    r"\bno\b[\s,.!]+i'?m\s+not\b", r"\bno\b[\s,.!]+it\s+is\s?n'?t\b",
    r"\bno\b[\s,.!]+it'?s\s+not\b", r"\bno\b[\s,.!]+we\s+are\s+not\b",
    r"\bno\b[\s,.!]+i\s+don'?t\b", r"\bno\b[\s,.!]+i\s+am\s+not\b",
    # repeated refusal ("no, no, no") is unambiguous even though bare "no" is not
    r"\bno\b[\s,.!]+no\b[\s,.!]+no\b",
]
COMPILED = [re.compile(p, re.I) for p in OBJECTION_PATTERNS]


def owner_objected(dialogue: str, label_style: str) -> tuple[bool, str | None]:
    """(objection_found, matched_cue). Only looks at what the OWNER said."""
    if label_style in ("channel", "named", "letter"):
        text = owner_text(dialogue)
    else:
        # No speaker structure -- we cannot attribute. Caller decides what to do.
        return (None, None)
    if not text.strip():
        return (False, None)
    for pat in COMPILED:
        m = pat.search(text)
        if m:
            return (True, m.group(0))
    return (False, None)


def main():
    labels = {json.loads(l)["id"]: json.loads(l)
              for l in Path("eval_data/labeled.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    sample = {json.loads(l)["id"]: json.loads(l)
              for l in Path("eval_data/sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

    tp = fp = tn = fn = unknown = 0
    fp_ex, fn_ex = [], []
    for cid, lab in labels.items():
        s = sample[cid]
        truth = lab.get("objection") not in (None, "", "null")
        pred, cue = owner_objected(s["dialogue"] or "", s["label_style"])
        if pred is None:
            unknown += 1
            continue
        if pred and truth: tp += 1
        elif pred and not truth:
            fp += 1
            if len(fp_ex) < 5: fp_ex.append((cid, cue, (owner_text(s['dialogue'])or'')[:70]))
        elif not pred and truth:
            fn += 1
            if len(fn_ex) < 5: fn_ex.append((cid, lab.get("objection"), (owner_text(s['dialogue'])or'')[:70]))
        else: tn += 1

    scored = tp + fp + tn + fn
    print(f"calls with usable speaker labels : {scored}")
    print(f"calls we cannot attribute        : {unknown}  (no speaker structure)")
    print()
    print(f"  objection correctly found   TP : {tp}")
    print(f"  correctly said no objection TN : {tn}")
    print(f"  claimed objection, none      FP: {fp}   <- would keep flagging unfairly")
    print(f"  missed a real objection      FN: {fn}   <- would stop flagging a fair case")
    if scored:
        print(f"\n  accuracy vs judges: {100.0*(tp+tn)/scored:.1f}%")
    if tp + fp:
        print(f"  precision: {100.0*tp/(tp+fp):.1f}%")
    if tp + fn:
        print(f"  recall   : {100.0*tp/(tp+fn):.1f}%")
    print("\nfalse positives (we say objection, judge says none):")
    for cid, cue, txt in fp_ex: print(f"   [{cue}] owner said: {txt!r}")
    print("\nfalse negatives (judge found objection, we missed it):")
    for cid, obj, txt in fn_ex: print(f"   judge: {str(obj)[:45]!r}\n     owner: {txt!r}")


if __name__ == "__main__":
    main()
