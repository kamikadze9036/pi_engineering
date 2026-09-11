#!/usr/bin/env python3
"""Create or update a ProcessLog user in the Docker SQLite database."""
import argparse
import os
import sqlite3
from werkzeug.security import generate_password_hash

parser = argparse.ArgumentParser()
parser.add_argument("--username", required=True)
parser.add_argument("--display-name", required=True)
parser.add_argument("--role", choices=("admin", "technolog"), required=True)
parser.add_argument("--password", required=True)
parser.add_argument("--deactivate", action="store_true")
args = parser.parse_args()

db = sqlite3.connect(os.environ.get("DATABASE_PATH", "/data/processlog.db"))
if args.deactivate:
    db.execute("UPDATE users SET active=0 WHERE username=?", (args.username,))
else:
    db.execute(
        """INSERT INTO users(username,display_name,password_hash,role,active,created_at) VALUES(?,?,?,?,1,datetime('now'))
           ON CONFLICT(username) DO UPDATE SET display_name=excluded.display_name,password_hash=excluded.password_hash,role=excluded.role,active=1""",
        (args.username, args.display_name, generate_password_hash(args.password), args.role),
    )
db.commit()
print(f"{'Deactivated' if args.deactivate else 'Ready'}: {args.username}")
