#!/usr/bin/env python3
"""Atomic read-only Cyklades catalogue export for the specs Docker service.

Run on the Ubuntu host with the same spc-vm SSH alias as ProcessLog. The MES
credential remains in ~/cyclades-db.env on spc-vm, never in this repository.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sync_cyclades import ALL_MACHINES_QUERY, ALL_TOOLS_QUERY, sql_export


def normalize(rows: list[dict], kind: str) -> list[dict]:
    seen = set()
    result = []
    for row in rows:
        code = row["code"].strip()
        if not code or code in seen:
            raise ValueError(f"Duplicitní/prázdný MES kód v {kind}: {code!r}")
        seen.add(code)
        result.append({"ref": code, "code": code, "name": row["name"].strip()})
    if not result:
        raise ValueError(f"Cyklades vrátil prázdný seznam {kind}; starý export zůstává zachovaný.")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-target", default=os.getenv("CYCLEDES_SSH_TARGET", "spc-vm"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    machines = normalize(sql_export(args.ssh_target, ALL_MACHINES_QUERY), "machines")
    tools = normalize(sql_export(args.ssh_target, ALL_TOOLS_QUERY), "tools")
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "source": "SUIVPRO.dbo.MACHINE + SUIVPRO.dbo.LISTE_OUTILS",
               "machines": machines, "tools": tools}
    if not args.dry_run:
        target = Path(__file__).resolve().parent / "mes-export" / "catalog.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)
    print(json.dumps({"machines": len(machines), "tools": len(tools),
                      "status": "dry-run" if args.dry_run else "exported"}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Export Cyklades selhal: {exc}", file=sys.stderr)
        raise SystemExit(1)
