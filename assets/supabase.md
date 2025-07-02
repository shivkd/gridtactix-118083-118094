# Supabase Integration & Backend Migration Guide

This backend now uses Supabase/Postgres **instead of** a local SQLite DB.

## 1. Environment/Secrets

All backend authentication/secrets must be in `backend/.env` (never commit to Git). **Required keys:**
- `SUPABASE_URL`: e.g. `https://YOUR_PROJECT_REF.supabase.co`
- `SUPABASE_KEY`: (Service key from your Supabase project)
- `SUPABASE_DB_URL`: e.g. `postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres`

Example `.env`:
```
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=eyJhb...
SUPABASE_DB_URL=postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
```

## 2. Database Schema Requirements

The backend requires these tables with proper foreign keys:

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
If these tables are not present, create them using Supabase's SQL editor or Alembic.

## 3. Backend Migration: From SQLite

A migration script is provided:  
`backend/src/api/db_migrate_sqlite_to_supabase.py`

**How to migrate:**
1. Ensure `.env` is present and correct.
2. (Optional) Place your legacy `app.db` SQLite database in `backend/src/api/`.
3. Run:
   ```
   cd backend/src/api
   python db_migrate_sqlite_to_supabase.py
   ```
   - If `app.db` exists: All games/players/units are copied into Supabase (all current Supabase data is wiped).
   - If `app.db` does not exist: Only Supabase tables/schema are created, no data import.

**Never run against production data you want to keep!**  
The migration script always truncates (`delete from`) destination tables before import.

## 4. Development and Testing

- Backend code only talks to Supabase/Postgres via async SQLAlchemy.
- Test your FastAPI endpoints (e.g., `/api/games/`); ensure you are reading/writing to Supabase.
- On first project setup, **run the migration script** (even on new DB) to ensure schema exists.
- Keep `.env` up to date for each environment.

## 5. Keeping Schema in Sync

- To alter DB design, add models/migrations and keep schema + code in sync.
- Use Alembic, manual migration scripts, or the Supabase SQL tab as appropriate.

## 6. Further Reading

- [Supabase Documentation](https://supabase.com/docs)
- [How to get service keys/DB URLs](https://supabase.com/docs/guides/database/connecting-to-postgres)

---

Record any schema-altering changes and important DB documentation here as your backend evolves!

