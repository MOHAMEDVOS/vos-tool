# Railway Deployment

Deploy:

- Backend service from `backend/Dockerfile`
- Webapp service from `webapp/Dockerfile`
- PostgreSQL
- Redis if job queue features are enabled

Set backend `FRONTEND_URL` to the public webapp URL.
