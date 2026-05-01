# VOS — Voice Observation System
> AI-Powered Call Center QA Automation for High-Performance Sales Teams.

VOS is a sophisticated, high-fidelity platform designed to automate Quality Assurance for real estate sales calls. By leveraging a multi-layered AI detection engine, VOS transcribes, analyzes, and scores thousands of calls in seconds, providing actionable insights that previously took hours of manual effort.

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg?style=flat&logo=react&logoColor=white)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Deployment-Docker-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com)

---

## 🧠 The 3-Layer Detection Engine
VOS doesn't just look for keywords. It understands the context of sales conversations through a proprietary three-layer pipeline:

1.  **Exact Match**: Lightning-fast identification of high-confidence rebuttal phrases.
2.  **Semantic Match**: Uses `Sentence Transformers` to identify conceptually similar objections even when the exact wording differs.
3.  **LLM Fallback**: Utilizes `Groq / Llama 3.1` for complex linguistic analysis of ambiguous interactions, ensuring 99% detection accuracy.

---

## ✨ Core Features

### 📡 ReadyMode Integration
*   **Automated Downloads**: Playwright-based automation logs into ReadyMode dialers to fetch recordings.
*   **Session Persistence**: Handles authentication and secure session management automatically.
*   **Intelligent Filtering**: Downloads calls based on duration, disposition, and campaign.

### 📊 Advanced Dashboards
*   **Real-time Analytics**: Monitor agent performance, rebuttal hit rates, and quality trends.
*   **Hierarchical Views**: Custom views for Owners (System-wide), Admins (Team-wide), and Auditors (Self-view).
*   **Quality Scoring**: Automated detection of "Late Hello", "Releasing", and "Agent-Only" calls.

### 🛡️ Secure Management
*   **Google OAuth**: Modern, secure authentication flow.
*   **Granular Quota System**: Hierarchical credit allocation (Owner → Admin → Auditor) to manage API costs.
*   **Secure Storage**: All credentials and API keys are encrypted at rest.

### 🎓 Phrase Learning System
*   **Auto-Learning**: The system automatically identifies new successful rebuttals from high-performing agents.
*   **Quality Tiers**: Phrases are scored and categorized into tiers (Premium, Standard, Lite) for precise detection.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Geist/Stitch Design |
| **Backend** | FastAPI, Python 3.11, Pydantic v2 |
| **Database** | PostgreSQL (Primary), Redis (Caching/Jobs) |
| **AI/ML** | AssemblyAI (Transcription), Sentence Transformers, Llama 3.1 (via Groq) |
| **Automation** | Playwright (Chromium) |
| **Infrastructure** | Docker, Celery (Background Tasks), Railway (Deployment) |

---

## 🚀 Quick Start

### 🐳 Using Docker (Recommended)
The fastest way to get VOS running is with Docker Compose:

```bash
docker compose up --build
```

Access the services:
*   **Frontend**: `http://localhost:3000`
*   **Backend API**: `http://localhost:8000`
*   **API Documentation**: `http://localhost:8000/docs`

### 💻 Local Development

**1. Backend Setup**
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

**2. Frontend Setup**
```bash
cd webapp
npm install
npm run dev
```

---

## 📂 Project Structure

```text
backend/          # FastAPI routers, auth, services, and Pydantic models
webapp/           # Modern React frontend (Vite + Tailwind)
lib/              # Core business logic: Quota, User, and Session Managers
analyzer/         # The 3-layer Rebuttal Detection engine
audio_pipeline/   # Transcription and audio processing workflows
automation/       # Playwright scripts for ReadyMode integration
migrations/       # Database schema and migration scripts
docs/             # Technical documentation and architecture diagrams
```

---

## 📝 Configuration
Copy `.env.example` to `.env` and configure your API keys:
*   `ASSEMBLYAI_API_KEY`: For call transcription.
*   `GROQ_API_KEY`: For LLM-powered semantic analysis.
*   `DATABASE_URL`: PostgreSQL connection string.
*   `GOOGLE_CLIENT_ID`: For OAuth authentication.

---

## ⚠️ Legacy Notice
The legacy Streamlit-based interface (`app.py`) has been sunset and is no longer maintained. Please use the modern React dashboard for all operations.

---
**VOS** — *Transforming voice data into operational intelligence.*
