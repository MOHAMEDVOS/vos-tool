# Wrong Dispo: add a semantic (ML) matching layer

## Problem

`lib/wrong_dispo_detector.py` only catches a phrase if it's an exact (normalized)
substring of the transcript. A homeowner who says "I'd really rather you guys
didn't reach out again" means the same thing as "do not call me again," but
today that's a silent miss, not a flag — because it's not a literal match.

We don't want to keep growing the phrase lists forever to chase every possible
wording. The fix is to add a second pass that catches *paraphrases* of the
phrases we already trust, using the same kind of semantic matching VOS already
runs for rebuttal detection.

## What we already have (reuse, don't rebuild)

VOS already loads a sentence-embedding model for rebuttal detection
(`analyzer/rebuttal_detection.py`'s `SemanticDetectionEngine`):

- **Model**: `sentence-transformers/all-MiniLM-L6-v2`, loaded once as a
  process-wide singleton via `models/manager.py::get_semantic_model()`. By the
  time Wrong Dispo runs, rebuttal detection has usually already triggered this
  load for the same call, so there's no extra model load — just extra forward
  passes.
- **Matching method**: `sklearn.metrics.pairwise.cosine_similarity` between
  sentence embeddings and phrase embeddings, with a similarity threshold
  (rebuttal's default is 0.68, configurable via `persistent_app_settings`).
- **Sentence splitting**: `SemanticDetectionEngine._split_into_sentences()` —
  a small stdlib regex splitter, not worth importing (it's a method on a
  class that also pulls in `KeywordRepository` and a DB-backed LLM evaluator,
  which `wrong_dispo_detector.py` deliberately has none of — see module
  docstring: "No I/O, no dependencies beyond stdlib"). We write a standalone
  ~15-line version instead.

**Not reusing**: the rebuttal engine's `phrase_embeddings` dict — that's the
*rebuttal* phrase library embedded, a different set of phrases entirely.
Wrong Dispo needs its own embeddings, built from `DNC_PHRASES`,
`WRONG_NUMBER_PHRASES`, and `NYI_CONTRADICTION_PHRASES`.

**Not reusing**: the LLM (Groq) fallback tier the texting project and VOS's
own rebuttal detector both have. Mohamed asked specifically for ML/embeddings
here, not an LLM call per transcript — an LLM tier is a bigger, separate
decision (cost per call, latency, prompt design) and isn't in scope today.

## Design

### Two tiers, same as now plus one more

1. **Tier 1 (unchanged)**: the existing literal phrase match. If it fires,
   return "Yes" immediately — this is the trusted, zero-false-positive path,
   and stays exactly as-is.
2. **Tier 2 (new)**: only runs for a category where Tier 1 found nothing.
   Split the transcript into sentences, embed them, compare against that
   category's phrase embeddings, and flag "Yes" if the best match clears the
   similarity threshold.

### Threshold: stricter than rebuttal's

Rebuttal detection's 0.68 threshold is tuned for *recall* — a missed rebuttal
silently flags the agent as having given no rebuttal, so rebuttal detection
would rather over-match. Wrong Dispo is the opposite: a wrong semantic match
*is* the false positive we're trying to avoid. Default threshold: **0.80**,
override via `WRONG_DISPO_SEMANTIC_THRESHOLD` env var (clamped to
[0.65, 0.95], same clamping pattern rebuttal detection uses) so it can be
tuned from real misses without a code change.

### Kill switch

`WRONG_DISPO_SEMANTIC_ENABLED` env var, default `true` — same pattern as
rebuttal's `LLM_FALLBACK_ENABLED`. If the model singleton isn't loaded yet,
fails to load, or the flag is off, Tier 2 is skipped silently and Tier 1's
result stands. Never block or crash the call on a missing/slow model — a
missed semantic match is a silent miss, same acceptable failure mode as
today.

### What doesn't change

- `wrong_dispo_detection(transcript, disposition) -> "Yes"/"No"` — same
  signature, same return type, same call site in
  `audio_pipeline/audio_processor.py`. Zero changes anywhere else in the
  pipeline.
- The "DNC wins over Wrong Number" precedence and the three category scopes
  (DNC / Wrong Number / NYI-contradiction) stay exactly as widened on
  2026-11-04/05 — Tier 2 just gives each of those three categories a second
  chance to catch a paraphrase.

### New dependency surface

`wrong_dispo_detector.py` currently has zero third-party imports by design
(module docstring: "No I/O, no dependencies beyond stdlib"). This plan breaks
that — it will import `sentence_transformers`/`sklearn`/`numpy` (all already
project dependencies via rebuttal detection) and depend on the model
singleton being loadable. Worth flagging explicitly since it's a real
architecture change to a module that was written to avoid exactly this.

### Phrase embeddings: built once, cached in-process

Same singleton pattern as `models/manager.py`'s rebuttal embeddings: a
module-level global + `threading.Lock`, computed lazily on first call,
reused for the life of the process. ~70 short phrases total across the three
lists — encoding them is sub-second, not worth precomputing to a pickle file
the way rebuttal's `hardcoded_embeddings.pkl` is (that optimization exists
because rebuttal's phrase library is 2000+ phrases; ours is two orders of
magnitude smaller).

### Testing

The existing 18 tests are pure-stdlib and run instantly — don't make them
depend on a 80MB model download/load. Tier 2's matching function takes the
model/embeddings as parameters (not a hidden global lookup), so tests can
inject a small fake encoder (e.g. a hash-based fake embedding, or a couple of
precomputed real vectors checked into the test file) and verify the
threshold/precedence logic without loading the real model. One or two tests
can run against the real model as a slower, explicitly-marked integration
check, consistent with there being no existing precedent for real-model
tests in this repo (checked — rebuttal's semantic layer has none either).

## Not changing / out of scope

- No LLM (Groq) fallback tier — flagged above, separate decision.
- No change to Voicemail/Prank Voicemail — separate, shelved conversation
  (needs a behavioral signal, not a phrase list at all; see chat).
- No change to `SCORING_DISPOSITIONS` scoping — still Actions/Call Review
  only, per [[wrong-dispo-flag]].
- Threshold tuning against real transcripts happens after this ships, same
  as the original phrase lists — we don't have a labeled paraphrase dataset
  to tune against up front.

## Files

- `lib/wrong_dispo_detector.py` — add Tier 2, sentence splitter, phrase
  embedding cache. Stays the single file that owns this flag's logic.
- `tests/test_wrong_dispo_detector.py` — add Tier 2 tests with injected fake
  embeddings (fast) + one slow/real-model test.

## Risk

Medium — this is the first time this module touches an ML model, a real
architecture change (see "New dependency surface" above), not just a bigger
phrase list. The conservative threshold and Tier-1-first ordering keep the
existing zero-false-positive guarantee intact for every case Tier 1 already
covers; the new risk surface is entirely inside Tier 2's paraphrase catches,
which is also the entire point of building it.

## Status: built, threshold unresolved (2026-11-05)

Built as designed (Tier 1 unchanged, Tier 2 gated behind `_applicable` flags,
`WRONG_DISPO_SEMANTIC_ENABLED`/`WRONG_DISPO_SEMANTIC_THRESHOLD` env vars,
25/25 unit tests passing -- 18 Tier-1-only + 7 Tier-2, all against a fast
fake encoder except one real-model smoke test).

**But the 0.80 threshold this plan specified doesn't hold up against real
measurements.** Ran the actual `all-MiniLM-L6-v2` model against hand-written
paraphrases and found:

| category | real paraphrase | similarity |
|---|---|---|
| dnc | "I'd really rather you guys didn't reach out to me again." | 0.480 |
| dnc | "Can you take my number off whatever list this is." | 0.685 |
| wrong_number | "This isn't my property, you must be mistaken." | 0.797 |
| nyi | "Yeah I'd love to move forward with this." | 0.591 |

At 0.80, almost none of these clear the bar -- Tier 2 would rarely fire in
practice, which defeats the point of building it.

Lowering the threshold to actually catch these runs into the opposite
problem -- a **false-signal sentence scored higher than a true positive**:

| category | sentence | similarity | should flag? |
|---|---|---|---|
| wrong_number | "I'm the owner but my spouse handles this stuff." | 0.614 | **No** -- confirms ownership |
| wrong_number | "Sorry, I think you have the wrong guy." | 0.629 | Yes |

A threshold loose enough to catch the real "wrong guy" paraphrase (0.629) is
also loose enough to flag an owner who just confirmed they *are* the owner
(0.614) -- the exact false-positive this flag exists to prevent. There's no
single threshold in the measured range that cleanly separates true
paraphrases from false signals for short sentences on this model.

This isn't a tuning nitpick -- it means raw cosine similarity on
`all-MiniLM-L6-v2`, at this phrase-list size, isn't reliable enough on its
own to safely widen past Tier 1. Shipped with the threshold left at the
plan's original conservative 0.80 (so Tier 2 is live but very rarely fires,
and never less safe than Tier 1 alone) pending a decision on how to close
this gap. See [[wrong-dispo-flag]] for the options discussed.
