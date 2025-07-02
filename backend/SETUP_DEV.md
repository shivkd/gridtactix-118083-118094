# Backend FastAPI Development Environment Setup

Before running linter or development commands, ensure the virtual environment is created and dependencies are installed:

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install flake8
```

Now you can run linting (from the backend directory):

```sh
venv/bin/flake8 src/
```

## Database migration (SQLite to Supabase)

A script is provided to automatically migrate legacy SQLite data (if any) to the Supabase-backed Postgres database.
- To run the migration, from the backend directory:

```sh
cd src/api
python db_migrate_sqlite_to_supabase.py
```

- If `app.db` exists and contains games/players/units, they will all be imported to Supabase.
- If `app.db` does not exist, only the schema is guaranteed to be set up.
- Make sure your `.env` is present and contains the correct `SUPABASE_DB_URL`.
```

If using a custom linter script, make sure the `venv` is activated and required packages are installed.
