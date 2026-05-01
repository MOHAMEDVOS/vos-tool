# Environment Variables

Core variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `FRONTEND_URL` | React webapp URL for backend CORS | `http://localhost:3000` |
| `CORS_ORIGINS` | Optional comma-separated CORS allow list | unset |
| `SECRET_KEY` | App secret | required in production |
| `JWT_SECRET` | JWT signing secret | required in production |
| `DATABASE_URL` | PostgreSQL connection URL | optional if split vars are set |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | PostgreSQL database | `vos_tool` |
| `POSTGRES_USER` | PostgreSQL user | `vos_user` |
| `POSTGRES_PASSWORD` | PostgreSQL password | required |
| `ASSEMBLYAI_API_KEY` | Default AssemblyAI key | optional if user keys are set |
| `READYMODE_USER` | Optional global ReadyMode user | optional |
| `READYMODE_PASSWORD` | Optional global ReadyMode password | optional |

React local dev uses `webapp/.env` style variables when needed:

```text
VITE_BACKEND_URL=http://localhost:8000
```

For Docker Compose, leave `VITE_BACKEND_URL` unset because nginx proxies `/api` to the backend service.
