<h1 align="center">
  🎙️ VOS Tool — Voice Observation System
</h1>

<p align="center">
  <strong>An AI system that audits call center audio, transcribes it, and detects rebuttals</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/AssemblyAI-000000?style=for-the-badge" alt="AssemblyAI">
</p>

---

## 📋 What is VOS Tool?

VOS Tool analyzes voice calls for quality assurance. It uses AssemblyAI to transcribe audio and NLP to check if agents properly used rebuttals. It also flags quality issues like "late hello" or releasing calls early.

**What it does:**
- 🔊 Transcribes audio files automatically
- 🔍 Detects rebuttals in agent speech
- 📈 Tracks agent performance over time
- 📊 Generates campaign audit reports
- 🔒 Keeps users' dashboard data isolated

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **🎤 Cloud Transcription** | Uses AssemblyAI for speech-to-text |
| **🧠 Rebuttal Detection** | Checks text against known rebuttals using Sentence Transformers |
| **⚡ Dual Audit Modes** | Heavy (full transcription) and Lite (quick keyword spotting) |
| **👥 Role-Based Access** | Owner, Admin, and Auditor permission levels |
| **🔒 Data Isolation** | Users only see their assigned data |
| **📊 Analytics Dashboards** | Filterable stats for agents and campaigns |
| **🎯 Quality Detection** | Flags late hellos and releasing |
| **🌐 ReadyMode Integration** | Pulls calls directly from ReadyMode dialers |

---

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Frontend      │         │    Backend      │         │   PostgreSQL    │
│   (Streamlit)   │◄────────┤   (FastAPI)     │◄────────┤    Database     │
│   Port: 8501    │  HTTP   │   Port: 8000    │  SQL    │   Port: 5432   │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                      │
                                      │ API Calls
                                      ▼
                            ┌─────────────────┐
                            │   AssemblyAI    │
                            │  (Transcription)│
                            └─────────────────┘
                                      │
                                      │ Automation
                                      ▼
                            ┌─────────────────┐
                            │    ReadyMode    │
                            │  (Call Download)│
                            └─────────────────┘
```

---

## 🚀 Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/MOHAMEDVOS/vos-tool.git
cd vos-tool

# 2. Create environment file (see .env.example)
cp .env.example .env
# Edit .env with your values

# 3. Build and start all services
docker-compose up --build

# 4. Access the application
# Frontend:    http://localhost:8501
# Backend API: http://localhost:8000
# API Docs:    http://localhost:8000/docs
```

📖 **For detailed setup, see [DOCKER_SETUP.md](DOCKER_SETUP.md)**

---

## 📁 Project Structure

```
vos-tool/
├── app.py                      # Frontend entry point (Streamlit)
├── config.py                   # Main configuration
├── backend/                    # Backend API (FastAPI)
│   ├── main.py                # Backend entry point
│   ├── api/                   # API routes
│   ├── core/                  # Core functionality
│   ├── models/                # Data models
│   └── services/              # Business logic
├── frontend/                   # Frontend components
│   ├── app_ai/                # UI components & auth
│   └── api_client.py          # Backend API client
├── analyzer/                   # Rebuttal detection engine
├── audio_pipeline/            # Audio processing pipeline
├── processing/                 # Batch processing
├── models/                     # ML model management
├── docker-compose.yml          # Docker orchestration
├── requirements-production.txt # Production dependencies
└── docs/                       # Documentation
```

---

## 👥 User Roles & Permissions

| Feature | Owner | Admin | Auditor |
|---------|:-----:|:-----:|:-------:|
| Settings | ✅ | Limited | ❌ |
| User Management | Full | Create Auditors | ❌ |
| Modify/Delete Users | ✅ | ❌ | ❌ |
| System Health | ✅ | ❌ | ❌ |
| Dashboard Access | Personal | Personal | Personal |

---

## 🔍 Rebuttal Detection

- **Semantic Matching** using Sentence Transformers (all-MiniLM-L6-v2) with cosine similarity
- **Optimal Threshold** of 0.68 minimizes false positives
- **Pattern Library** of 50+ common rebuttal phrases with contextual variations
- **Agent-Only Analysis** focuses on agent channel for accurate detection

---

## ⚡ Audit Modes

| | Heavy Audit | Lite Audit |
|--|------------|------------|
| **Approach** | Full transcription + accent correction | Keyword spotting + pattern matching |
| **Analysis** | Complete rebuttal analysis with confidence scores | Basic quality metrics |
| **Speed** | ~200 records in 3 minutes | ~1000 records in 8 minutes |
| **Use Case** | Critical calls requiring detail | High-volume rapid screening |

---

## 🔒 Security

- **JWT Authentication** with 24-hour session expiration
- **Single Session Enforcement** per user
- **Complete Data Isolation** between users
- **Encrypted Credentials** for external service integrations
- **CORS Protection** with configurable policies

---

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/auth/*` | Authentication & session management |
| `/api/audio/*` | Audio processing & transcription |
| `/api/dashboard/*` | Dashboard data & analytics |
| `/api/settings/*` | Application settings |
| `/api/readymode/*` | ReadyMode integration |

Interactive docs available at `http://localhost:8000/docs` (Swagger UI)

---

## 🛠️ Development

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (or use Docker)
- AssemblyAI API key

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-production.txt

# Start backend
cd backend && uvicorn main:app --reload --port 8000

# Start frontend (new terminal)
streamlit run app.py --server.port 8501
```

### Running Tests

```bash
cd backend && pytest
```

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [DOCKER_SETUP.md](DOCKER_SETUP.md) | Complete Docker build guide |
| [README-DOCKER-HUB.md](README-DOCKER-HUB.md) | Quick start with Docker Hub images |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deployment guide |

---

## 📄 License

Proprietary Software — All rights reserved.
