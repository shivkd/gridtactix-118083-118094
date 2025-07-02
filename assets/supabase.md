# Supabase Integration & Backend Migration Guide

## Credentials Storage

- Supabase project credentials (URL, API key, and database URL) are now securely stored in `backend/.env`, which must never be committed to source control.
    - `SUPABASE_URL`: https://plzaymbonadzwjcrskld.supabase.co
    - `SUPABASE_KEY`: [REDACTED]
    - `SUPABASE_DB_URL`: postgresql://postgres:[YOUR_DB_PASSWORD]@db.plzaymbonadzwjcrskld.supabase.co:5432/postgres

## FastAPI Backend Configuration Changes

- The backend now connects to the Supabase Postgres database **instead of local SQLite**.
- Database clients are switched to async SQLAlchemy (`sqlalchemy[asyncio]`) + `asyncpg`.
- The `.env` file must be present for the FastAPI backend to connect.

## Database Schema Sync

The following tables are required on Supabase Postgres (run with Alembic/migrations or manually if not present):

```sql
CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    status VARCHAR(16) NOT NULL,
    current_player INTEGER NOT NULL,
    winner INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id),
    name VARCHAR(64) NOT NULL,
    color VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    hp INTEGER NOT NULL
);
```

- **If these tables are not present in Supabase, create/alter using the SQL tab or migrations.**

## Code and Persistence Layer Changes

- All database access methods in `backend/src/api/main.py` must use async SQLAlchemy with the `SUPABASE_DB_URL`.
- Local SQLite file use (`app.db`) is fully removed.

## Backend Development/Deployment

- Install dependencies: `pip install -r requirements.txt`
- Backend must use the `.env` for config/secrets.
- Use `alembic` or SQL tab in Supabase to keep schemas in sync.

## Caution

- DO NOT commit secrets or `.env` to version control.
- Document any changes to the DB schema here as you evolve the backend.

## See also

- [Supabase Documentation](https://supabase.com/docs)
