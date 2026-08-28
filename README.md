# VOS (Voice Observation System)

Call QA automation for Egyptian real estate sales teams. VOS pulls recordings from ReadyMode dialers, transcribes them, checks whether the agent answered the customer's objection, flags quality problems, and scores the audit.

Manual review of the same calls took about 45 seconds each.

## Rebuttal detection

A transcript goes through up to four stages, and each stage runs only if the one before it came back unsure. Most calls stop after the first two.

1. Exact phrase match against `rebuttal_phrases.txt` (roughly 3,200 phrases)
2. Regex patterns, applied only to what the agent says after the objection
3. Semantic match with sentence-transformers, for wording the phrase list misses
4. Groq (Llama 3.3 70B) evaluation when confidence is still below threshold

A match at 0.95 or higher ends the pipeline. See `docs/DETECTION_WORKFLOW.md`.

AssemblyAI handles transcription with speaker diarization. Before any matching runs, `lib/egyptian_accent_correction.py` repairs the transcription errors that Egyptian accents tend to produce.

## Everything else

- Downloads calls from ReadyMode over plain HTTP, no browser driver (`automation/readymode_http.py`)
- Flags late hello, releasing, agent-only, and long voicemail or dead calls
- Runs heavy audits (full scoring) and lite audits (campaign reachability and dispositions)
- Learns new rebuttal phrases from calls it already scored (`lib/phrase_learning.py`)
- Passes credit quotas down from owner to admin to auditor (`lib/quota_manager.py`)
- Exports agent scores in the company's Auditors-Scoring sheet format (`lib/scoring_audit.py`)

## Stack

FastAPI on Python 3.11 with Pydantic v2, PostgreSQL, and Celery on Redis for background jobs. Login is Google OAuth only, issuing a JWT.

The frontend is React 19 with Vite, TypeScript, and Tailwind, plus TanStack Query and Table, ag-grid, Recharts, and Zustand. It builds to static files served by nginx.

Both services run on Railway as Docker images. `nixpacks.toml` is there only to stop Railway from reaching for Nixpacks instead of the Dockerfiles.

## Running it

Bring your own PostgreSQL. The Compose file does not start one.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

```bash
cd webapp
npm install
npm run dev
```

Vite serves on port 3000 and proxies `/api` to the backend on 8000. API docs are at `http://localhost:8000/docs`.

`requirements.txt` is the full set. The backend image uses the smaller `requirements-backend.txt` and installs CPU-only PyTorch on its own.

## Configuration

Copy `.env.example` to `.env`. `env.template` has more variables and notes, though neither file is complete. What you need to set:

- `DATABASE_URL`, or the individual `POSTGRES_*` variables
- `SECRET_KEY` and `JWT_SECRET`
- `ASSEMBLYAI_API_KEY` for transcription
- `GROQ_API_KEY` for stage 4
- `GOOGLE_CLIENT_ID`, plus `VITE_GOOGLE_CLIENT_ID` in `webapp/.env`

On Railway these live in the Variables tab.

## Layout

```text
backend/          FastAPI app: routers, auth, Celery tasks, models
webapp/           React frontend
lib/              Data managers, quota, scoring, phrase learning, detectors
analyzer/         Rebuttal detection and the LLM evaluator
audio_pipeline/   Transcription and audio preprocessing
automation/       ReadyMode HTTP client
processing/       Batch and parallel call processing
migrations/       SQL schema changes
scripts/          One-off backfills and probes
tests/            Detector tests
docs/             See below
```

Start with `docs/ARCHITECTURE.md`. From there, `DETECTION_WORKFLOW.md` explains the four stages, `READYMODE_HTTP_SPEC.md` the dialer integration, `DEPLOYMENT.md` Railway, and `DATABASE.md` the schema. `IMPROVEMENTS.md` tracks known issues.
