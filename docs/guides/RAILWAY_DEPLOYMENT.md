# Railway + Supabase Deployment Guide

## 🚀 Quick Start

This guide will help you deploy your VOS Tool to Railway with Supabase as the database.

---

## 📋 Prerequisites

- ✅ GitHub repository: `MOHAMEDVOS/vos-tool`
- ✅ Supabase database set up and initialized
- ✅ Railway account (sign up at https://railway.app)

---

## 🔑 Step 1: Security Keys

Generate security keys for your Railway environment variables:

```
SECRET_KEY=<generate-a-new-secret>
JWT_SECRET=<generate-a-new-secret>
```

**⚠️ IMPORTANT:** Save these keys securely. You'll need them for Railway environment variables.

---

## 🗄️ Step 2: Database Connection Details

Use your database provider connection information (recommended: Railway PostgreSQL).

```
DATABASE_URL=<from-railway-postgres-or-your-provider>
```

---

## 🚂 Step 3: Create Railway Project

1. **Go to Railway**: https://railway.app
2. **Sign up/Login** with your GitHub account
3. **New Project** → **Deploy from GitHub repo**
4. **Select repository**: `MOHAMEDVOS/vos-tool`
5. **Railway will auto-detect**:
   - `backend/Dockerfile` → Backend Service
   - `frontend/Dockerfile` → Frontend Service

---

## ⚙️ Step 4: Configure Backend Service

### 4.1 Add Environment Variables

Go to **Backend Service** → **Variables** tab and add:

#### Database Configuration
```
DB_TYPE=postgresql
DATABASE_URL=<from-railway-postgres-or-your-provider>
POSTGRES_SSLMODE=require
```

#### Security Keys
```
SECRET_KEY=<your-secret-key>
JWT_SECRET=<your-jwt-secret>
```

#### Application Settings
```
DEBUG=false
FRONTEND_URL=https://your-frontend-service.railway.app
CORS_ORIGINS=https://your-frontend-service.railway.app
```

#### Connection Pool Settings (Optional)
```
DB_POOL_MAX_SIZE=5
DB_CONNECT_TIMEOUT=10
DB_QUERY_TIMEOUT=30000
```

#### Other Required Variables
```
REDIS_URL=redis://redis:6379
TZ=America/New_York
```

**Note:** After deploying, Railway will assign a URL to your frontend service. Update `FRONTEND_URL` and `CORS_ORIGINS` with the actual frontend URL.

---

## 🎨 Step 5: Configure Frontend Service

Go to **Frontend Service** → **Variables** tab and add:

```
BACKEND_URL=https://your-backend-service.railway.app
TZ=America/New_York
```

**Note:** Replace `your-backend-service.railway.app` with the actual backend URL from Railway.

---

## 🔄 Step 6: Deploy

1. **Railway will auto-deploy** when you push to GitHub
2. **Or manually trigger** deployment:
   - Go to your service
   - Click **Deploy** → **Redeploy**

---

## ✅ Step 7: Verify Deployment

### Backend Health Check
Visit: `https://your-backend-service.railway.app/health`

Expected response:
```json
{"status": "healthy"}
```

### Frontend Access
Visit: `https://your-frontend-service.railway.app`

You should see the VOS Tool login page.

---

## 🔧 Step 8: Update URLs (After First Deploy)

After Railway assigns URLs to your services:

1. **Get Backend URL**: Backend Service → Settings → Domains
2. **Get Frontend URL**: Frontend Service → Settings → Domains
3. **Update Backend Variables**:
   - `FRONTEND_URL` = Your frontend URL
   - `CORS_ORIGINS` = Your frontend URL
4. **Update Frontend Variables**:
   - `BACKEND_URL` = Your backend URL
5. **Redeploy both services**

---

## 🐛 Troubleshooting

### Backend won't start
- Check environment variables are set correctly
- Verify Supabase connection details
- Check Railway logs: Service → Deployments → View Logs

### Frontend can't connect to backend
- Verify `BACKEND_URL` in frontend variables
- Check `CORS_ORIGINS` in backend variables includes frontend URL
- Ensure backend service is running

### Database connection errors
- Verify Supabase connection details
- Check Supabase dashboard → Settings → Database → Connection string
- Ensure Supabase allows connections from Railway IPs (should be automatic)

### Port errors
- Railway automatically sets `$PORT` environment variable
- Dockerfiles are configured to use `$PORT`
- No manual port configuration needed

---

## 📊 Monitoring

### View Logs
- **Backend**: Backend Service → Deployments → View Logs
- **Frontend**: Frontend Service → Deployments → View Logs

### Metrics
- Railway dashboard shows CPU, Memory, and Network usage
- Monitor connection pool usage in backend logs

---

## 🔐 Security Notes

1. **Never commit** `.env` files or secrets to GitHub
2. **Use Railway Variables** for all sensitive data
3. **Rotate keys** periodically (generate new `SECRET_KEY` and `JWT_SECRET`)
4. **Enable Railway's** built-in security features

---

## 📝 Next Steps

1. ✅ Deploy to Railway
2. ✅ Test login and basic functionality
3. ✅ Migrate existing data from local database (if needed)
4. ✅ Set up custom domains (optional)
5. ✅ Configure backups (Supabase handles this automatically)

---

## 🆘 Support

If you encounter issues:
1. Check Railway logs
2. Verify all environment variables
3. Test Supabase connection separately
4. Review this guide for common issues

---

**Good luck with your deployment! 🚀**

