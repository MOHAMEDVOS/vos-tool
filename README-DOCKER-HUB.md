# VOS Tool - Docker Hub Distribution Guide

This guide explains how to run VOS Tool using pre-built Docker images from Docker Hub, without needing to build from source.

## 📋 Prerequisites

Before you begin, ensure you have:

1. **Docker** (version 20.10+)
   - [Install Docker Desktop](https://www.docker.com/products/docker-desktop) for Windows/Mac
   - Or install Docker Engine for Linux

2. **Docker Compose** (version 2.0+)
   - Usually included with Docker Desktop
   - Verify: `docker-compose --version`

3. **PostgreSQL Database** (version 15+)
   - Local installation, or
   - Remote PostgreSQL server, or
   - Cloud PostgreSQL service (AWS RDS, Google Cloud SQL, Azure Database, etc.)

4. **AssemblyAI API Key** (optional but recommended)
   - Sign up at [AssemblyAI](https://www.assemblyai.com/)
   - Get your API key from the dashboard

## 🚀 Quick Start

### Step 1: Clone or Download Project Files

You need the following files from the repository:
- `docker-compose.example.yml` (rename to `docker-compose.yml`)
- `.env.example` (rename to `.env`)
- `cloud-migration/init.sql` (for database setup)

### Step 2: Set Up PostgreSQL Database

#### Option A: Local PostgreSQL

1. **Install PostgreSQL** (if not already installed):
   ```bash
   # Windows: Download from https://www.postgresql.org/download/windows/
   # macOS: brew install postgresql
   # Linux: sudo apt-get install postgresql
   ```

2. **Create Database and User**:
   ```sql
   -- Connect to PostgreSQL as superuser
   psql -U postgres
   
   -- Create database
   CREATE DATABASE vos_tool;
   
   -- Create user
   CREATE USER vos_user WITH PASSWORD 'your_secure_password';
   
   -- Grant privileges
   GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_user;
   
   -- Connect to vos_tool database
   \c vos_tool
   
   -- Run the schema initialization script
   \i cloud-migration/init.sql
   ```

#### Option B: Remote PostgreSQL

1. Ensure your PostgreSQL server is accessible
2. Create database and user (same as Option A)
3. Run the schema initialization script
4. Note the connection details (host, port, database, user, password)

### Step 3: Configure Environment Variables

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** with your configuration:

   ```env
   # Database Connection
   POSTGRES_HOST=host.docker.internal  # Use 'host.docker.internal' for local PostgreSQL
                                       # Or use your remote PostgreSQL host/IP
   POSTGRES_PORT=5432
   POSTGRES_DB=vos_tool
   POSTGRES_USER=vos_user
   POSTGRES_PASSWORD=your_secure_password  # Use the password you set in Step 2
   
   # Security Keys (IMPORTANT: Generate your own!)
   # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   SECRET_KEY=your_generated_secret_key_here
   JWT_SECRET=your_generated_jwt_secret_here
   
   # Frontend/Backend URLs
   FRONTEND_URL=http://localhost:8501
   BACKEND_URL=http://backend:8000
   
   # AssemblyAI (Optional but recommended)
   ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
   
   # ReadyMode (Optional - for call automation)
   READYMODE_USER=
   READYMODE_PASSWORD=
   
   # Redis (Optional)
   REDIS_PASSWORD=
   ```

   **⚠️ Security Note**: Never share your `.env` file or commit it to version control!

### Step 4: Configure Docker Compose

1. **Copy the example file**:
   ```bash
   cp docker-compose.example.yml docker-compose.yml
   ```

2. **Verify the image names** in `docker-compose.yml` match the Docker Hub repository:
   ```yaml
   services:
     backend:
       image: your-dockerhub-username/vos-backend:latest
     frontend:
       image: your-dockerhub-username/vos-frontend:latest
   ```

   Replace `your-dockerhub-username` with the actual Docker Hub username.

### Step 5: Pull and Run

1. **Pull the images**:
   ```bash
   docker-compose pull
   ```

2. **Start the services**:
   ```bash
   docker-compose up -d
   ```

3. **Check status**:
   ```bash
   docker-compose ps
   ```

4. **View logs** (if needed):
   ```bash
   docker-compose logs -f
   ```

### Step 6: Access the Application

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔧 Configuration Details

### Database Connection

The application connects to PostgreSQL using the credentials in your `.env` file.

**For Local PostgreSQL:**
- Use `POSTGRES_HOST=host.docker.internal` (Windows/Mac)
- Use `POSTGRES_HOST=172.17.0.1` (Linux, or use your host IP)

**For Remote PostgreSQL:**
- Use the actual hostname or IP address
- Ensure firewall rules allow connections from your Docker host
- Ensure PostgreSQL `pg_hba.conf` allows connections from your Docker network

### Port Configuration

Default ports:
- Frontend: `8501`
- Backend: `8000`
- Redis: `6379`

To change ports, modify the `ports` section in `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"  # Change host port to 8502
```

### Data Persistence

The application uses Docker volumes for data persistence:
- `recordings_data`: Audio files and recordings
- `dashboard_data`: Application data and user settings
- `chrome_sessions`: Browser session data
- `redis_data`: Redis cache data

These volumes persist even when containers are stopped.

## 🐛 Troubleshooting

### Issue: Cannot connect to database

**Symptoms**: Backend logs show connection errors

**Solutions**:
1. Verify PostgreSQL is running: `pg_isready` or check service status
2. Check database credentials in `.env` file
3. For local PostgreSQL, ensure `host.docker.internal` resolves correctly
4. Check PostgreSQL `pg_hba.conf` allows connections
5. Verify firewall rules allow port 5432

### Issue: Images not found

**Symptoms**: `Error: image not found` when running `docker-compose up`

**Solutions**:
1. Verify Docker Hub username is correct in `docker-compose.yml`
2. Check images exist on Docker Hub: https://hub.docker.com/r/your-username/vos-backend
3. Ensure you're logged into Docker: `docker login`
4. Try pulling manually: `docker pull your-username/vos-backend:latest`

### Issue: Frontend can't connect to backend

**Symptoms**: Frontend shows connection errors

**Solutions**:
1. Verify `BACKEND_URL` in `.env` is set to `http://backend:8000`
2. Check backend is running: `docker-compose ps`
3. Check backend logs: `docker-compose logs backend`
4. Verify network connectivity: `docker-compose exec frontend ping backend`

### Issue: Permission denied errors

**Symptoms**: Container fails to start or write files

**Solutions**:
1. On Linux, check Docker daemon has proper permissions
2. Verify volume mounts have correct permissions
3. Check SELinux/AppArmor settings if applicable

### Issue: Out of memory

**Symptoms**: Containers crash or become unresponsive

**Solutions**:
1. Increase Docker memory limit (Docker Desktop → Settings → Resources)
2. Recommended: At least 4GB RAM for Docker
3. Close other resource-intensive applications

## 📊 Health Checks

The containers include health checks. Check status:

```bash
# View health status
docker-compose ps

# Check specific service
docker inspect vos-backend | grep -A 10 Health
```

## 🔄 Updating Images

To update to the latest version:

```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose up -d
```

## 🗑️ Stopping and Cleaning Up

**Stop services**:
```bash
docker-compose stop
```

**Stop and remove containers** (keeps volumes):
```bash
docker-compose down
```

**Remove everything including volumes** (⚠️ deletes all data):
```bash
docker-compose down -v
```

## 📚 Additional Resources

- **Main README**: [README.md](README.md)
- **Docker Setup Guide**: [DOCKER_SETUP.md](DOCKER_SETUP.md)
- **Database Documentation**: [docs/DATABASE.md](docs/DATABASE.md)
- **API Documentation**: http://localhost:8000/docs (when running)

## 🆘 Support

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Review this guide's troubleshooting section
3. Check the main [README.md](README.md)
4. Contact the project maintainers

---

**Last Updated**: 2024 | **Version**: 1.0.0

