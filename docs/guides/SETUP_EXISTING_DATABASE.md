# Setup Existing Database

Point the backend at an existing PostgreSQL database with either `DATABASE_URL` or the split `POSTGRES_*` variables.

Use:

```text
FRONTEND_URL=http://localhost:3000
```

The backend applies required schema files from `cloud-migration/` during startup.
