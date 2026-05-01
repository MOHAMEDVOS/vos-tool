# Project Structure

```text
backend/          FastAPI API, auth, services, schemas, Dockerfile
webapp/           React + TypeScript + Vite frontend, nginx Dockerfile
lib/              Core business logic shared by backend services
analyzer/         Rebuttal detection and LLM evaluation
audio_pipeline/   Audio processing and detection helpers
automation/       ReadyMode download automation
processing/       Batch/audio orchestration
models/           Semantic model singleton management
cloud-migration/  PostgreSQL schema files
docs/             Project documentation
```

Retired:

- Streamlit `app.py`
- Python `frontend/` package
- Streamlit `ui/` helpers
- local utility `scripts/`
