# Docker Quick Start Guide

## Prerequisites

- Docker and Docker Compose installed
- AssemblyAI API key (get from https://www.assemblyai.com/)

## 3-Step Setup

### Step 1: Create Environment File

Create a `.env` file in the project root:

```bash
# Required: Database Password
POSTGRES_PASSWORD=your_secure_password_here

# Required: Security Keys (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your_generated_secret_key
JWT_SECRET=your_generated_jwt_secret

# Required: AssemblyAI API Key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key

# Optional: ReadyMode (for automated call downloading)
FORCE_READYMODE=false
READYMODE_USER=your_username
READYMODE_PASSWORD=your_password
```

### Step 2: Start Services

```bash
docker-compose up --build -d
```

### Step 3: Access Application

- **Frontend UI**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Verify Everything Works

```bash
# Check all services are running
docker-compose ps

# Check logs
docker-compose logs -f

# Test backend health
curl http://localhost:8000/health
```

## Common Commands

```bash
# Stop services
docker-compose down

# View logs
docker-compose logs -f [service_name]

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose up --build -d
```

## Troubleshooting

**Backend won't start?**
- Check `.env` file exists and has all required variables
- Check logs: `docker-compose logs backend`
- Verify PostgreSQL is healthy: `docker-compose ps postgres`

**Frontend can't connect to backend?**
- Ensure `BACKEND_URL=http://backend:8000` in `.env` (for Docker)
- Check backend is running: `docker-compose ps backend`

**Database connection errors?**
- Verify `POSTGRES_PASSWORD` is set in `.env`
- Check PostgreSQL logs: `docker-compose logs postgres`
- Wait for PostgreSQL to be healthy before backend starts

For detailed information, see [DOCKER_SETUP.md](DOCKER_SETUP.md)

