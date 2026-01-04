# Quick Start Guide - Using Docker Hub Images

This guide helps you quickly set up VOS Tool using pre-built Docker Hub images with your database configuration.

## 🚀 3-Step Setup

### Step 1: Download Configuration Files

Download these files to a folder on your PC:
- `docker-compose.example.yml` → Rename to `docker-compose.yml`
- `.env.example` → Rename to `.env`
- `cloud-migration/init.sql` (for database setup)

### Step 2: Configure Database in .env File

Open `.env` file and update **ONLY** these database settings:

```env
# ============================================================================
# UPDATE THESE DATABASE SETTINGS FOR YOUR PC
# ============================================================================

# For LOCAL PostgreSQL (on same machine):
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_database_password_here

# For REMOTE PostgreSQL (different server):
# POSTGRES_HOST=your-postgres-server-ip
# POSTGRES_PORT=5432
# POSTGRES_DB=vos_tool
# POSTGRES_USER=vos_user
# POSTGRES_PASSWORD=your_database_password_here
```

**That's it!** All other settings have sensible defaults.

### Step 3: Run the Application

```bash
# Pull images from Docker Hub
docker-compose pull

# Start the application
docker-compose up -d

# Check status
docker-compose ps
```

Access the app at: **http://localhost:8501**

---

## 📋 Database Setup (If Not Already Done)

If you don't have a PostgreSQL database yet:

### Option A: Use Existing PostgreSQL

1. Create database:
   ```sql
   CREATE DATABASE vos_tool;
   CREATE USER vos_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE vos_tool TO vos_user;
   ```

2. Run schema script:
   ```bash
   psql -U vos_user -d vos_tool -f cloud-migration/init.sql
   ```

3. Update `.env` with your credentials

### Option B: Add PostgreSQL to Docker Compose

Add this to your `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: vos-postgres
    environment:
      POSTGRES_DB: vos_tool
      POSTGRES_USER: vos_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./cloud-migration/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - vos-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vos_user -d vos_tool"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Then update `.env`:
```env
POSTGRES_HOST=postgres  # Use service name when PostgreSQL is in Docker
```

---

## 🔧 Common Database Configurations

### Local PostgreSQL (Windows/Mac)
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_password
```

### Local PostgreSQL (Linux)
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_password
```

### Remote PostgreSQL Server
```env
POSTGRES_HOST=192.168.1.100  # Your PostgreSQL server IP
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_password
```

### Cloud PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
```env
POSTGRES_HOST=your-db-instance.region.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=vos_tool
POSTGRES_USER=vos_user
POSTGRES_PASSWORD=your_password
```

---

## ✅ Verification

After starting, verify database connection:

```bash
# Check backend logs
docker-compose logs backend | grep -i "database\|connection"

# Should see: "Database connection established"
```

---

## 🆘 Troubleshooting

### "Cannot connect to database"

1. **Check PostgreSQL is running:**
   ```bash
   # Windows
   Get-Service postgresql*
   
   # Linux/Mac
   sudo systemctl status postgresql
   ```

2. **Verify credentials in `.env`** match your PostgreSQL setup

3. **Test connection manually:**
   ```bash
   psql -h localhost -U vos_user -d vos_tool
   ```

4. **Check firewall** allows port 5432

---

## 📝 Summary

**Minimum required changes in `.env`:**
- `POSTGRES_HOST` - Your PostgreSQL host
- `POSTGRES_PASSWORD` - Your database password
- `SECRET_KEY` - Generate a new one (optional but recommended)
- `JWT_SECRET` - Generate a new one (optional but recommended)

Everything else works with defaults!

