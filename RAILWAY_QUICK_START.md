# Railway Quick Start Guide

Quick reference for deploying VOS Tool to Railway.

## Prerequisites Checklist

- [ ] GitHub repository: `MOHAMEDVOS/vos-tool` (already done ✓)
- [ ] Railway account: https://railway.app
- [ ] Supabase account: https://supabase.com
- [ ] Supabase database created and schema initialized
- [ ] AssemblyAI API key

## Quick Deployment Steps

### 1. Supabase Setup (5 minutes)

1. Create project at https://supabase.com
2. Get connection details: Project Settings → Database
3. Initialize schema: SQL Editor → Run `cloud-migration/init.sql`
4. Note: Host, Port, Database, User, Password

### 2. Railway Setup (10 minutes)

1. **Create Project**:
   - Go to https://railway.app
   - New Project → Deploy from GitHub
   - Select: `MOHAMEDVOS/vos-tool`

2. **Create Backend Service**:
   - Add Service → GitHub Repo
   - Name: `vos-backend`
   - Railway auto-detects `backend/Dockerfile`

3. **Create Frontend Service**:
   - Add Service → GitHub Repo
   - Name: `vos-frontend`
   - Railway auto-detects `frontend/Dockerfile`

### 3. Environment Variables

**Backend Service Variables**:
```env
POSTGRES_HOST=db.xxxxx.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_supabase_password
SECRET_KEY=generate_with_python
JWT_SECRET=generate_with_python
ASSEMBLYAI_API_KEY=your_key
FRONTEND_URL=https://your-frontend.railway.app
CORS_ORIGINS=https://your-frontend.railway.app
```

**Frontend Service Variables**:
```env
BACKEND_URL=https://your-backend.railway.app
```

**Generate Secrets**:
```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Deploy

- Railway auto-deploys on push to `main` branch
- Or manually trigger: Service → Deployments → Redeploy

### 5. Get URLs

- Backend: Service → Settings → Domains
- Frontend: Service → Settings → Domains
- Update environment variables with actual URLs
- Redeploy services

## Common Commands

**View Logs**:
- Railway Dashboard → Service → Deployments → View Logs

**Check Health**:
```bash
curl https://your-backend.railway.app/health
```

**Test Frontend**:
- Open: `https://your-frontend.railway.app`

## Troubleshooting

**Service won't start**:
- Check logs for errors
- Verify environment variables are set
- Check Dockerfile builds successfully

**Database connection failed**:
- Verify Supabase connection details
- Check Supabase project is active
- Verify password is correct

**CORS errors**:
- Update `FRONTEND_URL` and `CORS_ORIGINS` with actual Railway URLs
- Redeploy backend service

## Full Documentation

See [RAILWAY_SUPABASE_DEPLOYMENT.md](RAILWAY_SUPABASE_DEPLOYMENT.md) for complete guide.

