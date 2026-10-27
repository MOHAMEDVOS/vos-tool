# Heavy Audit minimum duration: impact

## Current behavior

The normal Heavy Audit defaults to a 20-second minimum only when Duration Filter is `all`. The download layer also has a hard 5-second floor. Other duration filters set their own range: for example, `lt30` currently accepts calls from 5 to 30 seconds, while `30to60` accepts calls from 30 to 60 seconds. The Scoring page separately requests 20 seconds.

## Implemented behavior

The Agent Audit page has one minimum-duration-in-seconds input, defaulting to 20; duration presets are removed from that form. Agent Heavy Audit sends the value to the backend, which applies it as the lower bound. The comparison skips recordings only when their duration is below the cutoff, so a call exactly at the entered number qualifies. The existing presets remain for campaign audits. The Scoring flow still requests its own 20-second minimum.

## Expected impact

- Auditors can include shorter calls or focus on longer calls without changing code; default behavior remains 20 seconds for `all`.
- Lower minimums can increase eligible recordings, transcription work, analysis time, AssemblyAI usage, and daily download quota consumption. Very short calls may contain too little speech for intro, reason, or rebuttal scoring.
- Higher minimums can reduce eligible calls and audit coverage, especially on low-connectivity calls; fewer downloaded calls may mean fewer scored results.
- The request needs server-side validation (integer, bounded range) so malformed or extreme values cannot trigger unexpectedly large processing workloads.
- Campaign duration-filter behavior remains unchanged.
- The minimum must be enforced during recording-duration validation, not just in the UI, so all callers follow the same rule.

## Options considered

1. Make only the current Heavy Audit `all` default configurable. Smallest behavior change; other preset/custom duration filters retain their existing semantics.
2. Apply the minimum to every Heavy Audit duration selection. More consistent, but adds range-conflict behavior and may change current `lt30` results.
3. Replace the duration filter with explicit minimum and maximum inputs. Clearest long term, but changes more of the current form and request contract.

Chosen: agent-only minimum field, defaulting to 20, with the auditor's value taking precedence. Campaign presets remain available in the campaign audit form.
