"""
PUBLIC_INTERFACE

Script: test_db_connection.py

Test the ability to connect to Supabase/Postgres using the async SQLAlchemy engine configuration from the backend.

- Loads .env (must include SUPABASE_DB_URL)
- Attempts to open and close a connection using the backend's async engine.
- Prints connection status and any errors encountered.

Usage:
    python test_db_connection.py

Requirements:
- .env present at backend/.env with valid SUPABASE_DB_URL

This does NOT check for tables/schemas—only for a basic successful connection.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

def color(text, code):
    # Basic color for status
    return f"\033[{code}m{text}\033[0m"

def print_status(ok: bool, msg: str):
    if ok:
        print(color("[ SUCCESS ] ", "32") + msg)
    else:
        print(color("[ ERROR   ] ", "31") + msg)

def load_backend_env():
    # .env expected in backend/
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    BACKEND_ROOT = os.path.dirname(THIS_DIR)
    dotenv_path = os.path.join(BACKEND_ROOT, ".env")
    load_dotenv(dotenv_path=dotenv_path)

def main():
    load_backend_env()
    SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
    if not SUPABASE_DB_URL:
        print_status(False, "SUPABASE_DB_URL environment variable not set. Check .env in backend/")
        sys.exit(1)

    # Use the async engine config from backend code
    # Copied from main.py logic for dialect rewrite
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError:
        print_status(False, "sqlalchemy[asyncio] not installed. Run: pip install sqlalchemy[asyncio]")
        sys.exit(1)

    # Fix the asyncpg dialect
    ASYNC_DB_URL = (
        SUPABASE_DB_URL.replace("postgres://", "postgresql+asyncpg://")
        if SUPABASE_DB_URL.startswith("postgres://")
        else SUPABASE_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
    )
    engine = create_async_engine(ASYNC_DB_URL, echo=False, future=True)

    async def test_conn():
        try:
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
            print_status(True, f"Successfully connected to Supabase/Postgres: {ASYNC_DB_URL}")
            return True
        except Exception as e:
            print_status(False, f"Failed to connect: {type(e).__name__}: {e}")
            return False

    # Run the async test
    try:
        asyncio.run(test_conn())
    except Exception as e:
        print_status(False, f"Critical error initializing async engine: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
