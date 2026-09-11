#!/usr/bin/env python3
"""Import Cyclades catalog JSON into the SQLite database used by ProcessLog."""
import json
import os
import sqlite3
import sys


def main():
    payload = json.load(sys.stdin)
    database = os.environ.get("DATABASE_PATH", "/data/processlog.db")
    db = sqlite3.connect(database)
    db.execute("PRAGMA foreign_keys = ON")
    # Demo data should disappear after the first real Cyclades refresh; manually
    # added entries (source=local) are intentionally preserved.
    db.execute("UPDATE machines SET active=0 WHERE source IN ('cyclades', 'demo')")
    db.execute("UPDATE tools SET active=0 WHERE source IN ('cyclades', 'demo')")
    for item in payload["machines"]:
        db.execute(
            """INSERT INTO machines(code,name,location,active,source) VALUES(?,?,?,1,'cyclades')
               ON CONFLICT(code) DO UPDATE SET name=excluded.name, location=excluded.location,
               active=1, source='cyclades' WHERE machines.source IN ('cyclades','demo')""",
            (item["code"], item["name"], item.get("location", "")),
        )
    for item in payload["tools"]:
        db.execute(
            """INSERT INTO tools(code,name,material,active,source) VALUES(?,?,?,1,'cyclades')
               ON CONFLICT(code) DO UPDATE SET name=excluded.name, material=excluded.material,
               active=1, source='cyclades' WHERE tools.source IN ('cyclades','demo')""",
            (item["code"], item["name"], item.get("material", "")),
        )
    db.commit()
    machine_count = db.execute("SELECT COUNT(*) FROM machines WHERE active=1").fetchone()[0]
    tool_count = db.execute("SELECT COUNT(*) FROM tools WHERE active=1").fetchone()[0]
    db.close()
    print(json.dumps({"machines": machine_count, "tools": tool_count, "status": "ok"}))


if __name__ == "__main__":
    main()
