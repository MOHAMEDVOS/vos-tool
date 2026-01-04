# Setup Guide: Connect Docker to Existing PostgreSQL Database

## ✅ Completed Steps

1. ✅ Generated secure secret keys
2. ✅ Modified `docker-compose.yml` to connect to existing database
3. ✅ Created `.env.template` with all required configuration

## 📝 Final Step: Create .env File

Since `.env` files are protected for security, you need to create it manually:

### Option 1: Copy from Template (Recommended)

```bash
# Copy the template to .env
copy .env.template .env
```

### Option 2: Create Manually

Create a file named `.env` in the project root with this content:

```env
# ============================================
# Database Configuration
# ============================================
DB_TYPE=postgresql
# Railway: prefer DATABASE_URL (or PG* variables provided by Railway)
DATABASE_URL=
POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_SSLMODE=require

# ============================================
# Security Keys
# ============================================
SECRET_KEY=
JWT_SECRET=

# ============================================
# Backend Configuration
# ============================================
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=false
FRONTEND_URL=http://localhost:8501

# ============================================
# Frontend Configuration
# ============================================
FRONTEND_PORT=8501
BACKEND_URL=http://backend:8000

# ============================================
# AssemblyAI Configuration
# ============================================
ASSEMBLYAI_API_KEY=
ASSEMBLYAI_POLLING_INTERVAL=5
ASSEMBLYAI_RETRY_ATTEMPTS=3
ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION=true

# ============================================
# ReadyMode Configuration
# ============================================
FORCE_READYMODE=false
READYMODE_USER=
READYMODE_PASSWORD=

# ============================================
# Deployment Mode
# ============================================
DEPLOYMENT_MODE=enterprise

# ============================================
# Redis Configuration
# ============================================
REDIS_PORT=6379

# ============================================
# File Storage
# ============================================
UPLOAD_DIR=Recordings
MAX_UPLOAD_SIZE=52428800
```

## 🚀 Start Docker Services

Once the `.env` file is created:

```bash
# Build and start services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

## ✅ Verify Connection

### 1. Check PostgreSQL is Running

Make sure your PostgreSQL server in pgAdmin 4 is running and accessible on port 5432.

### 2. Test Database Connection from Docker

```bash
# Test backend can connect to database
docker exec vos-backend python -c "from lib.database import get_db_manager; db = get_db_manager(); print('✓ Connected!' if db and db.test_connection() else '✗ Failed')"
```

### 3. Check Service Health

```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:8501/_stcore/health
```

## Troubleshooting

### Issue: Cannot connect to database

**Solution**: Verify PostgreSQL is running and accessible.

### Issue: Backend won't start

**Check**:
- `.env` file exists and has all required variables
- PostgreSQL is running
- Port 5432 is not blocked by firewall
- Database credentials are correct

## What Changed

### docker-compose.yml Changes:
- Removed `postgres` service (using existing database)
- Updated database configuration to use environment variables
- Removed `depends_on: postgres` dependencies
- Removed `postgres_data` volume

### Database Connection:
- Configure your database connection using `DATABASE_URL` (recommended) or `POSTGRES_*` variables.

## Next Steps

1. Create `.env` file (copy from `.env.template`)
2. Ensure PostgreSQL is running in pgAdmin 4
3. Start Docker services: `docker-compose up --build -d`
4. Access application:
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

Your existing database with all users, ReadyMode credentials, and AssemblyAI API keys will be used automatically!

