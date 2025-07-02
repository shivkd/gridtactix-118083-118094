import os
import sys

DB_FILE = "app.db"  # This should match usage in main.py

def check_database_file():
    if not os.path.exists(DB_FILE):
        print(f"ERROR: Database file '{DB_FILE}' does NOT exist.")
        sys.exit(1)
    errors = []
    if not os.access(DB_FILE, os.R_OK):
        errors.append("not readable")
    if not os.access(DB_FILE, os.W_OK):
        errors.append("not writable")
    if errors:
        print(f"ERROR: Database file '{DB_FILE}' is " + " and ".join(errors) + ".")
        sys.exit(2)
    print(f"SUCCESS: Database file '{DB_FILE}' exists and is readable/writable.")

if __name__ == "__main__":
    check_database_file()
