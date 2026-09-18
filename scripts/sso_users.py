#!/usr/bin/env python3
"""Správa účtů ProcessLogu po přechodu na SSO (spouštět v kontejneru: docker compose exec processlog python scripts/sso_users.py …).

Účty vznikají samy při prvním přihlášení přes Authentik a párují se podle username. Tento skript
slouží k přípravě migrace: výpis stávajících účtů, přejmenování username tak, aby odpovídal
Authentiku (historie zůstane u stejného id), deaktivace a zahození starých hashů hesel.
"""
import argparse
import os
import sqlite3

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd", required=True)
sub.add_parser("list", help="vypíše účty (id, username, jméno, role, aktivní, má lokální heslo)")
r = sub.add_parser("rename", help="změní username (např. na login z Authentiku), historie zůstane")
r.add_argument("old"); r.add_argument("new")
d = sub.add_parser("deactivate", help="lokálně deaktivuje účet"); d.add_argument("username")
a = sub.add_parser("activate", help="lokálně aktivuje účet"); a.add_argument("username")
dp = sub.add_parser("drop-passwords", help="zahodí lokální hashe hesel (po ověřeném přechodu na SSO)")
dp.add_argument("--yes", action="store_true")
args = parser.parse_args()

db = sqlite3.connect(os.environ.get("DATABASE_PATH", "/data/processlog.db"))
db.row_factory = sqlite3.Row
if args.cmd == "list":
    for u in db.execute("SELECT * FROM users ORDER BY username"):
        print(f"{u['id']:>3}  {u['username']:<20} {u['display_name']:<28} {u['role']:<9} {'aktivní' if u['active'] else 'neaktivní':<9} {'heslo' if u['password_hash'] != '!sso' else 'sso'}")
elif args.cmd == "rename":
    new = args.new.strip().lower()
    if db.execute("SELECT 1 FROM users WHERE username=?", (new,)).fetchone():
        raise SystemExit(f"username {new} už existuje – nejdřív sluč ručně")
    n = db.execute("UPDATE users SET username=? WHERE username=?", (new, args.old.strip().lower())).rowcount
    db.commit(); print(f"přejmenováno: {n}")
elif args.cmd in ("deactivate", "activate"):
    n = db.execute("UPDATE users SET active=? WHERE username=?", (1 if args.cmd == "activate" else 0, args.username.lower())).rowcount
    db.commit(); print(f"{args.cmd}: {n}")
elif args.cmd == "drop-passwords":
    rows = db.execute("SELECT username FROM users WHERE password_hash != '!sso'").fetchall()
    for u in rows:
        print(u["username"])
    if not args.yes:
        print(f"{len(rows)} účtů má lokální heslo; spusť s --yes")
    else:
        db.execute("UPDATE users SET password_hash='!sso' WHERE password_hash != '!sso'")
        db.commit(); print(f"zahozeno {len(rows)} hesel")
