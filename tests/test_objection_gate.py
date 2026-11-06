"""Unit tests for analyzer/objection_gate.py -- pure logic, no DB, no I/O."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from analyzer.objection_gate import evaluate


def _verdict(dialogue, disposition=None):
    return evaluate(dialogue, disposition)["verdict"]


# ── Wrong Number calls: the agent still has to ask about other property ──────

@pytest.mark.parametrize("dialogue", [
    # Bare "No" to a question with no sales keyword in it.
    "Agent: Hello, George?\nOwner: Yeah.\nAgent: I believe on a property at 1502. Is this right?\n"
    "Owner: No.\nAgent: You don't own a property?",
    # Denials the literal phrase list doesn't cover.
    "Agent: Your house at 12921 Kerry Dell Road.\nOwner: I don't have. I don't own a house.\n"
    "Agent: All right, thanks so much.",
    "Agent: This is Anna calling regarding the property.\nOwner: Wrong phone number.\nAgent: Okay.",
    "Agent: I believe you own a property on Skipjack Lane, right?\nOwner: No, we don't.",
    # Re-asking about the same property isn't a pivot.
    "Agent: I believe you own a property on Haven Circle, right?\nOwner: I don't know what you're talking about.\n"
    "Agent: I'm talking about the house on 964 North Haven Circle. Are you still the owner?",
    # The loose word-count rule used to call this an attempt.
    "Agent: Are you the owner?\nOwner: No, this isn't James.\n"
    "Agent: I'm sorry. I'm just trying to reach the owner of the property on Grant Avenue.",
    # The owner never denied anything, but the agent logged Wrong Number and moved on.
    "Agent: Hello?\nOwner: Hello? Who is this?\nAgent: Oh, ma'am, sorry. I must have the wrong number.",
])
def test_wrong_number_without_a_pivot_stays_flagged(dialogue):
    assert _verdict(dialogue, "Wrong Number") == "no_attempt"


@pytest.mark.parametrize("agent_line", [
    "Sorry. You have any houses that you want to sell, by any chance?",
    "Gotcha. So do you have another properties you might be considered sellling?",
    "Okay. Do you have any other property?",
    "You have any other one, sir?",
    "Do you know anyone who wants to sell?",
    "Do you happen to know the owner?",
    "Are there any properties you're looking to sell?",
    "Sorry for the inconvenience. Nothing you'd be open to sellling at all.",
    "I got you. So do you have.",
])
def test_wrong_number_with_a_pivot_counts_as_attempted(agent_line):
    dialogue = f"Agent: Is this your property?\nOwner: No, wrong number.\nAgent: {agent_line}"
    assert _verdict(dialogue, "Wrong Number") == "attempted"


@pytest.mark.parametrize("agent_line", [
    "Do you have any problems?",
    "Is this Mr. James, by any chance?",
    "Did you sell it?",
])
def test_wrong_number_near_miss_is_not_a_pivot(agent_line):
    dialogue = f"Agent: Is this your property?\nOwner: No, wrong number.\nAgent: {agent_line}"
    assert _verdict(dialogue, "Wrong Number") == "no_attempt"


def test_wrong_number_pivot_before_the_owner_speaks_does_not_count():
    dialogue = "Agent: Do you have any other property?\nOwner: Wrong number.\nAgent: Okay."
    assert _verdict(dialogue, "Wrong Number") == "no_attempt"


@pytest.mark.parametrize("dialogue", [
    "Agent: I was looking for Mrs. Freka.\nOwner: There's no one here by that name. Bye.",
    "Agent: Is this your property?\nOwner: Wrong number.\nOwner: Goodbye.",
])
def test_wrong_number_explicit_owner_close_is_exempt(dialogue):
    assert _verdict(dialogue, "Wrong Number") == "owner_ended_call"


@pytest.mark.parametrize("agent_line", [
    "Oh, I'm sorry, sir. Thank you.",
    "That's fine. Have a good one.",
])
def test_wrong_number_owner_bye_after_agent_gave_up_stays_flagged(agent_line):
    dialogue = f"Agent: Is this your property?\nOwner: No.\nAgent: {agent_line}\nOwner: Okay, bye."
    assert _verdict(dialogue, "Wrong Number") == "no_attempt"


@pytest.mark.parametrize("disposition", ["wrong number", "  Wrong  Number ", "WRONG NUMBER"])
def test_wrong_number_disposition_spelling_variants(disposition):
    assert _verdict("Agent: Is this right?\nOwner: No.\nAgent: Okay.", disposition) == "no_attempt"


def test_wrong_number_call_with_no_labels_stays_unparseable():
    assert _verdict("Hello, is this right? No. You don't own a property?", "Wrong Number") == "unparseable"


def test_wrong_number_call_with_empty_transcript_stays_unusable():
    assert _verdict("", "Wrong Number") == "unusable"


# ── Other dispositions: unchanged ────────────────────────────────────────────

BARE_NO = "Agent: Is this right?\nOwner: No.\nAgent: Okay."


@pytest.mark.parametrize("disposition", [None, "", "Decision Maker - NYI", "Wrong Number Called Back"])
def test_other_dispositions_keep_the_general_rules(disposition):
    assert _verdict(BARE_NO, disposition) == "no_objection"


def test_general_rules_still_detect_a_real_miss():
    dialogue = "Agent: Would you consider selling?\nOwner: No, not interested.\nAgent: Okay."
    assert _verdict(dialogue, "Decision Maker - NYI") == "no_attempt"


def test_general_rules_still_detect_an_attempt():
    dialogue = "Agent: Would you consider selling?\nOwner: Not interested.\nAgent: Not even down the road?"
    assert _verdict(dialogue, "Decision Maker - NYI") == "attempted"
