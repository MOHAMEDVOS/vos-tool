# Docker Setup Guide for VOS Tool

## Quick Start

### 1. Create Environment File

Create a `.env` file in the project root with the following variables:

```bash
# Database
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user

# Security (Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# AssemblyAI (Required for transcription)
ASSEMBLYAI_API_KEY=your_assemblyai_api_key

# Backend/Frontend URLs
BACKEND_URL=http://backend:8000
FRONTEND_URL=http://localhost:8501

# Optional: ReadyMode
FORCE_READYMODE=false
READYMODE_USER=your_username
READYMODE_PASSWORD=your_password
```

### 2. Build and Start Services

```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Access the Application

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (if exposed)

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Frontend   │─────▶│   Backend   │─────▶│  PostgreSQL │
│ (Streamlit) │ HTTP │  (FastAPI)  │ SQL  │  Database   │
│  Port: 8501 │      │  Port: 8000 │      │  Port: 5432 │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Services

### Backend (FastAPI)
- **Container**: `vos-backend`
- **Port**: 8000
- **Health Check**: `GET /health`
- **Dependencies**: PostgreSQL (waits for healthy status)

### Frontend (Streamlit)
- **Container**: `vos-frontend`
- **Port**: 8501
- **Health Check**: Streamlit health endpoint
- **Dependencies**: Backend and PostgreSQL

### PostgreSQL
- **Container**: `vos-postgres`
- **Port**: 5432
- **Image**: postgres:15-alpine
- **Initialization**: Automatically runs `cloud-migration/init.sql` on first startup

### Redis (Optional)
- **Container**: `vos-redis`
- **Port**: 6379
- **Purpose**: Caching (currently optional, for future use)

## Volumes

Persistent data is stored in Docker volumes:

- `postgres_data`: Database files
- `recordings_data`: Audio recordings (`/app/Recordings`)
- `dashboard_data`: Dashboard JSON files and SQLite fallback (`/app/dashboard_data`)
- `chrome_sessions`: Chrome profile sessions for ReadyMode automation

### Managing Volumes

```bash
# List volumes
docker volume ls | grep vos

# Backup database
docker exec vos-postgres pg_dump -U vos_user vos_tool > backup.sql

# Remove all volumes (WARNING: Deletes all data!)
docker-compose down -v
```

## Database Connection

### How It Works

1. **Backend** connects to PostgreSQL using the service name `postgres`
2. Connection is established via Docker network `vos-network`
3. Database schema is automatically initialized from `cloud-migration/init.sql`
4. Connection pooling is handled by `lib/database.py` (1-10 connections)

### Environment Variables

```bash
DB_TYPE=postgresql
POSTGRES_HOST=postgres          # Docker service name
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=<from .env>
```

### Connection Verification

```bash
# Check backend can connect to database
docker exec vos-backend python -c "from lib.database import get_db_manager; db = get_db_manager(); print('Connected!' if db else 'Failed')"

# Check database directly
docker exec -it vos-postgres psql -U vos_user -d vos_tool -c "SELECT version();"
```

## Development vs Production

### Development
- Use `docker-compose up` (foreground) for live logs
- Mount local code for hot-reload (modify docker-compose.yml)
- Expose all ports for local access

### Production
- Use `docker-compose up -d` (detached)
- Use proper secrets management (not .env in production)
- Configure nginx reverse proxy (see `cloud-migration/nginx.conf`)
- Enable SSL/TLS certificates
- Set resource limits in docker-compose.yml

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Database not ready - wait for postgres health check
# 2. Missing environment variables - check .env file
# 3. Port conflict - change BACKEND_PORT in .env
```

### Frontend can't connect to backend

```bash
# Check BACKEND_URL in frontend container
docker exec vos-frontend env | grep BACKEND_URL

# Should be: BACKEND_URL=http://backend:8000 (not localhost!)
# Fix: Update .env file with correct BACKEND_URL
```

### Database connection errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection from backend
docker exec vos-backend python -c "from lib.database import get_db_manager; db = get_db_manager(); db.test_connection()"

# Verify credentials
docker exec -it vos-postgres psql -U vos_user -d vos_tool
```

### Port already in use

```bash
# Find process using port
# Linux/Mac:
lsof -i :8000
# Windows:
netstat -ano | findstr :8000

# Change port in .env:
BACKEND_PORT=8001
FRONTEND_PORT=8502
```

### Volume permissions

```bash
# Fix permissions for volumes
docker-compose down
docker volume rm vos-tool_recordings_data
docker-compose up -d
```

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL password | `secure_password_123` |
| `SECRET_KEY` | Application secret key | Generate with Python secrets |
| `JWT_SECRET` | JWT token secret | Generate with Python secrets |
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key | Get from assemblyai.com |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Database name | `vos_tool` |
| `POSTGRES_USER` | Database user | `vos_user` |
| `BACKEND_PORT` | Backend port | `8000` |
| `FRONTEND_PORT` | Frontend port | `8501` |
| `FORCE_READYMODE` | Enable ReadyMode | `false` |
| `DEBUG` | Debug mode | `false` |

## Building Individual Services

```bash
# Build only backend
docker-compose build backend

# Build only frontend
docker-compose build frontend

# Rebuild without cache
docker-compose build --no-cache
```

## Updating Services

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up --build -d

# Restart specific service
docker-compose restart backend
```

## Data Migration

If migrating from local installation:

1. **Export local data**:
   ```bash
   # Export PostgreSQL (if using local PostgreSQL)
   pg_dump -U vos_user vos_tool > backup.sql
   ```

2. **Import to Docker**:
   ```bash
   # Copy backup to container
   docker cp backup.sql vos-postgres:/tmp/
   
   # Import
   docker exec -i vos-postgres psql -U vos_user -d vos_tool < /tmp/backup.sql
   ```

3. **Copy JSON files** (if using SQLite fallback):
   ```bash
   # Copy dashboard_data to volume
   docker cp dashboard_data vos-frontend:/app/dashboard_data
   ```

## Security Best Practices

1. **Never commit `.env` file** - Use `.env.example` as template
2. **Use strong passwords** - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. **Limit exposed ports** - Only expose necessary ports
4. **Use secrets management** - In production, use Docker secrets or external vault
5. **Regular updates** - Keep base images updated
6. **Network isolation** - Services communicate via Docker network only

## Performance Tuning

### Resource Limits

Add to `docker-compose.yml` under each service:

```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2'
    reservations:
      memory: 2G
      cpus: '1'
```

### Database Optimization

```bash
# Increase shared_buffers (in postgres container)
docker exec -it vos-postgres psql -U vos_user -d vos_tool -c "ALTER SYSTEM SET shared_buffers = '256MB';"
docker-compose restart postgres
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f [service]`
2. Verify environment variables
3. Check service health: `docker-compose ps`
4. Review this documentation

