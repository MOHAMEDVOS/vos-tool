# Railway Deployment Checklist

## ✅ Pre-Deployment

- [x] Supabase database initialized
- [x] All required tables created
- [x] Security keys generated
- [x] GitHub repository ready

## 🚂 Railway Setup

- [ ] Create Railway account
- [ ] Connect GitHub repository
- [ ] Create Backend Service
- [ ] Create Frontend Service

## ⚙️ Backend Configuration

- [ ] Add database environment variables:
  - [ ] `DB_TYPE=postgresql`
  - [ ] `POSTGRES_HOST=db.gwmgpzcftdtiuhuoolso.supabase.co`
  - [ ] `POSTGRES_PORT=5432`
  - [ ] `POSTGRES_DB=postgres`
  - [ ] `POSTGRES_USER=postgres`
  - [ ] `POSTGRES_PASSWORD=HX7!j@sB.mE3!cQ`
- [ ] Add security keys:
  - [ ] `SECRET_KEY=MO6Rl-IME9m2vhFv78-8F6wuMy91GRyA3rPqArfkXNM`
  - [ ] `JWT_SECRET=KIMLI_m3TlOcRd48ADMV7l4V4N_Y2yMqJLsz9vpMUW4`
- [ ] Add application settings:
  - [ ] `DEBUG=false`
  - [ ] `FRONTEND_URL` (update after deployment)
  - [ ] `CORS_ORIGINS` (update after deployment)
- [ ] Add other required variables:
  - [ ] `REDIS_URL=redis://redis:6379`
  - [ ] `TZ=America/New_York`

## 🎨 Frontend Configuration

- [ ] Add `BACKEND_URL` (update after backend deploys)
- [ ] Add `TZ=America/New_York`

## 🚀 Deployment

- [ ] Trigger initial deployment
- [ ] Wait for services to start
- [ ] Get backend URL from Railway
- [ ] Get frontend URL from Railway
- [ ] Update `FRONTEND_URL` in backend
- [ ] Update `CORS_ORIGINS` in backend
- [ ] Update `BACKEND_URL` in frontend
- [ ] Redeploy both services

## ✅ Verification

- [ ] Backend health check: `/health` endpoint
- [ ] Frontend loads correctly
- [ ] Can log in to application
- [ ] Database connection working
- [ ] All features functional

## 📝 Post-Deployment

- [ ] Test user creation
- [ ] Test audio processing
- [ ] Test phrase management
- [ ] Monitor logs for errors
- [ ] Set up custom domain (optional)

---

**Status:** Ready to deploy! 🚀

