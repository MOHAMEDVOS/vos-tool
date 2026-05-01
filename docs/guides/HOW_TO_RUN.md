# How To Run VOS

## Docker

```bash
docker compose up --build
```

Open the app at `http://localhost:3000`.

Useful URLs:

- React webapp: `http://localhost:3000`
- FastAPI backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Frontend Development

```bash
cd webapp
npm ci
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and proxies `/api` to the backend.

## Backend Development

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Set database, JWT, ReadyMode, and AssemblyAI variables from `env.template`.

## Notes

Streamlit has been removed from the supported runtime. Do not run `streamlit run app.py`; use the React webapp instead.
