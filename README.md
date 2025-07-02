# GridTactix: FastAPI Backend & Supabase/Postgres Integration

## Overview

GridTactix is a Dockerized, grid-based tactical duel game with a React (TypeScript) frontend and a FastAPI backend. The backend now uses a **Supabase/Postgres** database (no longer SQLite) for all persistence and data access.

## Project Structure

- **frontend/**: React/TypeScript client (see dedicated instructions in frontend workspace)
- **backend/**: FastAPI backend (serves REST APIs, WebSocket, and migrates/game logic)
- **assets/supabase.md**: Detailed Supabase/Postgres integration and SQL schema info

## ⚠️ Important Backend Change: Supabase/Postgres is Required

The backend no longer works with SQLite. All game data is now stored in (and must be accessed from) your team/project's Supabase Postgres instance.

### Environment/Secrets

You MUST provide a `.env` file in `backend/` (never commit this file). Required variables:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_key
SUPABASE_DB_URL=postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR-PROJECT.supabase.co:5432/postgres
```

- See `assets/supabase.md` for help obtaining these values.

## Database Migration (From SQLite)

If you have legacy game data in a local `app.db` (SQLite) database, use the provided migration script.

### Step-by-step Migration

1. **Setup your environment**  
   Activate your backend virtualenv and install requirements:
   ```sh
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Update/Create your `.env` file**  
   You must set all Supabase connection variables above.

3. **Run the migration script**  
   ```sh
   cd backend/src/api
   python db_migrate_sqlite_to_supabase.py
   ```
   - If `app.db` is present, games/players/units will be copied to Supabase.
   - If `app.db` is absent, only the required tables/schema will be created.

   > Warning: The migration script will wipe all existing tables/data in Supabase before import! **DO NOT run against any prod DB containing real/important games!**

4. **Verify your backend works**  
   Start your FastAPI backend and use the `/api/games/` endpoints—these now read/write data in Supabase/Postgres.

5. **Keep your schema in sync**  
   Use Alembic or Supabase's SQL editor if you manually update backend models.

## Developing/Running Backend

- All backend code uses async SQLAlchemy via Supabase/Postgres (`SUPABASE_DB_URL`).
- Run all development/test/linting commands from within `backend/`.
- For new environments: provision a blank Supabase project, update `.env`, run the migration script at least once!

## Troubleshooting

- **DB connection errors**: Double-check `.env` settings/matching your Supabase project.
- **Missing schema/tables**: Run the migration script or create tables per `assets/supabase.md`.
- **Legacy data**: The new backend does NOT use SQLite anymore; previous local data is not loaded unless migrated.

## References

- See `assets/supabase.md` for backend DB schema, SQL table definitions, and Supabase project setup.
- [Supabase Documentation](https://supabase.com/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---
**Note:** Never commit `.env` or secrets to version control. Document any backend DB schema changes in `assets/supabase.md` as you evolve the project.
