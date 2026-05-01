# Deployment

VOS deploys as a React webapp plus FastAPI backend.

## Local Docker

```bash
docker compose up --build
```

Open:

- Web app: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Services

| Service | Dockerfile | Port |
| --- | --- | --- |
| Backend | `backend/Dockerfile` | 8000 |
| Web app | `webapp/Dockerfile` | 3000 |
| Redis | `redis:7-alpine` | 6379 |

PostgreSQL can be local or supplied by Railway through the database environment variables.

## Frontend Routing

The webapp nginx container serves React static files and proxies `/api/*` to the backend service. For production domains, set either:

```text
FRONTEND_URL=https://your-webapp-domain
```

or:

```text
CORS_ORIGINS=https://your-webapp-domain
```

## Railway

Create separate services:

- Backend service with Dockerfile path `backend/Dockerfile`
- Webapp service with Dockerfile path `webapp/Dockerfile`
- PostgreSQL
- Redis if Celery/job queue features are enabled

Streamlit is no longer deployed. Do not configure `frontend/Dockerfile`, port `8501`, or `_stcore` health checks.
