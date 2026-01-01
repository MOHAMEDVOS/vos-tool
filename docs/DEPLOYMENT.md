# Deployment Guide - Phase 4

## Overview

This guide covers deployment configuration for the separated backend and frontend architecture.

## Environment Configuration

### Backend Environment Variables

Create `backend/.env` (or use `backend/.env.example` as template):

```env
# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=false

# Frontend (for CORS)
FRONTEND_URL=http://localhost:8501

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=your-secret-key-here
JWT_SECRET=your-jwt-secret-here

# Database
DB_TYPE=postgresql
POSTGRES_HOST=postgres
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your-password

# File Storage
UPLOAD_DIR=Recordings
MAX_UPLOAD_SIZE=52428800

# ReadyMode (optional)
FORCE_READYMODE=true
READYMODE_USER=your-username
READYMODE_PASSWORD=your-password
```

### Frontend Environment Variables

Create `frontend/.env` (or use `frontend/.env.example` as template):

```env
# Backend API
BACKEND_URL=http://localhost:8000

# Frontend
FRONTEND_PORT=8501
```

## Docker Deployment

### Quick Start

1. **Create environment files:**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   # Edit .env files with your values
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Check status:**
   ```bash
   docker-compose ps
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f frontend
   ```

### Services

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:8501
- **PostgreSQL**: localhost:5432
- **API Docs**: http://localhost:8000/docs

## Development Deployment

### Option 1: Docker Compose (Recommended)

```bash
docker-compose up
```

### Option 2: Manual (Development)

**Terminal 1 - Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
export BACKEND_URL=http://localhost:8000
streamlit run app.py --server.port 8501
```

**Terminal 3 - Database (if not using Docker):**
```bash
# Start PostgreSQL
# Or use existing database
```

### Option 3: Using Batch Scripts (Windows)

```batch
run_app.bat
```

## Production Deployment

### 1. Environment Setup

Create production `.env` files with secure values:
- Generate strong `SECRET_KEY` and `JWT_SECRET`
- Use secure database passwords
- Set `DEBUG=false`
- Configure proper `FRONTEND_URL`

### 2. Build Images

```bash
docker-compose build
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Verify Deployment

- Backend health: `curl http://localhost:8000/health`
- Frontend: Visit http://localhost:8501
- API docs: http://localhost:8000/docs

## Configuration Files

### Backend Configuration

- `backend/core/config.py` - Backend settings
- `backend/.env` - Environment variables
- `backend/requirements.txt` - Python dependencies

### Frontend Configuration

- `frontend/.env` - Environment variables
- `frontend/requirements.txt` - Python dependencies
- `app.py` - Streamlit configuration

### Shared Configuration

- `config.py` - Shared settings
- `docker-compose.yml` - Docker orchestration

## CORS Configuration

CORS is configured in `backend/core/config.py`:

```python
CORS_ORIGINS: List[str] = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    os.getenv("FRONTEND_URL", "http://localhost:8501")
]
```

For production, update `FRONTEND_URL` in backend `.env`:
```env
FRONTEND_URL=https://your-domain.com
```

## File Storage

### Development
Files stored in local directories:
- `Recordings/` - Audio files
- `dashboard_data/` - Application data

### Production (Docker)
Files stored in Docker volumes:
- `recordings_data` - Audio files
- `user_data` - Application data
- `postgres_data` - Database

## Database Setup

### Automatic (Docker)
Database schema is automatically created from `cloud-migration/init.sql` on first startup.

### Manual
```bash
# Connect to database
psql -U vos_user -d vos_tool

# Run schema
\i cloud-migration/init.sql
```

## Health Checks

### Backend
```bash
curl http://localhost:8000/health
```

### Frontend
```bash
curl http://localhost:8501/_stcore/health
```

## Troubleshooting

### Backend won't start
- Check database connection
- Verify environment variables
- Check logs: `docker-compose logs backend`

### Frontend can't connect
- Verify `BACKEND_URL` in frontend `.env`
- Check CORS configuration in backend
- Ensure backend is running

### Database connection errors
- Verify PostgreSQL is running
- Check database credentials
- Ensure schema is initialized

## Security Checklist

- [ ] Change `SECRET_KEY` in production
- [ ] Change `JWT_SECRET` in production
- [ ] Use strong database passwords
- [ ] Configure proper CORS origins
- [ ] Enable HTTPS in production
- [ ] Set `DEBUG=false` in production
- [ ] Review file permissions
- [ ] Secure environment files

