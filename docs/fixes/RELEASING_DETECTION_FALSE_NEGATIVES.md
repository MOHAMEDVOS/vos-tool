# Releasing Detection — False Negative Investigation

**Symptom reported:** calls where the agent actually released (never spoke) are NOT being flagged `Releasing: Yes`.
**Status:** RESOLVED (2026-06-16, no commit yet) — root-caused against live production data and fixed in `audio_pipeline/detections.py`. See "Resolution" at the bottom.

## Where it lives

`audio_pipeline/detections.py:208` — `releasing_detection(agent_segment)`:

```python
def releasing_detection(agent_segment):
    agent_channel = extract_left_channel(agent_segment)
    call_duration_s = len(agent_channel) / 1000.0
    min_duration = app_settings.late_hello_time   # 5s

    if call_duration_s < min_duration:
        return "No"

    speech_segments = voice_activity_detection(
        agent_channel,
        energy_threshold=app_settings.vad_energy_threshold,   # 600
        min_speech_duration=app_settings.vad_min_speech_duration,  # 120ms
        use_adaptive=True
    )
    return "Yes" if len(speech_segments) == 0 else "No"
```

Confirmed: thresholds (`vad_energy_threshold=600`, `vad_min_speech_duration=120ms`, `late_hello_time=5s`) are unchanged since the file's initial commit — no recent regression in this file or in `config.py` defaults. Same `extract_left_channel` = agent assumption is used consistently everywhere (`detections.py`, `audio_processor.py`, `fast_audio_processor.py`, `agent_only_detector.py`).

## Why false negatives happen — ranked by likelihood

### 1. All-or-nothing trigger is structurally fragile (most likely)
`releasing_detection` only returns `"Yes"` if **zero** speech segments are found across the **entire call**. Any single false-positive blip — line static, a hold tone, a customer's voice bleeding faintly into the agent's channel (imperfect stereo separation at the dialer), a cough picked up by the agent's mic, a brief automated IVR tone before pickup — flips a genuinely-releasing call to `"No"`. There's no "speech must total at least X% of the call" allowance; one 120ms+ blip anywhere kills the flag.

### 2. Silent fallback to a much more permissive VAD
`voice_activity_detection()` wraps its entire enhanced detection (energy + ZCR + spectral checks) in a blanket `try/except Exception` that falls back to `simple_energy_vad()` on **any** failure:

```python
except Exception:
    return simple_energy_vad(audio_segment, energy_threshold)
```

`simple_energy_vad` uses `pydub.silence.detect_nonsilent` with a fixed `-40 dBFS` threshold and **no** ZCR/spectral speech verification — quiet background hum/hiss on the agent's line easily counts as "non-silent" there. Because the except is bare and unlogged, there's currently no way to tell from logs whether a given call's "No" result came from the strict detector finding real speech, or from a silent fallback to the loose one. This is invisible in production today.

### 3. Unverified left-channel = agent assumption
Every detector (`extract_left_channel`, `agent_only_detector.py`) hardcodes "left channel = agent" with no runtime check and no documentation of which ReadyMode dialers/extensions this holds for. If even one dialer/line records channels swapped, every call from that source would have the **customer's** speech analyzed instead of the agent's — since customers are not silent, those calls would never register as `Releasing: Yes` regardless of what the agent actually did. This would be a systemic, source-specific pattern (e.g., one dialer's calls never flag, others do) rather than random misses, which is the way to tell it apart from #1/#2.

## How to confirm which one is firing (no code change needed)

`debug_audio_analysis()` already exists at `audio_pipeline/detections.py:262` and is wired into the heavy pipeline via `include_debug=True` (`audio_processor.py:443-448`). It reports `dbfs`, `rms_energy`, `speech_segments` (with timestamps), and `speech_percentage` for a given file. Run it against 2-3 calls you know were actually released (agent never spoke) to see exactly where/why a speech segment got detected — that will point to #1, #2, or #3 directly instead of guessing further.

## Possible fixes (not implemented — pick one after confirming root cause)

- **For #1:** require speech to exceed a minimum *total duration or percentage* of the call (not just "zero segments") before clearing the Releasing flag — e.g., `total_speech_duration_ms < 300` still counts as released.
- **For #2:** log a warning whenever the fallback VAD fires, and/or raise its silence threshold so it isn't drastically more permissive than the primary detector.
- **For #3:** add a one-time per-dialer validation pass (or a config flag) to confirm channel order, rather than assuming left=agent globally.

---

## Resolution (2026-06-16)

The user reported the issue started after migrating ReadyMode call downloads from Playwright to pure HTTP (`automation/readymode_http.py`, commit `7f489b1`, 2026-06-15). Investigated that angle first:

- **Download bytes are unchanged.** Both old (Playwright-scraped `<a href>`) and new (`RecId` + `?force_dl=1`) code paths fetch via plain `requests.get()` on the same URL pattern. Live-downloaded a real sample (5 calls on `resva`, 35 on dead-call/unknown dispositions across 6 dialers, 72 on the real unfiltered default) — every file came back as a proper 2-channel 8kHz stereo MP3, byte-exact to its `Content-Length` header. No corruption, no mono mixdown, no wrong-channel content.
- **Default disposition-type population is also very likely unchanged.** The new client's `DEFAULT_TYPES` (used whenever no disposition filter is selected — the common case, since the UI defaults to an empty selection) was reverse-engineered directly from a HAR capture of the same "Auditing AI" account's browser session with nothing manually filtered. The old Playwright code also never touched the disposition checkboxes when no filter was given, so both should be sending the server the same implicit default.
- Conclusion: **no migration-specific cause was found.** The actual bug is structural and predates the HTTP migration — confirmed via git history that the relevant logic in `detections.py` has been unchanged since the initial commit.

### What was actually live-tested and found (against real ReadyMode recordings)

Two concrete, reproducible bugs in `releasing_detection()`:

1. **Hard 5-second cutoff returned `"No"` unconditionally**, even for calls with 0% detected speech. Confirmed multiple real "Voicemail"/"Dead Call" recordings as short as 1.5–4.7s with `speech_segments_count=0` still scoring `"No"` because `call_duration_s < app_settings.late_hello_time (5s)` short-circuited before VAD ran.
2. **All-or-nothing trigger** (described above as hypothesis #1) — confirmed in production data: across 72 real default-filtered calls, ~22% had only 1-2 noise/static blips as short as 112ms total, which still flipped a near-silent call to `"No"`.

### Fix applied

`audio_pipeline/detections.py` — `releasing_detection()`:
- Removed the 5-second early-return; VAD now runs regardless of call length.
- Replaced the `len(speech_segments) == 0` all-or-nothing check with a total-speech-duration floor: `RELEASING_MIN_TOTAL_SPEECH_MS = 300`. A call only loses the Releasing flag if total detected speech across the whole call reaches 300ms.
- Re-validated against the same live data after the fix: previously-silent-but-short calls now correctly return `"Yes"` (3→6 in a 65-72 call sample), and the single-blip false negatives are resolved. No call with substantial real speech flipped to `"Yes"`.

No other module reimplements this logic — `optimized_audio_processor.py`, `fast_audio_processor.py`, `semantic_audio_processor.py`, and `audio_processor.py` all import `releasing_detection` from `detections.py`, so the fix applies everywhere automatically.

**Still open / not investigated further:** hypothesis #2 (silent fallback to the more permissive `simple_energy_vad`) and #3 (unverified left=agent channel assumption) from above — neither was needed to explain the confirmed false negatives, but could still be worth a logging pass if false negatives persist after this fix ships.
