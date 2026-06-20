# VOS Architecture

Last updated: React cutover branch `NEW-UI`.

## Overview

VOS is a React + FastAPI application.

```text
Browser
  |
  v
React webapp (webapp/, nginx, port 3000)
  |
  | /api/*
  v
FastAPI backend (backend/, port 8000)
  |
  v
PostgreSQL / Redis / external AI services
```

## Major Subsystems

| Subsystem | Purpose |
| --- | --- |
| `webapp/` | React UI, typed API clients, dashboard views, admin/owner workflows |
| `backend/api/` | FastAPI route layer for auth, audio, dashboards, phrases, settings, quota, sharing, system, jobs |
| `backend/services/` | Thin service wrappers around core business logic |
| `lib/` | Existing core data managers, auth/session helpers, quota, settings, phrase learning |
| `audio_pipeline/` | Audio loading, channel splitting, quality detections, transcription orchestration |
| `analyzer/` | Exact, semantic, and LLM rebuttal detection |
| `automation/` | ReadyMode call download automation |

## Frontend

The React app uses:

- Vite + TypeScript
- React Router-style protected shell
- TanStack Query for API state and polling
- Zustand for auth/UI state
- Tailwind CSS 3 + project tokens
- nginx static serving with `/api` proxy to backend

Important pages:

- Audit: ReadyMode download and MP3 upload
- Actions: flagged call review queue
- Call Review: audio playback and flagged-call context
- Dashboard: agent, lite, and campaign dashboards
- Phrase Management: owner-only phrase review/repository/settings
- Settings: profile, users, quota, sharing, sessions, system health, app config

## Backend API

The backend exposes all UI-facing behavior through FastAPI. React must not import Python business logic directly.

Key routers:

- `/api/auth`
- `/api/audio`
- `/api/dashboard`
- `/api/readymode`
- `/api/settings`
- `/api/phrases`
- `/api/campaigns`
- `/api/quota`
- `/api/sharing`
- `/api/system`
- `/api/jobs`

## Deployment

Docker Compose runs:

- `backend` from `backend/Dockerfile`
- `webapp` from `webapp/Dockerfile`
- `redis`

PostgreSQL may be local, Railway-managed, or supplied through the configured database environment variables.

Default local URLs:

- Web app: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
