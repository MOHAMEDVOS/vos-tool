# Railway Setup Steps

## Services

Create these Railway services:

1. Backend
   - Dockerfile path: `backend/Dockerfile`
   - Port: `8000`

2. Webapp
   - Dockerfile path: `webapp/Dockerfile`
   - Port: `3000`

3. PostgreSQL

4. Redis, if background job queue features are enabled

## Required Environment

Backend:

```text
FRONTEND_URL=https://your-webapp-domain
SECRET_KEY=...
JWT_SECRET=...
DATABASE_URL=...
ASSEMBLYAI_API_KEY=...
```

Webapp:

No secret environment variables are required. The nginx container serves React and proxies `/api` to the backend in Docker Compose. For Railway, configure routing/proxying according to the deployed domains, or set `VITE_BACKEND_URL` at build time if you do not use same-origin proxying.

## Removed Legacy Settings

Do not configure:

- `frontend/Dockerfile`
- `FRONTEND_PORT=8501`
- Streamlit health checks
- `_stcore` routes
