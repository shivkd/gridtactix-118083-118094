"""
PUBLIC_INTERFACE

Script: db_migrate_sqlite_to_supabase.py

Utility script to migrate database schema and (if present) data from legacy SQLite (app.db) to Supabase/Postgres
via SQLAlchemy async models.

- Checks for an 'app.db' SQLite file in this backend directory.
- Migrates all rows from games, players, and units tables to Supabase/Postgres via SQLAlchemy async session.
- If no 'app.db' or if it has no relevant data, simply ensures required tables exist in Supabase/Postgres (schema-only mode).

Usage: python db_migrate_sqlite_to_supabase.py

Requirements:
- .env must be present and configured with SUPABASE_DB_URL.

WARNING: This script deletes *all* current data in Supabase tables ('games', 'players', 'units') before importing.
Only use on an empty or test database, or if you intend to overwrite completely.

"""

import os
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Import models and engine/session system from main.py
from main import (
    Base, GameModel, PlayerModel, UnitModel, engine, async_session,
)

# Paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BACKEND_DIR, "app.db")
SQLITE_URI = f"sqlite:///{SQLITE_DB_PATH}"

# PUBLIC_INTERFACE
def check_sqlite_db():
    """Check if legacy app.db exists in backend directory."""
    return os.path.isfile(SQLITE_DB_PATH)

# PUBLIC_INTERFACE
def sync_sqlite_session():
    """Create a synchronous SQLAlchemy session to legacy SQLite DB."""
    engine = create_engine(SQLITE_URI)
    Session = sessionmaker(engine)
    return Session()

# PUBLIC_INTERFACE
async def create_schema_if_needed():
    """Ensure Supabase (Postgres) schema for games/players/units is present."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# PUBLIC_INTERFACE
async def migrate_sqlite_to_supabase():
    """
    Migrate all rows in games, players, units from SQLite (if exists) into Supabase/Postgres via async SQLAlchemy.

    - If no legacy SQLite or no data: just ensure schema is created in Supabase/Postgres (no data import).
    - Otherwise: wipes Postgres tables before import (do not use on production DBs with important data).
    """

    # Check for SQLite file
    if not check_sqlite_db():
        print("No SQLite app.db found. Only creating schema on Supabase/Postgres...")
        await create_schema_if_needed()
        print("Schema setup finished (no data migrated).")
        return

    # Open sync session for SQLite
    sync_session = sync_sqlite_session()

    # Read data from SQLite, in order: games, players, units
    games = sync_session.query(GameModel).all()
    players = sync_session.query(PlayerModel).all()
    units = sync_session.query(UnitModel).all()
    sync_session.close()

    if not games and not players and not units:
        print("SQLite app.db exists but contains no data. Only creating schema...")
        await create_schema_if_needed()
        print("Schema setup finished (no data migrated).")
        return

    print(f"Found {len(games)} games, {len(players)} players, {len(units)} units to migrate.")

    # Insert into Supabase/Postgres DB in correct order in one transaction.
    # Delete all current records to re-import everything cleanly.
    async with async_session() as session:
        async with session.begin():
            # Truncate all tables before import for idempotency.
            await session.execute(UnitModel.__table__.delete())
            await session.execute(PlayerModel.__table__.delete())
            await session.execute(GameModel.__table__.delete())

            # Insert games
            for game in games:
                session.add(
                    GameModel(
                        id=game.id,
                        status=game.status,
                        current_player=game.current_player,
                        winner=game.winner,
                    )
                )

            # Insert players
            for player in players:
                session.add(
                    PlayerModel(
                        id=player.id,
                        game_id=player.game_id,
                        name=player.name,
                        color=player.color,
                    )
                )

            # Insert units
            for unit in units:
                session.add(
                    UnitModel(
                        id=unit.id,
                        game_id=unit.game_id,
                        player_id=unit.player_id,
                        x=unit.x,
                        y=unit.y,
                        hp=unit.hp,
                    )
                )
        await session.commit()
    print("Migration completed: all records copied to Supabase/Postgres.")


if __name__ == "__main__":
    # Load environment variables for DB connection
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(BACKEND_DIR), ".env"))
    # Run main migration logic
    asyncio.run(migrate_sqlite_to_supabase())
