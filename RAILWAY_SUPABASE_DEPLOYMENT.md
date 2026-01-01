# Railway + Supabase Deployment Guide

Complete guide for deploying VOS Tool to Railway (hosting) and Supabase (database).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Phase 1: Supabase Database Setup](#phase-1-supabase-database-setup)
3. [Phase 2: Railway Project Setup](#phase-2-railway-project-setup)
4. [Phase 3: Environment Variables](#phase-3-environment-variables)
5. [Phase 4: File Storage Configuration](#phase-4-file-storage-configuration)
6. [Phase 5: Database Migration](#phase-5-database-migration)
7. [Phase 6: Deployment Verification](#phase-6-deployment-verification)
8. [Phase 7: Custom Domain (Optional)](#phase-7-custom-domain-optional)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- GitHub account with repository: `MOHAMEDVOS/vos-tool`
- Railway account: https://railway.app
- Supabase account: https://supabase.com
- AssemblyAI API key
- Domain name (optional, for custom domain)

---

## Phase 1: Supabase Database Setup

### Step 1.1: Create Supabase Project

1. **Sign up/Login to Supabase**: https://supabase.com
2. **Create New Project**:
   - Click "New Project"
   - Organization: Create or select existing
   - Name: `vos-tool` (or your preferred name)
   - Database Password: Set a **strong password** (save this!)
   - Region: Choose closest to your users
   - Pricing Plan: Free tier (500MB database, 2GB bandwidth) or Pro ($25/month)
   - Click "Create new project"

3. **Wait for Project Setup** (2-3 minutes)

### Step 1.2: Get Database Connection Details

1. **Go to Project Settings** → **Database**
2. **Note the connection details**:
   - Host: `db.xxxxx.supabase.co` (or similar)
   - Port: `5432`
   - Database: `postgres` (default)
   - User: `postgres` (default)
   - Password: The password you set during project creation

3. **Connection String Format**:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

### Step 1.3: Initialize Database Schema

**Option A: Using Supabase SQL Editor (Recommended)**

1. **Go to SQL Editor** in Supabase dashboard
2. **Click "New query"**
3. **Open** `cloud-migration/init.sql` from your local project
4. **Copy the entire contents** and paste into SQL Editor
5. **Click "Run"** (or press Ctrl+Enter)
6. **Verify tables created**: Go to "Table Editor" to see all tables

**Option B: Using psql from Local Machine**

```bash
# Connect to Supabase
psql "postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres"

# Run schema script
\i cloud-migration/init.sql
```

### Step 1.4: Create Application Database User (Optional but Recommended)

For better security, create a dedicated user instead of using `postgres`:

```sql
-- In Supabase SQL Editor
CREATE USER vos_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE postgres TO vos_user;
GRANT ALL ON SCHEMA public TO vos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vos_user;
```

**Update connection string**:
```
postgresql://vos_user:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

---

## Phase 2: Railway Project Setup

### Step 2.1: Create Railway Account and Project

1. **Sign up/Login to Railway**: https://railway.app
2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Authorize Railway to access your GitHub account
   - Select repository: `MOHAMEDVOS/vos-tool`
   - Project name: `vos-tool` (or your preferred name)

### Step 2.2: Create Backend Service

1. **Add Service** → **GitHub Repo**
2. **Service Name**: `vos-backend`
3. **Root Directory**: Leave empty (backend code is in root)
4. **Build Command**: Railway will auto-detect `backend/Dockerfile`
5. **Start Command**: Railway will use Dockerfile CMD

**Settings**:
- **Port**: Railway auto-detects from EXPOSE in Dockerfile (8000)
- **Health Check Path**: `/health`

### Step 2.3: Create Frontend Service

1. **Add Service** → **GitHub Repo**
2. **Service Name**: `vos-frontend`
3. **Root Directory**: Leave empty (frontend code is in root)
4. **Build Command**: Railway will auto-detect `frontend/Dockerfile`
5. **Start Command**: Railway will use Dockerfile CMD

**Settings**:
- **Port**: Railway auto-detects from EXPOSE in Dockerfile (8501)
- **Health Check Path**: `/_stcore/health`

---

## Phase 3: Environment Variables

### Step 3.1: Backend Service Environment Variables

In Railway, go to **Backend Service** → **Variables** tab, add:

```env
# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=false

# Frontend URL (will be Railway URL - update after frontend deploys)
FRONTEND_URL=https://your-frontend-service.railway.app

# CORS Origins (add Railway frontend URL)
CORS_ORIGINS=https://your-frontend-service.railway.app

# Security (Generate new secrets!)
SECRET_KEY=your-generated-secret-key-here
JWT_SECRET=your-generated-jwt-secret-here

# Database (Supabase)
DB_TYPE=postgresql
POSTGRES_HOST=db.xxxxx.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-supabase-password

# Connection Pool Settings
DB_POOL_MAX_SIZE=20
DB_CONNECT_TIMEOUT=30
DB_QUERY_TIMEOUT=60000

# File Storage
UPLOAD_DIR=/app/Recordings
MAX_UPLOAD_SIZE=52428800

# AssemblyAI
ASSEMBLYAI_API_KEY=your-assemblyai-api-key
ASSEMBLYAI_POLLING_INTERVAL=5
ASSEMBLYAI_RETRY_ATTEMPTS=3
ASSEMBLYAI_ENABLE_SPEAKER_DIARIZATION=true

# ReadyMode (Optional)
FORCE_READYMODE=false
READYMODE_USER=
READYMODE_PASSWORD=

# Timezone
TZ=America/New_York
```

**Important**: 
- Generate `SECRET_KEY` and `JWT_SECRET` using:
  ```python
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- Update `FRONTEND_URL` and `CORS_ORIGINS` after frontend service is deployed (get URL from Railway dashboard)

### Step 3.2: Frontend Service Environment Variables

In Railway, go to **Frontend Service** → **Variables** tab, add:

```env
# Backend URL (Railway backend service URL)
BACKEND_URL=https://your-backend-service.railway.app

# Frontend
FRONTEND_PORT=8501

# Timezone
TZ=America/New_York
```

**Important**: Update `BACKEND_URL` after backend service is deployed (get URL from Railway dashboard)

---

## Phase 4: File Storage Configuration

**Important**: Railway has **ephemeral storage** - files are lost when service restarts.

### Option A: Use Railway Volumes (Recommended for Small Files)

1. **Create Volume** in Railway:
   - Go to Backend Service → **Volumes** tab
   - Click "New Volume"
   - Name: `recordings-data`
   - Mount Path: `/app/Recordings`

2. **Environment Variables** (already set):
   ```env
   UPLOAD_DIR=/app/Recordings
   ```

**Limitations**: Volumes are per-service, not shared between backend/frontend.

### Option B: Use Supabase Storage (Recommended for Production)

1. **Go to Supabase** → **Storage**
2. **Create bucket**: `recordings`
3. **Set public or private** as needed
4. **Update code** to use Supabase Storage API (future enhancement)

---

## Phase 5: Database Migration

### Step 5.1: Backup Local Database (If Migrating)

```bash
# Backup local database
pg_dump -h localhost -U vos_user -d vos_tool -F c -f vos_tool_backup.dump
```

### Step 5.2: Migrate Data to Supabase

**Option A: Using pg_restore**

```bash
# Restore to Supabase
pg_restore -h db.xxxxx.supabase.co -U postgres -d postgres -c vos_tool_backup.dump
```

**Option B: Using Supabase Dashboard**

1. Go to **Database** → **Import/Export**
2. Upload SQL dump file
3. Follow import wizard

---

## Phase 6: Deployment Verification

### Step 6.1: Verify Backend Deployment

1. **Check Railway logs**: Backend Service → **Deployments** → **View Logs**
2. **Test health endpoint**:
   ```bash
   curl https://your-backend.railway.app/health
   ```
3. **Verify database connection**: Check logs for "Database connection established"

### Step 6.2: Verify Frontend Deployment

1. **Check Railway logs**: Frontend Service → **Deployments** → **View Logs**
2. **Open frontend URL** in browser: `https://your-frontend.railway.app`
3. **Test login functionality**

### Step 6.3: Update Environment Variables

After both services are deployed:

1. **Get service URLs** from Railway dashboard
2. **Update Backend Variables**:
   - `FRONTEND_URL`: Frontend service URL
   - `CORS_ORIGINS`: Frontend service URL
3. **Update Frontend Variables**:
   - `BACKEND_URL`: Backend service URL
4. **Redeploy services** (Railway auto-redeploys on variable changes)

---

## Phase 7: Custom Domain (Optional)

### Step 7.1: Add Custom Domain in Railway

1. **Go to Service** → **Settings** → **Domains**
2. **Add Custom Domain**
3. **Follow DNS instructions**:
   - Add CNAME record pointing to Railway domain
   - Wait for SSL certificate (automatic, ~5 minutes)

### Step 7.2: Update Environment Variables

After custom domain is active:
- Update `FRONTEND_URL` and `CORS_ORIGINS` with custom domain
- Update `BACKEND_URL` with custom domain (if using subdomain)
- Redeploy services

---

## Troubleshooting

### Issue: Database Connection Failed

**Symptoms**: Backend logs show connection errors

**Solutions**:
1. Verify Supabase connection string is correct
2. Check Supabase project is active
3. Verify firewall rules (Supabase allows all IPs by default)
4. Check connection pool settings (reduce if hitting limits)

### Issue: Service Won't Start

**Symptoms**: Railway deployment fails

**Solutions**:
1. Check Railway logs for errors
2. Verify environment variables are set
3. Check Dockerfile builds successfully
4. Verify port configuration matches Railway `$PORT`

### Issue: CORS Errors

**Symptoms**: Frontend can't connect to backend

**Solutions**:
1. Verify `FRONTEND_URL` matches actual frontend URL
2. Check `CORS_ORIGINS` includes frontend URL
3. Ensure backend allows frontend origin
4. Check both services are deployed and URLs are correct

### Issue: File Uploads Fail

**Symptoms**: File uploads don't work

**Solutions**:
1. Check volume is mounted (if using Railway volumes)
2. Verify `UPLOAD_DIR` path exists
3. Consider migrating to Supabase Storage for persistent storage

### Issue: 502 Bad Gateway

**Symptoms**: Service returns 502 error

**Solutions**:
1. Check service is running (Railway dashboard)
2. Verify health check endpoint works
3. Check service logs for errors
4. Verify port configuration

---

## Cost Estimation

### Railway
- **Free Tier**: $5 credit/month (500 hours)
- **Hobby Plan**: $5/month (512MB RAM, 1GB storage)
- **Pro Plan**: $20/month (8GB RAM, 100GB storage)

### Supabase
- **Free Tier**: 500MB database, 2GB bandwidth
- **Pro Plan**: $25/month (8GB database, 250GB bandwidth)

### Total Estimated Cost
- **Minimum**: $0/month (free tiers, limited usage)
- **Recommended**: $30-45/month (Railway Hobby + Supabase Pro)

---

## Next Steps

1. Set up custom domain (optional)
2. Configure automated backups in Supabase
3. Set up monitoring and alerts
4. Migrate file storage to Supabase Storage (if needed)
5. Configure CI/CD for automated deployments
6. Set up staging environment (optional)

---

## Support

- Railway Documentation: https://docs.railway.app
- Supabase Documentation: https://supabase.com/docs
- Project Repository: https://github.com/MOHAMEDVOS/vos-tool

---

**Last Updated**: 2025-01-01 | **Version**: 1.0.0

