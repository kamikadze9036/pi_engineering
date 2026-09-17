#!/usr/bin/env python3
"""Sync the raw-material catalogue (Vstupní materiál dropdown) from Cyklades.

Run on spc-vm (or the Ubuntu host, same --ssh-target convention as
export_cyclades.py). Reads distinct raw materials from the materials master
(SUIVPRO.dbo.CONSOMMABLES, TYPC_TYPE=1 filtered to KG/G units — see
scripts/sync_cyclades.py for why) and pushes them into the running specs app
via its own API — additive only, never removes a material the admin added by
hand or one Cyklades stopped listing.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sync_cyclades import MATERIALS_QUERY, sql_export


def api_call(base_url: str, path: str, method: str, body: dict | None = None, cookies: str = "", csrf: str = ""):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if cookies:
        headers["Cookie"] = cookies
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = Request(f"{base_url}{path}", method=method, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(request, timeout=15) as response:
            return response, json.loads(response.read() or "null")
    except HTTPError as exc:
        raise RuntimeError(f"{method} {path} selhalo ({exc.code}): {exc.read().decode(errors='replace')}") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-target", default=os.getenv("CYCLEDES_SSH_TARGET", "local"))
    parser.add_argument("--base-url", default=os.getenv("SPECS_BASE_URL", "http://localhost:8082"))
    parser.add_argument("--admin-password", default=os.getenv("SPECS_ADMIN_PASSWORD"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = sql_export(args.ssh_target, MATERIALS_QUERY)
    names = sorted({row["name"].strip() for row in rows if row["name"].strip()})
    if args.dry_run:
        print(json.dumps({"materials": len(names), "status": "dry-run"}))
        return
    if not args.admin_password:
        raise RuntimeError("Chybí SPECS_ADMIN_PASSWORD (env nebo --admin-password).")

    login_response, login_body = api_call(args.base_url, "/api/v1/auth/login", "POST",
                                          {"username": "admin", "password": args.admin_password})
    cookies = "; ".join(header.split(";", 1)[0] for header in (login_response.headers.get_all("Set-Cookie") or []))
    _, result = api_call(args.base_url, "/api/v1/materials/sync", "POST", {"names": names},
                         cookies=cookies, csrf=login_body["csrf"])
    print(json.dumps({"materials_found": len(names), **result}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Synchronizace materiálů selhala: {exc}", file=sys.stderr)
        raise SystemExit(1)
