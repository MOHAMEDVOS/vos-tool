# Railway + Supabase Setup Checklist

Step-by-step checklist for deploying VOS Tool to Railway with Supabase.

## ✅ Phase 1: Supabase Setup

### Step 1.1: Create Supabase Project
- [x] Project created: `vos-tool`
- [x] Password set: `<your-password>`
- [x] Connection details obtained

### Step 1.2: Initialize Database Schema
- [ ] Open Supabase Dashboard → SQL Editor
- [ ] Click "New query"
- [ ] Open `cloud-migration/init.sql` from local project
- [ ] Copy entire contents
- [ ] Paste into SQL Editor
- [ ] Click "Run"
- [ ] Verify tables created (Table Editor)

**OR use PowerShell script:**
```powershell
.\scripts\init-supabase-schema.ps1 -SupabaseHost "<your-supabase-host>" -SupabaseUser "<your-db-user>" -SupabasePassword "<your-db-password>"
```

## ✅ Phase 2: Railway Project Setup

### Step 2.1: Create Railway Account
- [ ] Sign up/Login: https://railway.app
- [ ] Authorize GitHub access

### Step 2.2: Create Project
- [ ] New Project → Deploy from GitHub repo
- [ ] Select repository: `MOHAMEDVOS/vos-tool`
- [ ] Project name: `vos-tool`

### Step 2.3: Create Backend Service
- [ ] Add Service → GitHub Repo
- [ ] Service name: `vos-backend`
- [ ] Root directory: (leave empty)
- [ ] Railway auto-detects `backend/Dockerfile`

### Step 2.4: Create Frontend Service
- [ ] Add Service → GitHub Repo
- [ ] Service name: `vos-frontend`
- [ ] Root directory: (leave empty)
- [ ] Railway auto-detects `frontend/Dockerfile`

## ✅ Phase 3: Environment Variables

### Step 3.1: Generate Security Keys
- [ ] Run: `.\scripts\generate-railway-secrets.ps1`
- [ ] Copy `SECRET_KEY` and `JWT_SECRET`

### Step 3.2: Get AssemblyAI Key
- [ ] Open local `.env` file
- [ ] Copy `ASSEMBLYAI_API_KEY` value

### Step 3.3: Backend Service Variables
- [ ] Go to Backend Service → Variables tab
- [ ] Add all variables from `RAILWAY_ENV_VARIABLES.txt`
- [ ] Update `SECRET_KEY` (from Step 3.1)
- [ ] Update `JWT_SECRET` (from Step 3.1)
- [ ] Update `ASSEMBLYAI_API_KEY` (from Step 3.2)
- [ ] Keep `FRONTEND_URL` and `CORS_ORIGINS` as placeholders for now

### Step 3.4: Frontend Service Variables
- [ ] Go to Frontend Service → Variables tab
- [ ] Add `BACKEND_URL` (placeholder for now)
- [ ] Add `FRONTEND_PORT=8501`
- [ ] Add `TZ=America/New_York`

## ✅ Phase 4: Initial Deployment

### Step 4.1: Deploy Services
- [ ] Railway auto-deploys on variable save
- [ ] Or manually: Service → Deployments → Redeploy
- [ ] Wait for deployment to complete

### Step 4.2: Get Service URLs
- [ ] Backend Service → Settings → Domains
- [ ] Copy backend URL (e.g., `https://vos-backend-production.up.railway.app`)
- [ ] Frontend Service → Settings → Domains
- [ ] Copy frontend URL (e.g., `https://vos-frontend-production.up.railway.app`)

### Step 4.3: Update URLs in Environment Variables
- [ ] Backend Service → Variables
- [ ] Update `FRONTEND_URL` with actual frontend URL
- [ ] Update `CORS_ORIGINS` with actual frontend URL
- [ ] Frontend Service → Variables
- [ ] Update `BACKEND_URL` with actual backend URL
- [ ] Services auto-redeploy

## ✅ Phase 5: Verification

### Step 5.1: Verify Backend
- [ ] Check backend logs for "Database connection established"
- [ ] Test: `curl https://your-backend.railway.app/health`
- [ ] Should return: `{"status":"ok"}`

### Step 5.2: Verify Frontend
- [ ] Open frontend URL in browser
- [ ] Should load Streamlit interface
- [ ] Test login functionality

### Step 5.3: Verify Database Connection
- [ ] Login to application
- [ ] Check if data loads correctly
- [ ] Verify database queries work

## ✅ Phase 6: File Storage (Optional)

### Option A: Railway Volumes
- [ ] Backend Service → Volumes tab
- [ ] Create volume: `recordings-data`
- [ ] Mount path: `/app/Recordings`

### Option B: Supabase Storage (Future)
- [ ] Supabase → Storage
- [ ] Create bucket: `recordings`
- [ ] Update code to use Supabase Storage API

## 📝 Quick Reference

**Supabase Connection:**
```
Host: <your-supabase-host>
Port: 5432
Database: postgres
User: postgres
Password: <your-db-password>
```

**Environment Variables Template:**
- See `RAILWAY_ENV_VARIABLES.txt`

**Documentation:**
- Full guide: `RAILWAY_SUPABASE_DEPLOYMENT.md`
- Quick start: `RAILWAY_QUICK_START.md`

## 🆘 Troubleshooting

**Database connection failed:**
- Verify Supabase connection details
- Check Supabase project is active
- Verify password is correct

**Service won't start:**
- Check Railway logs
- Verify environment variables are set
- Check Dockerfile builds successfully

**CORS errors:**
- Update `FRONTEND_URL` and `CORS_ORIGINS` with actual URLs
- Redeploy backend service

