# 502 Bad Gateway Error Investigation Results

_This document summarizes the full diagnosis for the persistent 502 Bad Gateway errors in the backend container, covering log, network, configuration, FastAPI/code startup, and SQLite access issues._

---

## 1. FastAPI Server Initialization & Endpoint Health

- **Health Check:** The FastAPI backend exposes a root endpoint (`@app.get("/")`) returning `{ "message": "Healthy" }`. If the server starts and is reachable, a GET request to `/` or `/docs` should return 200. If the server fails to start due to any cause (e.g., DB unavailable), container orchestration or proxy will show a 502 error.
- **Entrypoint:** When run as the main module, the application launches `uvicorn` on `0.0.0.0` using the port from `$PORT` env or 8000 by default.

## 2. SQLite Database Connectivity

- **Database Path Discovery:** Both FastAPI app and `check_sqlite_file.py` use the function `locate_db_file()` to search for the SQLite file in three places:
    1. Path from `SQLITE_DB` environment variable (should be set).
    2. `app.db` in the current working directory.
    3. `/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db` (the expected location of the external database container).
- **Fallback:** If the file is not found, FastAPI prints an error and falls back to `"app.db"` in the current dir, which is almost certainly missing/empty/not mapped, causing operational errors.

## 3. Database File Permissions & Existence

- `check_sqlite_file.py` performs an explicit check for the discovered DB file and tests both read and write permissions.
- The `post_process_status.lock` with content `SUCCESS` implies that this check **succeeded** at least once.

**Potential Issues:**
- If the backend container does not have the correct `SQLITE_DB` env or proper file mapping to the database container, DB access will fail.
- If launched with a working directory not matching the expectations (`os.getcwd()`), DB path resolution may fail.
- Permissions may differ if the process user/context differs from the one who created the DB file.

## 4. Docker/Deployment Misconfiguration

Common sources of 502 errors include:
- **FastAPI process crash or failure to start:** (usually due to missing DB or unhandled exceptions in `init_db()`)
- **DB Not Reachable:** If backend and database containers are not joined into the same Docker network, or the SQLite file is not volume-mounted from the correct path, or the `SQLITE_DB` env var is unset/misconfigured.
- **Proxy Misrouting:** If the reverse proxy points to an unloaded or crashed service, 502 results.
- **File Permissions:** Even if the DB file exists, read/write blockers will surface as operational errors in FastAPI (detected by `check_sqlite_file.py`, but runtime could differ).

## 5. Startup Sequence and Initialization

- The backend attempts to run `init_db()` at startup, which connects to SQLite and creates tables if needed. It assumes the DB is reachable and modifiable. If it fails (e.g., DB not found, permissions error), the FastAPI app may not fully start or throw 500s to all endpoints.

## 6. Observed File Paths and Configuration State

From your workspace:
- `backend`'s code expects a database at the location `/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db`.
- There is no code-based fallback for Docker secrets, network-hosted DB, or custom mountpoint: **absolute correctness of file mapping and `SQLITE_DB` env is essential.**

---

# Detected and Potential Issues

### 1. **Database File Path and Mapping**
   - If `SQLITE_DB` env var is not set **inside the backend container** to the _actual path_ of the SQLite file (on the shared volume), the app will fail to locate the database and silently fall back to `app.db` (likely missing).
   - If Docker Compose/host does not mount the DB file or volume correctly (from the database container's `myapp.db` to backend with the same path), all DB access fails.

### 2. **File Permissions**
   - Backend must have read/write permission on the file at the resolved DB path. Any permission mismatch causes FastAPI or SQLite to raise operational errors, possibly causing the server to crash and 502 to result.

### 3. **Working Directory/Entrypoint Path**
   - The code relies on `os.getcwd()` and relative paths. If the backend container's working directory is not the root of the backend application (or does not contain the database), the autodiscovery will fail.

### 4. **FastAPI Startup Error Propagation**
   - If `init_db()` fails (DB not found or writable), FastAPI may be "running" but all endpoints emit 500. Proxies will convert this to a 502 if the process dies or refuses connection.

### 5. **Container Networking**
   - As SQLite is file-based, network per se is not the issue—but only if volume mapping is correct and the backend can see the file as a local file.

### 6. **Lack of Error Feedback in Proxy/Frontend**
   - If the backend fails during startup or on all API requests due to missing/misconfigured DB, the upstream proxy will only see a 502 Bad Gateway.

---

# Recommendations / Steps to Fix

1. **Ensure the `SQLITE_DB` environment variable is set inside the backend container to the _absolute path_ of the database file as mounted.**
2. **Ensure Docker Compose mounts the SQLite DB file from the database container's data location to the identical path inside the backend container.**
   - For example:
     ```
     volumes:
       - ./database/myapp.db:/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db
     ```
3. **Verify backend container has full read & write access to the SQLite DB file.**
   - Run `check_sqlite_file.py` inside the backend exactly as the FastAPI user would execute it.
4. **Confirm that backend startup logs do NOT display "Could not locate SQLite database file" or permission errors.**
5. **Make sure working directory and all code paths are as expected—avoid relative paths where possible for database files.**
6. **If debugging via logs, add print statements or structured logging to database connection and all critical startup routines.**

---

# Summary Table

| Issue Category            | Details                                                          | How It Causes 502                |
|-------------------------- |------------------------------------------------------------------|----------------------------------|
| DB Path Misconfiguration  | `SQLITE_DB` unset/wrong or wrong mountpoint                     | FastAPI 500/crash -> Proxy 502   |
| DB File Missing           | Not mapped from host/db container                               | Unable to connect DB, FastAPI 500|
| File Permissions          | No read/write for backend user                                  | SQLite errors, backend fails     |
| Wrong Working Directory   | App looks for DB in wrong dir                                   | File not found, operational error|
| FastAPI Startup Failures  | `init_db()` can't connect/create tables                         | Crash, app unresponsive          |
| Networking Issues         | (Unlikely for SQLite if file is mounted correctly)               | Not root cause, but possible     |

---

# Conclusion

The **overwhelmingly likely cause** of persistent 502 Bad Gateway errors in this setup is that the backend container is either:
- Not receiving the correct path to the SQLite file,
- Not mounting the database file at all (so falls back to a non-existent file),
- Lacking file permissions to access/read/write the SQLite DB file.

**Action:** Focus on verifying Docker Compose/service mountpoints and `SQLITE_DB` env variable, and confirming DB file permissions as run by the backend's user.
