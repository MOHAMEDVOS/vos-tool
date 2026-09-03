"""Build a tiny synthetic sample so the harness can be verified without real data."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dialogue_utils import agent_text, label_style, parse_turns

CASES = [
    # (id, cohort, stored_verdict, dialogue, why_it_is_here)
    ("smoke-clear-rebuttal", "yes_control", "Yes",
     "Agent: Hi, I'm calling about your property on Maple Street.\n"
     "Owner: I'm not interested, it's not for sale.\n"
     "Agent: I completely understand. Do you have any other property you would consider selling?\n"
     "Owner: No I don't.\n"
     "Agent: No problem, thank you for your time.",
     "agent plainly rebuts after an objection"),

    ("smoke-owner-first-swap", "no", "No",
     "A: Hello?\n"
     "B: Hi, is this the owner of the house on Oak Avenue?\n"
     "A: Yes, but I'm not interested in selling.\n"
     "B: I hear you. Would you consider it even in the future, or do you have any other property?\n"
     "A: Not really.",
     "diarization put the CUSTOMER in slot A, so the agent's rebuttal sits under 'Owner'"),

    ("smoke-empty", "no", "No", "", "never analysed - timeout/exception recorded as No"),

    ("smoke-no-objection", "no", "No",
     "Agent: Hi, I'm calling about your property.\n"
     "Owner: Oh sure, I've actually been thinking about selling.\n"
     "Agent: That's great, let me take some details.\n"
     "Owner: Sounds good.",
     "customer never objected - there was no rebuttal to give"),

    ("smoke-genuine-miss", "no", "No",
     "Agent: Morning, calling about the property on Pine Road.\n"
     "Owner: We're not selling, we just refinanced.\n"
     "Agent: Understood. If the numbers were right and it was completely on your "
     "timeline, is that something you'd at least hear out?\n"
     "Owner: I mean, maybe, but not now.",
     "real paraphrased rebuttal, not in the phrase library"),

    ("smoke-agent-silent", "no", "No",
     "Agent: Hi, calling about your property.\n"
     "Owner: Not interested, take me off your list.\n"
     "Agent: Okay. Bye.",
     "genuine failure - agent gave up. This one SHOULD stay flagged."),
]

out = Path("eval_data/smoke_sample.jsonl")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8") as fh:
    for cid, cohort, verdict, dialogue, note in CASES:
        turns = parse_turns(dialogue)
        fh.write(json.dumps({
            "id": cid, "cohort": cohort, "stored_verdict": verdict,
            "agent_name": "SMOKE", "file_name": f"{cid}.mp3",
            "releasing": "No", "late_hello": "No",
            "call_duration": 60.0, "stored_confidence": None, "feedback": None,
            "dialogue": dialogue,
            "transcript_empty": not dialogue.strip(),
            "label_style": label_style(dialogue),
            "turn_count": len(turns),
            "agent_turns": sum(1 for s, _ in turns if s == "Agent"),
            "owner_turns": sum(1 for s, _ in turns if s == "Owner"),
            "first_speaker": turns[0][0] if turns else None,
            "agent_char_count": len(agent_text(dialogue)),
            "disposition": None, "dialer": None, "timestamp": None,
            "_note": note,
        }, ensure_ascii=False) + "\n")
print(f"wrote {len(CASES)} synthetic calls -> {out}")
