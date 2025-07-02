# 502 Bad Gateway Error - Full Diagnostic Summary

_This document provides a comprehensive diagnosis for persistent 502 Bad Gateway errors observed in the backend container of the GridTactix application, with emphasis on code, environment, Docker, file configuration, and operational factors._

---

## 1. FastAPI Server Startup & Health

- **Health Endpoint**: The FastAPI backend at `/` is designed to return `{ "message": "Healthy" }` if running. A 502 error at this endpoint means the server failed to start or crashed post-initialization; commonly, this is due to initialization or database errors.
- **Entrypoint**: The application is started by running `uvicorn` on `0.0.0.0`, port `${PORT}` or `8000` by default. Any failure in initialization, especially database-related, will prevent FastAPI from accepting requests, resulting in a 502 seen by proxy layers.

## 2. SQLite Database Discovery & Access

- **Path Resolution**: Both `main.py` and `check_sqlite_file.py` use `locate_db_file()` to search for the SQLite database in the following order:
    1. The path provided via the `SQLITE_DB` environment variable (should be absolute and **set inside the backend container**)
    2. `app.db` in the backend's current working directory
    3. The canonical path: `/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db`
- **Fallback Risk**: If the intended DB file is not found (or not mapped by Docker), the application falls back to `app.db` in the container's current working dir, which very likely does not exist or is empty, making the backend unsuitable for handling requests.

## 3. Volume Mounts and File Permissions

- **Volume Mounts**: If Docker Compose or the deployment does not mount the SQLite DB file from the database container’s storage *into* the backend container at the *identical path*, the backend will not see a usable DB file, and all SQL operations will fail.
- **File Permissions**: Backend code checks for both read and write access to the discovered DB file. If permissions differ (e.g., file created by root, backend runs as non-root user), FastAPI will throw errors at startup (detected by `check_sqlite_file.py`, but could fail at runtime if user differs).

## 4. Docker/Deployment Network & Configuration

Common sources of 502 errors:
- **Backend process not running**: Typically due to code error, DB missing/unwritable, or uncaught exception in `init_db()` or startup.
- **Database file not mapped or reachable**: If the volume is not correctly specified, or the `SQLITE_DB` env var is wrong or unset, backend cannot find the DB file.
- **Proxy misrouting**: Reverse proxies or other networking components will report 502 if the backend process is not exposing its service or returns only 500s.

## 5. Working Directory and Entrypoint/Startup

- **Relative Path Risk**: Any mismatch in container working directory vs. code or Docker Compose expectations will break file path resolution (since `os.getcwd()` is used). Hardcoded and absolute paths are present, so misconfiguration is easy to introduce.

## 6. Application and Init Logic

- The backend runs `init_db()` on startup. If this cannot access the DB and initialize tables (file missing, unreadable, unwriteable), the server will likely fail or return a 500 on every endpoint.
- Server logs should be checked for "Could not locate SQLite database file" or operational errors immediately on startup.

---

## **Root Causes and Plausibility Overview**

| Category              | Possible Causes                                                        | How It Causes 502?              |
|-----------------------|------------------------------------------------------------------------|---------------------------------|
| DB Path Misconfig     | `SQLITE_DB` unset, set incorrectly, or Docker mount mismatch           | Backend can't find DB, 500/502  |
| File Permissions      | Backend user lacks R/W permission on mapped file                       | SQLite error, backend crash     |
| File Missing          | Volume not mounted, DB file absent at specified path                   | Startup/init fails, 502         |
| Working Directory     | Entrypoint sets unexpected CWD, relative path fails                    | File not found, crash           |
| FastAPI Crash         | Any uncaught DB or OS error in `init_db()`                             | Server crash, 502 from proxy    |
| Proxy or Port Mismap  | Backend listens on wrong port/address/not exposed by Docker            | Proxy receives connection reset |
| Network (rare)        | Not a usual issue for SQLite, unless file mapping depends on it        | File inaccessible, backend dies |

---

## **Evidence in Workspace / Tools**

- `check_sqlite_file.py`: Explicitly checks for DB file and permissions—`post_process_status.lock` with `SUCCESS` means test passed **once**, but runtime context could differ (different user, missing after restart, etc).
- `main.py`: Contains fallbacks and error-prints, but "fallback to app.db" nearly always signifies backend will later error.
- No indications of alternative DB service, secrets, or dynamic DB discovery—**absolute path correctness and volume mapping are mandatory**.

---

## **Minimal Diagnostic Checklist**

1. **Check `SQLITE_DB` env in backend container is set, matches volume mount path.**
2. **Confirm Docker Compose mounts the DB file to correct path inside backend container.**
3. **Validate backend user (not root?) has R/W permission on DB file at that path.**
4. **Review FastAPI logs at container start for errors regarding DB file absence or permission errors.**
5. **Check container's working directory (on startup) matches path logic.**
6. **Add or review logs in `init_db()`, inspect why server refuses to start if errors are present.**

---

## **Conclusion**

- The **overwhelmingly likely cause** of persistent 502 Bad Gateway errors is that the backend cannot see (missing/mismapped), or cannot access (permissions), the SQLite database file at the expected absolute path.
- **Recommended Fixes**:
    1. Set `SQLITE_DB` environment variable correctly in backend container.
    2. Map DB file/volume at exact same path between database and backend.
    3. Check/adjust file permissions for backend's runtime user.
    4. Scan and improve startup logs and error messages for easier future debugging.

---
Task performed: Full review of container health, deployment config, volume mounting, permissions, code, and expected server health endpoints. Refer to this document for quick visual diagnosis of future 502 gateway errors.
