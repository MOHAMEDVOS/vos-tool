# Docker Setup

VOS now runs as:

- `backend`: FastAPI on port `8000`
- `webapp`: React/nginx on port `3000`
- `redis`: optional job/cache service

## Start

```bash
docker compose up --build
```

## Access

- Web app: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Environment

Set secrets in `.env` before production use:

```text
SECRET_KEY=...
JWT_SECRET=...
POSTGRES_PASSWORD=...
FRONTEND_URL=http://localhost:3000
```

The webapp container proxies `/api` to the backend service, so no browser-visible backend URL is required for Docker Compose.
