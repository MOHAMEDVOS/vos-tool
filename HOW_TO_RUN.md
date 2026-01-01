# How to Run VOS Tool with Docker

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d
```

This starts all services in the background (detached mode).

### 2. View Logs (Optional)

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. Access the Application

Once services are running, open your web browser and go to:

- **Frontend UI**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Common Commands

### Start Services
```bash
# Start in background (recommended)
docker-compose up -d

# Start and see logs in real-time
docker-compose up
```

### Stop Services
```bash
# Stop services (keeps containers)
docker-compose stop

# Stop and remove containers
docker-compose down
```

### Restart Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### Check Status
```bash
# Check if services are running
docker-compose ps

# Check service health
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

### Rebuild After Code Changes
```bash
# Rebuild and restart
docker-compose up --build -d

# Rebuild specific service
docker-compose build backend
docker-compose up -d backend
```

## First Time Setup

If this is your first time running:

1. **Ensure PostgreSQL is running** in pgAdmin 4
2. **Verify .env file exists** with your database credentials
3. **Start services**:
   ```bash
   docker-compose up --build -d
   ```
4. **Wait for services to be healthy** (check with `docker-compose ps`)
5. **Access the application** at http://localhost:8501

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker-compose logs

# Check if ports are already in use
netstat -ano | findstr :8000
netstat -ano | findstr :8501
```

### Backend Can't Connect to Database

1. Verify PostgreSQL is running in pgAdmin 4
2. Check database credentials in `.env` file
3. Test connection:
   ```bash
   # From host machine
   psql -h localhost -U vos_tool -d vos_tool
   ```

### View Real-Time Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Restart Everything

```bash
# Stop and remove everything
docker-compose down

# Start fresh
docker-compose up --build -d
```

## Access Points

Once running, you can access:

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:8501 | Main application UI |
| Backend API | http://localhost:8000 | REST API endpoint |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| Health Check | http://localhost:8000/health | Service health status |

## Daily Usage

### Morning: Start Services
```bash
docker-compose up -d
```

### Check Status
```bash
docker-compose ps
```

### Access Application
Open browser: http://localhost:8501

### Evening: Stop Services (Optional)
```bash
docker-compose stop
```

Or leave them running - they'll auto-restart if the system reboots.

## Tips

- Services run in the background with `-d` flag
- Use `docker-compose logs -f` to monitor in real-time
- Press `Ctrl+C` to stop if running without `-d`
- Services automatically restart if they crash (restart: unless-stopped)
- Data persists in Docker volumes even if containers are removed

