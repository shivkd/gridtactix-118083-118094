import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum
import sqlite3
import threading
import os

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

# =======================
# Database Path Discovery
# =======================
def locate_db_file(verbose=True):
    """
    Searches for the SQLite DB file in priority order:
      1. Absolute path from SQLITE_DB environment variable (MUST be set & valid)
      2. 'app.db' in working directory (rarely correct in Docker)
      3. Hardcoded canonical path from analysis
    Returns the file path if found, else None (prints to stderr).
    """
    possible_paths = [
        os.environ.get("SQLITE_DB"),
        os.path.join(os.getcwd(), "app.db"),
        "/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db"
    ]
    reason = [
        "SQLITE_DB env variable",
        "app.db in current dir [" + os.getcwd() + "]",
        "canonical project database dir"
    ]
    for pidx, path in enumerate(possible_paths):
        if path and os.path.exists(path):
            # Enhanced: Check permissions
            errors = []
            try:
                if not os.access(path, os.R_OK):
                    errors.append("not readable")
                if not os.access(path, os.W_OK):
                    errors.append("not writable")
            except Exception as e:
                errors.append("permission check failed: %s" % e)
            if errors:
                if verbose:
                    print(f"ERROR: Database file '{path}' ({reason[pidx]}) is " + " and ".join(errors) + ".", file=sys.stderr)
                return None
            if verbose:
                print(f"INFO: Database file discovered at '{path}' ({reason[pidx]})", file=sys.stderr)
            return path
        elif verbose and path:
            print(f"SKIP: {reason[pidx]}: '{path}' not found.", file=sys.stderr)
    if verbose:
        print("ERROR: Could not locate SQLite database file (checked: env, cwd, canonical path).", file=sys.stderr)
    return None

DB_FILE = locate_db_file(verbose=True)
if not DB_FILE:
    # Do not fallback to a phantom file! Exit to force correct config.
    print("CRITICAL: Backend initialization failed due to missing or inaccessible SQLite database.\n"
          "Check SQLITE_DB env var and volume mount. Refer to backend/DEBUG_502_BAD_GATEWAY_ANALYSIS.md.", file=sys.stderr)
    sys.exit(5)

DB_LOCK = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Attempt to connect and initialize tables; aborts on OSError.
    Logs precise startup diagnostics for DB file and CWD.
    """
    try:
        # Print working dir and DB file path at startup (for Docker/cwd troubleshooting)
        print(f"FastAPI working directory: {os.getcwd()} (should match Dockerfile or Compose setting)", file=sys.stderr)
        print(f"Using SQLite DB path: {DB_FILE}", file=sys.stderr)
        with DB_LOCK:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    current_player INTEGER NOT NULL,
                    winner INTEGER
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    hp INTEGER NOT NULL,
                    FOREIGN KEY(game_id) REFERENCES games(id),
                    FOREIGN KEY(player_id) REFERENCES players(id)
                )
            """)
            conn.commit()
            conn.close()
    except Exception as e:
        print("CRITICAL: Backend failed DB/table initialization: %s" % e, file=sys.stderr)
        sys.exit(11)
init_db()


# If launched directly, run the FastAPI server on 0.0.0.0 (all interfaces) and the port given by environment variable or 8000
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=False)

# ENUMs
class StatusEnum(str, Enum):
    waiting = "waiting"
    ongoing = "ongoing"
    finished = "finished"

# SCHEMAS

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

# Game logic helpers
def get_game_by_id(game_id: int) -> Game:
    with DB_LOCK:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        game_row = c.fetchone()
        if not game_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Game not found")
        c.execute("SELECT * FROM players WHERE game_id = ?", (game_id,))
        players = [Player(id=row["id"], name=row["name"], color=row["color"]) for row in c.fetchall()]
        c.execute("SELECT * FROM units WHERE game_id = ?", (game_id,))
        units = [Unit(id=row["id"], player_id=row["player_id"], x=row["x"], y=row["y"], hp=row["hp"]) for row in c.fetchall()]
        game = Game(
            id=game_row["id"],
            status=game_row["status"],
            current_player=game_row["current_player"],
            winner=game_row["winner"],
            players=players,
            units=units
        )
        conn.close()
        return game

def next_player(game: Game) -> int:
    idx = [p.id for p in game.players].index(game.current_player)
    next_idx = (idx + 1) % len(game.players)
    return game.players[next_idx].id

def is_adjacent(x1: int, y1: int, x2: int, y2: int) -> bool:
    # 4-directional adjacency
    return abs(x1 - x2) + abs(y1 - y2) == 1

def find_unit(unit_id: int, units: List[Unit]) -> Unit:
    for unit in units:
        if unit.id == unit_id:
            return unit
    raise HTTPException(status_code=404, detail="Unit not found")

def valid_move(unit: Unit, target_x: int, target_y: int, units: List[Unit]) -> bool:
    # Unit must move to adjacent empty square
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

def update_db(sql: str, params: tuple):
    with DB_LOCK:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        conn.close()

def set_winner_if_any(game_id: int):
    # Winner = if only one player's units have HP > 0
    with DB_LOCK:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT player_id, COUNT(*) as count 
            FROM units WHERE game_id=? AND hp > 0 
            GROUP BY player_id
        """, (game_id,))
        alive_counts = c.fetchall()
        if len(alive_counts) == 1:
            winner_id = alive_counts[0]["player_id"]
            c.execute("UPDATE games SET status=?, winner=? WHERE id=?", (StatusEnum.finished.value, winner_id, game_id))
            conn.commit()
        conn.close()

# WebSocket manager
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
        # Send to all clients in that game
        clients = self.active_connections.get(game_id, set())
        for ws in clients:
            await ws.send_json(message)

manager = ConnectionManager()

############# ROUTES #############

# PUBLIC_INTERFACE
@app.get("/", tags=["Games"])
def health_check():
    """Health check."""
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.post("/api/games/", response_model=Game, status_code=201, tags=["Games"], summary="Create new game")
def create_game(payload: GameCreate):
    """Start a new game. Initializes players and units. Returns complete game state."""
    with DB_LOCK:
        conn = get_db_connection()
        c = conn.cursor()
        # Insert the game, status waiting, first player arbitrarily 1
        c.execute("INSERT INTO games (status, current_player) VALUES (?,?)", (StatusEnum.ongoing.value, 0))
        game_id = c.lastrowid
        player_ids = []
        for idx, pl in enumerate(payload.players):
            c.execute("INSERT INTO players (game_id, name, color) VALUES (?,?,?)", (game_id, pl.name, pl.color))
            player_id = c.lastrowid
            player_ids.append(player_id)
        # Set current_player to 1st player created
        c.execute("UPDATE games SET current_player=? WHERE id=?", (player_ids[0], game_id))
        # Place units: each player's units in their row; HP=3 default
        for i, pid in enumerate(player_ids):
            start_row = 0 if i == 0 else 5
            for j in range(payload.units_per_player or 3):
                x = j * (6 // (payload.units_per_player or 3))
                y = start_row
                c.execute("INSERT INTO units (game_id, player_id, x, y, hp) VALUES (?,?,?,?,?)",
                          (game_id, pid, x, y, 3))
        conn.commit()
    return get_game_by_id(game_id)

# PUBLIC_INTERFACE
@app.get("/api/games/", response_model=List[Game], tags=["Games"], summary="List all games")
def list_games():
    """List all games and their basic states."""
    with DB_LOCK:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM games")
        ids = [row["id"] for row in c.fetchall()]
    return [get_game_by_id(gid) for gid in ids]

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}", response_model=Game, tags=["Games"], summary="Get a game by ID")
def get_game(game_id: int = Path(..., gt=0, description="ID of game")):
    """Get the current state of a specific game (units, players, turn, winner, etc)."""
    return get_game_by_id(game_id)

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/move", response_model=Game, tags=["Units"], summary="Move a unit")
def move_unit(game_id: int, action: MoveAction):
    """Move a unit to an adjacent empty cell. Only current player's unit can move."""
    game = get_game_by_id(game_id)
    if game.status != StatusEnum.ongoing:
        raise HTTPException(status_code=400, detail="Game not in progress")
    unit = find_unit(action.unit_id, game.units)
    if unit.player_id != game.current_player:
        raise HTTPException(status_code=403, detail="Not your turn to move")
    if not valid_move(unit, action.target_x, action.target_y, game.units):
        raise HTTPException(status_code=400, detail="Invalid move")
    # Update db
    update_db("UPDATE units SET x=?, y=? WHERE id=?", (action.target_x, action.target_y, unit.id))
    # End turn
    npid = next_player(game)
    update_db("UPDATE games SET current_player=? WHERE id=?", (npid, game_id))
    new_game = get_game_by_id(game_id)
    # Notify websocket clients
    import asyncio
    asyncio.create_task(manager.broadcast(game_id, {"event": "move", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/attack", response_model=Game, tags=["Units"], summary="Attack with a unit")
def attack_unit(game_id: int, action: AttackAction):
    """Attack adjacent enemy unit. Only current player's unit can attack."""
    game = get_game_by_id(game_id)
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
    update_db("UPDATE units SET hp=? WHERE id=?", (new_hp, target.id))
    set_winner_if_any(game_id)
    # End turn
    new_game = get_game_by_id(game_id)
    if new_game.status != StatusEnum.finished:
        npid = next_player(game)
        update_db("UPDATE games SET current_player=? WHERE id=?", (npid, game_id))
        new_game = get_game_by_id(game_id)
    # Notify websocket clients
    import asyncio
    asyncio.create_task(manager.broadcast(game_id, {"event": "attack", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.post("/api/games/{game_id}/endturn", response_model=Game, tags=["Games"], summary="End player's turn")
def end_turn(game_id: int):
    """Current player ends their turn (without action)."""
    game = get_game_by_id(game_id)
    if game.status != StatusEnum.ongoing:
        raise HTTPException(status_code=400, detail="Game not in progress")
    npid = next_player(game)
    update_db("UPDATE games SET current_player=? WHERE id=?", (npid, game_id))
    new_game = get_game_by_id(game_id)
    # Notify clients
    import asyncio
    asyncio.create_task(manager.broadcast(game_id, {"event": "endturn", "game": new_game.dict()}))
    return new_game

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}/players", response_model=List[Player], tags=["Players"], summary="Get players in a game")
def get_players(game_id: int):
    """Get all players in a specified game."""
    game = get_game_by_id(game_id)
    return game.players

# PUBLIC_INTERFACE
@app.get("/api/games/{game_id}/units", response_model=List[Unit], tags=["Units"], summary="Get game units")
def get_units(game_id: int):
    """Get all units in a specified game."""
    game = get_game_by_id(game_id)
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
        game = get_game_by_id(game_id)
        await websocket.send_json({"event": "sync", "game": game.dict()})
        while True:
            # No client->server messages expected; keep the socket open.
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
