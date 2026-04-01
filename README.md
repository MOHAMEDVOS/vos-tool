<h1 align="center">
  🎙️ VOS Tool — Voice Observation System
</h1>

<p align="center">
  <strong>AI-powered call center QA automation for Egyptian real estate sales calls</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/AssemblyAI-000000?style=for-the-badge" alt="AssemblyAI">
  <img src="https://img.shields.io/badge/Groq-LLM-orange?style=for-the-badge" alt="Groq">
</p>

---

## What is VOS Tool?

VOS (Voice Observation System) automatically downloads call recordings from ReadyMode dialers, transcribes them using AssemblyAI, and analyzes agent performance using a 3-layer AI detection system. Manual analysis took 45 seconds per call — VOS does it in 2–3 seconds at $2–3 per 1,000 calls.

**What it does:**
- 🎤 Transcribes call audio via AssemblyAI
- 🧠 Detects sales rebuttals using 2,000+ phrase library + semantic matching + LLM fallback
- 📊 Flags quality issues: late hello, releasing, agent-only calls, silence
- 📈 Tracks agent performance over time across campaigns
- 🌐 Downloads calls automatically from ReadyMode dialers (8 instances)
- 🔒 Keeps each user's dashboard data fully isolated

---

## Key Features

| Feature | Description |
|---------|-------------|
| **3-Layer Rebuttal Detection** | Exact match → Semantic similarity → Groq LLM fallback |
| **2,000+ Phrase Library** | Domain-specific Egyptian real estate rebuttal phrases |
| **80% Early-Exit Rate** | Layer 1/2 resolves most calls, LLM only for edge cases |
| **Dual Audit Modes** | Full audit (transcription + AI) and Lite audit (fast keyword scan) |
| **ReadyMode Integration** | Playwright automation to download MP3s from 8 dialer instances |
| **Role-Based Access** | Owner, Admin, User permission levels |
| **Campaign Dashboards** | Per-agent and campaign-level analytics with CSV export |
| **Self-Learning Phrases** | Auto-learns new rebuttal patterns from confirmed calls |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
│                    Streamlit UI (port 8501)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │  app.py      │ │  frontend/   │ │  backend/    │
  │  (Streamlit  │ │  (UI logic,  │ │  (FastAPI    │
  │   entry)     │ │   auth, CSS) │ │   REST API)  │
  │  3098 lines  │ │              │ │  port 8000   │
  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
         │                │                │
         ├────────────────┴────────────────┤
         ▼                                 ▼
  ┌──────────────┐                 ┌──────────────┐
  │    lib/      │                 │  automation/  │
  │  (Core       │                 │  (ReadyMode   │
  │   business   │                 │   Playwright  │
  │   logic)     │                 │   downloader) │
  └──────┬───────┘                 └──────┬───────┘
         │                                │
    ┌────┼────┬────────┐                  │
    ▼    ▼    ▼        ▼                  ▼
┌───────┐┌───────┐┌─────────┐     ┌──────────────┐
│audio_ ││analy- ││process- │     │  ReadyMode   │
│pipe-  ││zer/   ││ing/     │     │  Dialer      │
│line/  ││       ││(batch)  │     │  (External)  │
└───┬───┘└───┬───┘└────┬────┘     └──────────────┘
    │        │         │
    ▼        ▼         ▼
┌─────────────────────────────────────────┐
│           External Services             │
│  ┌───────────┐  ┌───────┐  ┌─────────┐ │
│  │AssemblyAI │  │ Groq  │  │ Railway │ │
│  │(Transcr.) │  │(LLM)  │  │(Postgre)│ │
│  └───────────┘  └───────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

---

## 3-Layer Rebuttal Detection

```
MP3 File → AssemblyAI Transcription
                    │
        ┌───────────▼────────────┐
        │  Layer 1: Exact Match  │  confidence = 1.00 → STOP
        │  2,000+ phrase library │  (saves ~40 seconds)
        └───────────┬────────────┘
                    │ no match
        ┌───────────▼────────────┐
        │  Layer 2: Semantic     │  confidence > 0.7 → STOP
        │  Sentence Transformers │  (~2–5 seconds)
        └───────────┬────────────┘
                    │ confidence ≤ 0.7
        ┌───────────▼────────────┐
        │  Layer 3: LLM          │  Groq / Llama 3.1
        │  20 rebuttal strategies│  edge cases only
        └────────────────────────┘
```

**Result:** 80% early-exit rate. Only ~20% of calls reach Layer 3 (LLM).  
**Cost:** $2–3 per 1,000 calls vs $15–20 naive approach.  
**Speed:** 2,500 calls in ~2.5 hours vs 12.5 hours without optimization.

---

## Audit Modes

| | Full Audit | Lite Audit |
|--|-----------|------------|
| **Approach** | Full transcription + 3-layer AI analysis | Fast keyword spotting + pattern matching |
| **Speed** | ~200 calls in 3 minutes | ~1,000 calls in 8 minutes |
| **Use Case** | Deep QA review, agent coaching | High-volume daily screening |

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/MOHAMEDVOS/vos-tool.git
cd vos-tool

# 2. Create environment file
cp .env.example .env
# Edit .env with your values

# 3. Build and start all services
docker-compose up --build

# 4. Access the application
# Frontend:    http://localhost:8501
# Backend API: http://localhost:8000
# API Docs:    http://localhost:8000/docs
```

📖 See [docs/guides/DOCKER_SETUP.md](docs/guides/DOCKER_SETUP.md) for full setup guide.

---

## Project Structure

```
vos-tool/
├── app.py                      # Streamlit entry point
├── config.py                   # Central configuration
├── backend/                    # FastAPI REST API (port 8000)
│   ├── api/                   # Auth, audio, dashboard, settings routes
│   ├── core/                  # JWT, DB pool, security
│   └── services/              # Business logic layer
├── frontend/                   # Streamlit UI components
│   ├── app_ai/auth/           # Login, session validation
│   └── app_ai/ui/             # Audit, dashboard, phrase management
├── analyzer/                   # AI analysis engine
│   ├── rebuttal_detection.py  # 3-layer detection + 2,000+ phrase library
│   └── llm_rebuttal_evaluator.py  # Groq LLM (20 rebuttal strategies)
├── audio_pipeline/            # Audio processing (load, split, detect, transcribe)
├── processing/                # Batch processing engine
├── lib/                       # Core business logic (28 modules)
├── automation/                # ReadyMode Playwright downloader
├── models/                    # ML model management (Sentence Transformers)
└── docs/                      # Architecture, guides, fixes
```

---

## User Roles

| Feature | Owner | Admin | User |
|---------|:-----:|:-----:|:----:|
| User management | ✅ Full | ✅ Limited | ❌ |
| Phrase management | ✅ | ❌ | ❌ |
| System health | ✅ | ❌ | ❌ |
| Quotas & limits | ✅ | ✅ | ❌ |
| Audit & dashboard | ✅ | ✅ | ✅ |

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/login` | Authenticate, returns JWT + session ID |
| `GET /api/auth/me` | Current user info |
| `POST /api/audio/upload` | Upload and process audio file |
| `GET /api/audio/status/{job_id}` | Background job status |
| `GET /api/dashboard/audits/agent` | Agent audit results |
| `GET /api/dashboard/audits/campaign` | Campaign audit results |
| `GET /api/settings` | App settings CRUD |
| `POST /api/readymode/download-calls` | Trigger ReadyMode download |
| `GET /api/health/database` | DB connection pool health |

Interactive docs: `http://localhost:8000/docs`

---

## External Services

| Service | Purpose |
|---------|---------|
| **AssemblyAI** | Speech-to-text transcription |
| **Groq / Llama 3.1** | LLM rebuttal evaluation (Layer 3 fallback) |
| **Railway PostgreSQL** | Database hosting |
| **Sentence Transformers** | Semantic similarity (all-MiniLM-L6-v2) |
| **ReadyMode** | Call center dialer (8 instances) |

---

## Deployment (Railway)

5 services on Railway:

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 8501 | Streamlit app |
| Backend | 8000 | FastAPI API |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Celery broker |
| Celery Worker | — | Background batch jobs |

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture reference |
| [docs/DETECTION_WORKFLOW.md](docs/DETECTION_WORKFLOW.md) | 3-layer detection explained |
| [docs/guides/DOCKER_SETUP.md](docs/guides/DOCKER_SETUP.md) | Docker setup guide |
| [docs/guides/RAILWAY_DEPLOYMENT.md](docs/guides/RAILWAY_DEPLOYMENT.md) | Railway deployment guide |

---

## License

Proprietary Software — All rights reserved.
