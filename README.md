# VOS Tool - Voice Observation System

Advanced audio processing and analytics platform for call center quality assurance with automated transcription, rebuttal detection, and comprehensive audit capabilities.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](DOCKER_SETUP.md)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](requirements-production.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-teal)](backend/main.py)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)](app.py)

---

## 🚀 Quick Start (Docker - Recommended)

Get up and running in 3 steps:

# 1. Create environment file
# See DOCKER_SETUP.md for environment variable template
# Create .env file with your actual values

# 2. Build and start all services
docker-compose up --build

# 3. Access the application
# Frontend: http://localhost:8501
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**📖 For detailed Docker setup, see [DOCKER_SETUP.md](DOCKER_SETUP.md)**

---

## 📋 What is VOS Tool?

VOS Tool is an enterprise-grade voice analytics platform designed for call center quality assurance. It automatically transcribes calls, detects rebuttals, identifies quality issues (late hello, releasing), and provides comprehensive audit dashboards with role-based access control.

**Key Use Cases:**
- Automated call quality monitoring
- Rebuttal detection and analysis
- Agent performance tracking
- Campaign-level audit reporting
- User-isolated dashboard analytics

---

## ✨ Key Features

- **🎤 Cloud-Based Transcription** - AssemblyAI integration for accurate, fast transcription
- **🔍 Intelligent Rebuttal Detection** - Semantic matching with ML-powered analysis
- **⚡ Dual Audit Modes** - Heavy (comprehensive) and Lite (rapid screening)
- **👥 Role-Based Access Control** - Owner, Admin, and Auditor roles with granular permissions
- **🔒 User Data Isolation** - Complete dashboard isolation per user
- **📊 Comprehensive Analytics** - Agent-level, campaign-level, and lite audit dashboards
- **🎯 Quality Detection** - Late hello, releasing, and rebuttal detection
- **🌐 ReadyMode Integration** - Automated call download from ReadyMode dialers

---

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Frontend      │         │    Backend      │         │   PostgreSQL    │
│   (Streamlit)   │◄────────┤   (FastAPI)     │◄────────┤    Database      │
│   Port: 8501    │  HTTP   │   Port: 8000    │  SQL    │   Port: 5432    │
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

**Components:**
- **Frontend**: Streamlit-based web interface for user interaction
- **Backend**: FastAPI REST API for business logic and data processing
- **Database**: PostgreSQL for persistent data storage
- **External Services**: AssemblyAI (transcription), ReadyMode (call automation)

---

## 🚢 Deployment Options

### Option 1: Docker Hub (Easiest) ⭐⭐

**Best for:** Quick setup without building from source

Pull pre-built images from Docker Hub and run immediately:

```bash
# 1. Copy example files
cp docker-compose.example.yml docker-compose.yml
cp .env.example .env

# 2. Edit .env with your configuration
# 3. Set up PostgreSQL database (see DOCKER-HUB-SETUP.md)

# 4. Pull and run
docker-compose pull
docker-compose up -d
```

**Advantages:**
- ✅ No build time - instant startup
- ✅ Pre-optimized images
- ✅ Easy updates with `docker-compose pull`
- ✅ Consistent across all users

**📖 Full guide: [README-DOCKER-HUB.md](README-DOCKER-HUB.md)**

### Option 2: Docker Build from Source

**Best for:** Custom modifications or development

```bash
docker-compose up --build
```

**Advantages:**
- ✅ Isolated environment
- ✅ All dependencies included
- ✅ Easy scaling
- ✅ Consistent across machines

**📖 Full guide: [DOCKER_SETUP.md](DOCKER_SETUP.md)**

### Option 2: Local Development

**Best for:** Active development and debugging

#### Linux/macOS:
```bash
# Install dependencies
pip install -r requirements-production.txt

# Start both services (recommended)
./run_app.sh

# Or start individually:
./run_backend.sh  # Terminal 1
./run_frontend.sh # Terminal 2
```

#### Windows:
```bash
# Install dependencies
pip install -r requirements-production.txt

# Start both services (recommended)
run_app.bat

# Or start individually:
run_backend.bat  # Terminal 1
run_frontend.bat # Terminal 2
```

#### Manual Start:
```bash
# Install dependencies
pip install -r requirements-production.txt

# Start backend (Terminal 1)
cd backend
uvicorn main:app --reload --port 8000

# Start frontend (Terminal 2)
streamlit run app.py --server.port 8501
```

**📖 Full guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

---

## ⚙️ Configuration

### Essential Environment Variables

Create a `.env` file in the project root:

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_secure_password

# Security (Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# AssemblyAI (Required for transcription)
ASSEMBLYAI_API_KEY=your_assemblyai_api_key

# Timeout Configuration (Optional - for 30-60s files, system uses progressive timeouts)
# ASSEMBLYAI_TRANSCRIPTION_TIMEOUT=300
# ASSEMBLYAI_REBUTTAL_TIMEOUT_SECONDS=180
# PROCESSING_TIMEOUT_SINGLE_FILE=600

# ReadyMode (Optional - for call automation)
READYMODE_USER=your_username
READYMODE_PASSWORD=your_password
```

**📖 Complete environment variable list: [DOCKER_SETUP.md](DOCKER_SETUP.md#environment-variables)**

---

## 🎯 Features in Detail

### Rebuttal Detection
- **Semantic Matching**: Uses Sentence Transformers (all-MiniLM-L6-v2) with cosine similarity
- **Optimal Threshold**: 0.68 threshold minimizes false positives
- **Pattern Library**: 50+ common rebuttal phrases with contextual variations
- **Agent-Only Analysis**: Focuses on agent channel for accurate detection

### Audio Processing
- **Cloud Transcription**: AssemblyAI cloud-based transcription service
- **Audio Preprocessing**: Normalization, silence padding, sample rate conversion
- **Quality Detection**: Late hello detection (>5 seconds), releasing detection
- **Speaker Diarization**: Automatic speaker separation and identification

### Audit Modes

**Heavy Audit** (Comprehensive)
- Full transcription with accent correction
- Complete rebuttal analysis
- Detailed confidence scores
- **Processing Time**: ~3-5 minutes per minute of audio
- **Use Case**: Critical calls requiring detailed analysis

**Lite Audit** (Rapid Screening)
- Keyword spotting instead of full transcription
- Pattern matching for common rebuttals
- Basic quality metrics
- **Processing Time**: ~15-30 seconds per call
- **Use Case**: High-volume rapid screening

### User Management
- **Three Roles**: Owner (full access), Admin (limited management), Auditor (read-only)
- **Session Management**: Single concurrent session enforcement
- **Data Isolation**: Complete dashboard isolation per user
- **Security**: JWT-based authentication with 24-hour session expiration

---

## 👥 User Roles & Permissions

| Feature | Owner | Admin | Auditor |
|---------|-------|-------|---------|
| Settings Tab | ✅ | Limited | ❌ |
| User Management | Full | Create Auditors only | ❌ |
| Modify Users | ✅ | ❌ | ❌ |
| Delete Users | ✅ | ❌ | ❌ |
| End Sessions | ✅ | ❌ | ❌ |
| System Health | ✅ | ❌ | ❌ |
| App Configuration | ✅ | ❌ | ❌ |
| Dashboard Access | Personal | Personal | Personal |

**Default Role**: New users are assigned "Auditor" role by default.

---

## 📡 API Documentation

The backend provides a RESTful API with comprehensive documentation:

- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)

**Available Endpoints:**
- `/api/auth/*` - Authentication and session management
- `/api/audio/*` - Audio processing and transcription
- `/api/dashboard/*` - Dashboard data and analytics
- `/api/settings/*` - Application settings
- `/api/readymode/*` - ReadyMode integration

---

## 📁 Project Structure

```
vos-tool/
├── app.py                    # Frontend entry point (Streamlit)
├── config.py                 # Main configuration
├── backend/                  # Backend API (FastAPI)
│   ├── main.py              # Backend entry point
│   ├── api/                 # API routes
│   ├── core/                # Core functionality
│   ├── models/              # Data models
│   └── services/            # Business logic
├── frontend/                 # Frontend components
│   ├── app_ai/              # UI components and auth
│   └── api_client.py        # Backend API client
├── lib/                      # Core utilities
├── analyzer/                 # Rebuttal detection
├── audio_pipeline/          # Audio processing
├── processing/               # Batch processing
├── models/                   # ML model management
├── tools/                     # Utility scripts
├── static/                   # Static assets (CSS)
├── docker-compose.yml        # Docker orchestration
├── requirements-production.txt # Production dependencies
└── docs/                     # Documentation
```

---

## 🛠️ Development

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (or use Docker)
- AssemblyAI API key

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd vos-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-production.txt

# Set up environment variables
# See DOCKER_SETUP.md for environment variable template
# Create .env file with your values

# Start services
# See docs/DEPLOYMENT.md for detailed instructions
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests (if available)
pytest frontend/
```

**📖 Development guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

---

## 🔧 Troubleshooting

### Common Issues

**Backend won't start**
- ✅ Check database connection and credentials
- ✅ Verify environment variables are set
- ✅ Check logs: `docker-compose logs backend`

**Frontend can't connect to backend**
- ✅ Verify `BACKEND_URL` environment variable
- ✅ Check CORS configuration
- ✅ Ensure backend is running and healthy

**Database connection errors**
- ✅ Verify PostgreSQL is running
- ✅ Check database credentials in `.env`
- ✅ Ensure database schema is initialized

**Transcription not working**
- ✅ Verify `ASSEMBLYAI_API_KEY` is set correctly
- ✅ Check API key validity
- ✅ Review AssemblyAI account status

**📖 Detailed troubleshooting: [DOCKER_SETUP.md](DOCKER_SETUP.md#troubleshooting)**

---

## 📚 Documentation

- **[README-DOCKER-HUB.md](README-DOCKER-HUB.md)** - ⭐ Quick start with Docker Hub images
- **[DOCKER-HUB-SETUP.md](DOCKER-HUB-SETUP.md)** - Database setup for Docker Hub users
- **[DOCKER_SETUP.md](DOCKER_SETUP.md)** - Complete Docker build from source guide
- **[DOCKER_VALIDATION.md](DOCKER_VALIDATION.md)** - Docker optimization details
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment guide
- **[docs/DATABASE.md](docs/DATABASE.md)** - Database setup and schema
- **[docs/MIGRATION.md](docs/MIGRATION.md)** - Migration guides

---

## 🔒 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Session Management**: 24-hour expiration with single session enforcement
- **Data Isolation**: Complete user data separation
- **Role-Based Access**: Granular permission system
- **Encrypted Credentials**: Secure storage of ReadyMode credentials
- **CORS Protection**: Configurable cross-origin resource sharing

---

## 📊 Performance

- **Image Sizes**: 
  - Backend: ~800MB-1.2GB
  - Frontend: ~1GB-1.5GB
- **Processing Speed**:
  - Heavy Audit: ~3-5 min per minute of audio
  - Lite Audit: ~15-30 seconds per call
- **Concurrent Processing**: Supports batch processing with configurable limits

---

## 🤝 Contributing

This is a proprietary software project. For contributions or questions, please contact the project maintainers.

---

## 📄 License

Proprietary Software - All rights reserved

---

## 🆘 Support

For issues, questions, or support:
1. Check [DOCKER_SETUP.md](DOCKER_SETUP.md) for setup issues
2. Review [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for deployment questions
3. Check application logs for error details
4. Contact project maintainers

---

**Last Updated**: 2024 | **Version**: 1.0.0
