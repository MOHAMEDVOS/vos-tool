from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from sqlalchemy import URL, create_engine, make_url, pool

config = context.config


def _database_url() -> URL:
    if os.getenv("DB_TYPE", "postgresql").lower() == "sqlite":
        database_path = Path("dashboard_data/vos_tool.db").resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return URL.create("sqlite", database=str(database_path))

    raw_url = next(
        (
            os.getenv(name)
            for name in (
                "DATABASE_URL",
                "POSTGRES_URL",
                "POSTGRES_PRIVATE_URL",
                "DATABASE_PUBLIC_URL",
                "POSTGRES_PUBLIC_URL",
            )
            if os.getenv(name)
        ),
        None,
    )
    if raw_url:
        url = make_url(raw_url)
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg2")
        host = os.getenv("POSTGRES_HOST") or os.getenv("PGHOST") or url.host
        port_value = os.getenv("POSTGRES_PORT") or os.getenv("PGPORT")
        sslmode = os.getenv("POSTGRES_SSLMODE") or url.query.get("sslmode")
        if not sslmode:
            sslmode = "require" if host and "supabase.co" in host else "prefer"
        url = url.set(
            username=os.getenv("POSTGRES_USER") or os.getenv("PGUSER") or url.username,
            password=os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or url.password,
            host=host,
            port=int(port_value) if port_value else url.port,
            database=os.getenv("POSTGRES_DB") or os.getenv("PGDATABASE") or url.database,
            query={**url.query, "sslmode": sslmode},
        )
        return url

    host = os.getenv("POSTGRES_HOST") or os.getenv("PGHOST") or "localhost"
    sslmode = os.getenv("POSTGRES_SSLMODE")
    if not sslmode:
        sslmode = "require" if "supabase.co" in host else "prefer"
    return URL.create(
        "postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER") or os.getenv("PGUSER") or "vos_user",
        password=os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or "",
        host=host,
        port=int(os.getenv("POSTGRES_PORT") or os.getenv("PGPORT") or "5432"),
        database=os.getenv("POSTGRES_DB") or os.getenv("PGDATABASE") or "vos_tool",
        query={"sslmode": sslmode},
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url().render_as_string(hide_password=True),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
