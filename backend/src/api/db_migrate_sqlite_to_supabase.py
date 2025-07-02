"""
Utility script to migrate SQLite data (if exists) into Supabase/Postgres using SQLAlchemy async models.

- Checks for an 'app.db' SQLite file in this backend directory.
- Migrates all rows from games, players, units tables to Supabase database via SQLAlchemy async session.
- If no 'app.db' or no data, simply ensures required tables exist (schema-only mode).
- Usage: `python db_migrate_sqlite_to_supabase.py`
"""

import os
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Import models from main.py
from main import (
    Base, GameModel, PlayerModel, UnitModel, engine, async_session
)

# Paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BACKEND_DIR, "app.db")
SQLITE_URI = f"sqlite:///{SQLITE_DB_PATH}"

def check_sqlite_db():
    return os.path.isfile(SQLITE_DB_PATH)

def sync_sqlite_session():
    """Create a synchronous SQLAlchemy session to the old SQLite DB."""
    engine = create_engine(SQLITE_URI)
    Session = sessionmaker(engine)
    return Session()

async def create_schema_if_needed():
    """Ensure Supabase (Postgres) schema is set up."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def migrate_sqlite_to_supabase():
    # Step 1: Check for SQLite file
    if not check_sqlite_db():
        print("No SQLite app.db found. Only creating schema on Supabase/Postgres...")
        await create_schema_if_needed()
        print("Schema setup finished (no data migrated).")
        return

    # Step 2: Sync session for SQLite, Async session for Supabase DB
    sync_session = sync_sqlite_session()

    # Step 3: Read data from SQLite, ordered by games -> players -> units
    games = sync_session.query(GameModel).all()
    players = sync_session.query(PlayerModel).all()
    units = sync_session.query(UnitModel).all()

    if not games and not players and not units:
        print("SQLite app.db exists but contains no data. Only creating schema...")
        await create_schema_if_needed()
        print("Schema setup finished (no data migrated).")
        return

    print(f"Found {len(games)} games, {len(players)} players, {len(units)} units to migrate.")

    # Step 4: Insert to Supabase DB in correct order in one transaction.
    # Delete all current records to re-import everything cleanly.
    async with async_session() as session:
        async with session.begin():
            # Clear all tables
            await session.execute(UnitModel.__table__.delete())
            await session.execute(PlayerModel.__table__.delete())
            await session.execute(GameModel.__table__.delete())

            # Insert games
            for game in games:
                new_game = GameModel(
                    id=game.id,
                    status=game.status,
                    current_player=game.current_player,
                    winner=game.winner,
                )
                session.add(new_game)

            # Insert players
            for player in players:
                new_player = PlayerModel(
                    id=player.id,
                    game_id=player.game_id,
                    name=player.name,
                    color=player.color,
                )
                session.add(new_player)

            # Insert units
            for unit in units:
                new_unit = UnitModel(
                    id=unit.id,
                    game_id=unit.game_id,
                    player_id=unit.player_id,
                    x=unit.x,
                    y=unit.y,
                    hp=unit.hp,
                )
                session.add(new_unit)
        await session.commit()
    print("Migration completed: all records copied to Supabase/Postgres.")

if __name__ == "__main__":
    # Ensure .env and DB connection
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(BACKEND_DIR), ".env"))
    # Main migration logic
    asyncio.run(migrate_sqlite_to_supabase())
