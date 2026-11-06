# Manual audit: Wrong Dispo flags (2026-11-05)

I read every Heavy Audit call that the current local code flags as Wrong Dispo.
That includes the NYI fix, which isn't committed yet. There are 18 calls, read from
their transcripts with no audio. The judgments are mine, and nobody has listened to
the recordings.

| Verdict | Calls |
|---|---:|
| Fair flag | 13 |
| Unclear | 2 |
| Needs a rule from Mohamed | 1 |
| False flag | 2 |

After this audit, the two false-flag patterns were fixed in local code, which also
cleared `a6b401d1`. The DNC - Unknown rule below cleared `bd400744`. Replaying the
same stored calls now gives 14 flags: the 13 fair, and `fb6f2095`.

## False flags

**`52307091`, shown as "NYI instead of WN".** The owner confirmed owning the property
and said they weren't selling, so NYI is correct.

> Owner: No, I'm not. I don't plan on sellling it. And\
> Owner: I don't have any other property.

No literal phrase matched, so the ML check fired. "I don't have any other property"
reads like a denial of owning the property. The agent's question was about other
property, so this is not a wrong number.

**`1ee31405`, shown as "NYI instead of WN".** The person said they had the wrong
number, then talked like the owner, so NYI looks correct.

> Owner: got the wrong number.\
> Agent: ...You still own it, right?\
> Owner: Yeah, I already. I thought. I think I'd left to talk to your wife. I told
> her that we're. We're not interestted.

"I got the wrong number" means the speaker made the mistake. That's different from
"you got the wrong number", but the check treats them the same.

## Needs a rule

**`bd400744`, logged DNC - Unknown, shown as "DNC-Unk instead of DNC".**

> Owner: I don't own the property on Trotter Drive... Take me off your call list and
> never call me again.

The person isn't the owner, so DNC - Unknown looks right. The check only accepted
DNC - Decision Maker, which was an assumption from the first version of this flag.

Mohamed confirmed that DNC - Unknown is correct when a non-owner asks not to be
called, and the local code now accepts it.

## Unclear

**`fb6f2095`, shown as "NYI instead of WN".** The person said "No, you got the wrong
number", then answered the follow-ups as if the property might be theirs: "Yeah, it's
not for show" and "Not right now. No." The transcript looks garbled.

**`a6b401d1`, shown as "NYI instead of WN".** The person said "I think I put the wrong
number" and later "I'm a maintenance guy". The call looks like Wrong Number, but the
phrase that fired means the speaker's own mistake, so the flag is right for the wrong
reason. The false-flag fix for `1ee31405` would clear this one too.

## Fair flags

| Call | Shown as | Owner said |
|---|---|---|
| `b6d7f339` | NYI instead of DNC | "Please don't call me back." |
| `af64d45f` | WN instead of DNC | "Can you please remove my number?" |
| `e24310d7` | WN instead of DNC | "Can you please take me off the list?" |
| `0c2cb09d` | WN instead of DNC | "No, please don't call me again." |
| `95c9984c` | NYI instead of WN | "Oh, no, I'm not the owner of that" |
| `caf51ce3` | NYI instead of WN | "No, sir, you got the wrong number." |
| `f462b1fc` | NYI instead of Interested | "Sure. Let's selll it." |
| `a8193f60` | NYI instead of DNC | "No, Please take me off the list." |
| `b7642127` | NYI instead of WN | "I think you got the wrong number." |
| `0a6afe8d` | WN instead of DNC | "Take" / "me off your list." (split across two lines) |
| `fa3bd41b` | NYI instead of DNC | "please quit calling this number." |
| `688736dc` | NYI instead of DNC | "Stop calling me." |
| `51e4d8c2` | NYI instead of DNC | "you can quit calling... Take it off your list." |

`f462b1fc` is the weakest of these. The owner may have been sarcastic, and later said
money was all that mattered.

In `e24310d7`, `0c2cb09d` and `0a6afe8d` the person also denied owning the property.
The flag says the agent should have logged DNC, but the rule above decides which DNC
is correct.
