import os
import asyncio
from typing import List, Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, ForeignKey, select, update
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from enum import Enum

from dotenv import load_dotenv

# Load config
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
if not SUPABASE_DB_URL:
    raise RuntimeError("SUPABASE_DB_URL environment variable not set. Ensure .env is present.")

ASYNC_DB_URL = SUPABASE_DB_URL.replace("postgres://", "postgresql+asyncpg://")

Base = declarative_base()
engine = create_async_engine(ASYNC_DB_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# FastAPI App Metadata
app = FastAPI(
    title="GridTactix Game Backend",
    description="REST API and WebSocket for grid-based tactical duel game (6x6).",
    version="1.0.0",
    openapi_tags=[
        {"name": "Games", "description": "Game creation, retrieval, update."},
        {"name": "Players", "description": "Player management and info."},
        {"name": "Units", "description": "Unit movement and attack actions."},
        {"name": "WebSocket", "description": "Real-time game state & events."}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ENUMs
class StatusEnum(str, Enum):
    waiting = "waiting"
    ongoing = "ongoing"
    finished = "finished"

# SQLAlchemy MODELS
class GameModel(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(16), nullable=False)
    current_player = Column(Integer, nullable=False)
    winner = Column(Integer, nullable=True)

    players = relationship("PlayerModel", back_populates="game", cascade="all, delete")
    units = relationship("UnitModel", back_populates="game", cascade="all, delete")

class PlayerModel(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    name = Column(String(64), nullable=False)
    color = Column(String(16), nullable=False)

    game = relationship("GameModel", back_populates="players")
    units = relationship("UnitModel", back_populates="player")

class UnitModel(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    hp = Column(Integer, nullable=False)

    game = relationship("GameModel", back_populates="units")
    player = relationship("PlayerModel", back_populates="units")

# ---------- Pydantic SCHEMAS ----------
class UnitBase(BaseModel):
    x: int = Field(..., ge=0, le=5, description="Unit's x position on grid (0-indexed)")
    y: int = Field(..., ge=0, le=5, description="Unit's y position on grid (0-indexed)")
    hp: int = Field(..., ge=0, le=10, description="Unit's HP")

class UnitCreate(UnitBase):
    player_id: int = Field(..., description="Player owner of this unit")

class Unit(UnitBase):
    id: int
    player_id: int

    class Config:
        orm_mode = True

class PlayerBase(BaseModel):
    name: str = Field(..., description="Player's display name")
    color: str = Field(..., description="Hex color for player units")

class PlayerCreate(PlayerBase):
    pass

class Player(PlayerBase):
    id: int

    class Config:
        orm_mode = True

class GameCreate(BaseModel):
    players: List[PlayerCreate] = Field(..., description="Players (2) participating in the game")
    units_per_player: Optional[int] = Field(3, description="How many units per player, default 3")

class Game(BaseModel):
    id: int
    status: StatusEnum
    current_player: int
    winner: Optional[int]
    players: List[Player]
    units: List[Unit]

    class Config:
        orm_mode = True

class MoveAction(BaseModel):
    unit_id: int = Field(..., description="ID of the unit to move")
    target_x: int = Field(..., ge=0, le=5, description="Destination x")
    target_y: int = Field(..., ge=0, le=5, description="Destination y")

class AttackAction(BaseModel):
    attacker_id: int = Field(..., description="ID of the attacking unit")
    target_id: int = Field(..., description="ID of the unit being attacked")

# Dependency for DB session
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

# ----- Utility/Game Logic Helpers (async) -----
# PUBLIC_INTERFACE
async def get_game_by_id(game_id: int, session: AsyncSession) -> Game:
    """Fetch a Game and associated players & units, assembling Pydantic Game"""
    game: GameModel = await session.get(GameModel, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Load players and units for this game
    players_result = await session.execute(select(PlayerModel).where(PlayerModel.game_id == game_id))
    players = players_result.scalars().all()
    units_result = await session.execute(select(UnitModel).where(UnitModel.game_id == game_id))
    units = units_result.scalars().all()

    out = Game(
        id=game.id,
        status=game.status,
        current_player=game.current_player,
        winner=game.winner,
        players=[Player(id=p.id, name=p.name, color=p.color) for p in players],
        units=[Unit(id=u.id, player_id=u.player_id, x=u.x, y=u.y, hp=u.hp) for u in units],
    )
    return out

def next_player(game: Game) -> int:
    ids = [p.id for p in game.players]
    idx = ids.index(game.current_player)
    next_idx = (idx + 1) % len(ids)
    return ids[next_idx]

def is_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    return abs(x1 - x2) + abs(y1 - y2) == 1

def find_unit(unit_id: int, units: List[Unit]) -> Unit:
    for unit in units:
        if unit.id == unit_id:
            return unit
    raise HTTPException(status_code=404, detail="Unit not found")

def valid_move(unit: Unit, target_x: int, target_y: int, units: List[Unit]) -> bool:
    if not (0 <= target_x < 6 and 0 <= target_y < 6):
        return False
    if not is_adjacent(unit.x, unit.y, target_x, target_y):
        return False
    for u in units:
        if u.x == target_x and u.y == target_y and u.hp > 0:
            return False
    return True

def valid_attack(attacker: Unit, target: Unit) -> bool:
    return is_adjacent(attacker.x, attacker.y, target.x, target.y) and target.hp > 0

async def set_winner_if_any(game_id: int, session: AsyncSession):
    # Winner = if only one player's units have HP > 0
    stmt = select(UnitModel.player_id).where(
        UnitModel.game_id == game_id, UnitModel.hp > 0
    )
    result = await session.execute(stmt)
    alive_player_ids = [row[0] for row in result.fetchall()]
    if len(set(alive_player_ids)) == 1:
        winner_id = alive_player_ids[0]
        await session.execute(update(GameModel).where(GameModel.id == game_id).values(status=StatusEnum.finished.value, winner=winner_id))
        await session.commit()

# --------- WebSocket Manager (as before) ---------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, game_id: int, websocket: WebSocket):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()
        self.active_connections[game_id].add(websocket)

    def disconnect(self, game_id: int, websocket: WebSocket):
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def broadcast(self, game_id: int, message: dict):
        clients = self.active_connections.get(game_id, set())
        for ws in list(clients):  # make a copy, since a disconnect may change the set
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(game_id, ws)

manager = ConnectionManager()

############# ROUTES #############

# PUBLIC_INTERFACE
@app.get("/", tags=["Games"])
async def health_check():
    """Health check."""
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.post("/api/games/", response_model=Game, status_code=201, tags=["Games"], summary="Create new game")
async def create_game(payload: GameCreate, session: AsyncSession = Depends(get_session)):
    """Start a new game. Initializes players and units. Returns complete game state."""
    # Create game row
    async with session.begin():
        game = GameModel(status=StatusEnum.ongoing.value, current_player=0)
        session.add(game)
        await session.flush()  # Assigns game.id
        player_ids = []
        # Insert players
        for pl in payload.players:
            player = PlayerModel(game_id=game.id, name=pl.name, color=pl.color)
            session.add(player)
            await session.flush()
            player_ids.append(player.id)
        # Update current_player to the first player
        game.current_player = player_ids[0]
        await session.flush()
        # Insert units
        for i, pid in enumerate(player_ids):
            start_row = 0 if i == 0 else 5
            for j in range(payload.units_per_player or 3):
                x = j * (6 // (payload.units_per_player or 3))
                y = start_row
                unit = UnitModel(game_id=game.id, player_id=pid, x=x, y=y, hp=3)
                session.add(unit)
    await session.commit()
    return await get_game_by_id(game.id, session)

# PUBLIC_INTERFACE
@app.get("/api/games/", response_model=List[Game], tags=["Games"], summary="List all games")
async def list_games(session: AsyncSession = Depends(get_session)):
    """List all games and their basic states."""
    rows = await session.execute(select(GameModel.id))
    ids = [row[0] for row in rows.fetchall()]
    return [await get_game_by_id(gid, session) for gid in ids]

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}", response_model=Game, tags=["Games"], summary="Get a game by ID")
async def get_game(game_id: int = Path(..., gt=0, description="ID of game"), session: AsyncSession = Depends(get_session)):
    """Get the current state of a specific game (units, players, turn, winner, etc)."""
    return await get_game_by_id(game_id, session)

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/move", response_model=Game, tags=["Units"], summary="Move a unit")
async def move_unit(game_id: int, action: MoveAction, session: AsyncSession = Depends(get_session)):
    """Move a unit to an adjacent empty cell. Only current player's unit can move."""
    game = await get_game_by_id(game_id, session)
    if game.status != StatusEnum.ongoing:
        raise HTTPException(status_code=400, detail="Game not in progress")
    unit = find_unit(action.unit_id, game.units)
    if unit.player_id != game.current_player:
        raise HTTPException(status_code=403, detail="Not your turn to move")
    if not valid_move(unit, action.target_x, action.target_y, game.units):
        raise HTTPException(status_code=400, detail="Invalid move")
    # Update unit's x/y
    await session.execute(
        update(UnitModel)
        .where(UnitModel.id == unit.id)
        .values(x=action.target_x, y=action.target_y)
    )
    # End turn
    npid = next_player(game)
    await session.execute(
        update(GameModel)
        .where(GameModel.id == game_id)
        .values(current_player=npid)
    )
    await session.commit()
    new_game = await get_game_by_id(game_id, session)
    asyncio.create_task(manager.broadcast(game_id, {"event": "move", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/attack", response_model=Game, tags=["Units"], summary="Attack with a unit")
async def attack_unit(game_id: int, action: AttackAction, session: AsyncSession = Depends(get_session)):
    """Attack adjacent enemy unit. Only current player's unit can attack."""
    game = await get_game_by_id(game_id, session)
    if game.status != StatusEnum.ongoing:
        raise HTTPException(status_code=400, detail="Game not in progress")
    attacker = find_unit(action.attacker_id, game.units)
    if attacker.player_id != game.current_player:
        raise HTTPException(status_code=403, detail="Not your turn to attack")
    target = find_unit(action.target_id, game.units)
    if attacker.player_id == target.player_id:
        raise HTTPException(status_code=400, detail="Cannot attack ally")
    if not valid_attack(attacker, target):
        raise HTTPException(status_code=400, detail="Target is not adjacent or already defeated")
    # Apply damage: For simplicity, always 1 HP per attack
    new_hp = max(target.hp - 1, 0)
    await session.execute(
        update(UnitModel).where(UnitModel.id == target.id).values(hp=new_hp)
    )
    await set_winner_if_any(game_id, session)
    await session.commit()
    # End turn if not finished
    new_game = await get_game_by_id(game_id, session)
    if new_game.status != StatusEnum.finished:
        npid = next_player(game)
        await session.execute(
            update(GameModel).where(GameModel.id == game_id).values(current_player=npid)
        )
        await session.commit()
        new_game = await get_game_by_id(game_id, session)
    asyncio.create_task(manager.broadcast(game_id, {"event": "attack", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/endturn", response_model=Game, tags=["Games"], summary="End player's turn")
async def end_turn(game_id: int, session: AsyncSession = Depends(get_session)):
    """Current player ends their turn (without action)."""
    game = await get_game_by_id(game_id, session)
    if game.status != StatusEnum.ongoing:
        raise HTTPException(status_code=400, detail="Game not in progress")
    npid = next_player(game)
    await session.execute(
        update(GameModel)
        .where(GameModel.id == game_id)
        .values(current_player=npid)
    )
    await session.commit()
    new_game = await get_game_by_id(game_id, session)
    asyncio.create_task(manager.broadcast(game_id, {"event": "endturn", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}/players", response_model=List[Player], tags=["Players"], summary="Get players in a game")
async def get_players(game_id: int, session: AsyncSession = Depends(get_session)):
    """Get all players in a specified game."""
    game = await get_game_by_id(game_id, session)
    return game.players

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}/units", response_model=List[Unit], tags=["Units"], summary="Get game units")
async def get_units(game_id: int, session: AsyncSession = Depends(get_session)):
    """Get all units in a specified game."""
    game = await get_game_by_id(game_id, session)
    return game.units

# PUBLIC_INTERFACE
@app.websocket("/ws/games/{game_id}", name="Game real-time updates", tags=["WebSocket"])
async def websocket_game_updates(websocket: WebSocket, game_id: int = Path(..., description="Game id for WebSocket session")):
    """
    WebSocket connection for real-time updates for the game.
    - Connect via: `/ws/games/{game_id}`
    - Receives JSON events: {"event": "move"/"attack"/"endturn", "game": {...}}
    """
    await manager.connect(game_id, websocket)
    try:
        # On connect: send current game state
        async with async_session() as session:
            game = await get_game_by_id(game_id, session)
        await websocket.send_json({"event": "sync", "game": game.dict()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
    except Exception as e:
        manager.disconnect(game_id, websocket)
        raise e

# PUBLIC_INTERFACE
@app.get("/api/docs/ws", tags=["WebSocket"])
def websocket_usage():
    """WebSocket usage: Connect to /ws/games/{game_id} for live game events."""
    return {
        "summary": "WebSocket API usage",
        "ws_url": "/ws/games/{game_id}",
        "events": ["move", "attack", "endturn", "sync"]
    }

# ---- Auto-create tables helper ----
# You may run this once at container start to create/migrate -- but prefer to use Alembic/migrations in prod!
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
