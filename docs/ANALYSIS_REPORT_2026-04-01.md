# Analysis Report 2026-04-01

This historical report was superseded by the `NEW-UI` React migration.

The active architecture is now:

- React webapp in `webapp/`
- FastAPI backend in `backend/`
- Shared backend business logic in `lib/`, `audio_pipeline/`, `processing/`, and `analyzer/`
- Docker Compose service names: `webapp`, `backend`, `postgres`, and `redis`

Use `README.md`, `docs/ARCHITECTURE.md`, and `docs/DEPLOYMENT.md` for current guidance.
