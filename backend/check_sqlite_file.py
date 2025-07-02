import os
import sys

def locate_db_file():
    possible_paths = [
        os.environ.get("SQLITE_DB"),
        os.path.join(os.getcwd(), "app.db"),
        "/home/kavia/workspace/code-generation/gridtactix-118083-118092/database/myapp.db"
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    return None

def check_database_file():
    db_file = locate_db_file()
    if not db_file:
        print("ERROR: Could not locate SQLite database file (checked app.db and env var SQLITE_DB).")
        sys.exit(1)
    errors = []
    if not os.access(db_file, os.R_OK):
        errors.append("not readable")
    if not os.access(db_file, os.W_OK):
        errors.append("not writable")
    if errors:
        print(f"ERROR: Database file '{db_file}' is " + " and ".join(errors) + ".")
        sys.exit(2)
    print(f"SUCCESS: Database file '{db_file}' exists and is readable/writable.")

if __name__ == "__main__":
    check_database_file()
