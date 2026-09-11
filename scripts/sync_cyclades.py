#!/usr/bin/env python3
"""Read Cyclades catalogues via spc-vm and load them into the running Docker app.

No Cyclades password is stored here. The remote command uses the existing
~/cyclades-db.env file on spc-vm.
"""
import argparse
import json
import os
import shlex
import subprocess
import sys

SQLCMD_IMAGE = "mcr.microsoft.com/mssql-tools"
MACHINES_QUERY = "SET NOCOUNT ON; SELECT MAC_REFMAC, MAC_LIBMAC, '' FROM dbo.MACHINE WHERE MAC_REFMAC LIKE 'P%' AND MAC_LIBMAC IS NOT NULL ORDER BY MAC_REFMAC;"
TOOLS_QUERY = "SET NOCOUNT ON; SELECT OUT_REFOUT, OUT_LIBOUT, COALESCE(OUT_TYPEOUT,'') FROM dbo.LISTE_OUTILS WHERE OUT_REFOUT LIKE 'MO%' AND OUT_LIBOUT IS NOT NULL ORDER BY OUT_REFOUT;"


def sql_export(target, query):
    command = (
        "docker run --rm --env-file \"$HOME/cyclades-db.env\" " + SQLCMD_IMAGE + " /bin/sh -c " +
        shlex.quote(
            "/opt/mssql-tools/bin/sqlcmd -S \"$CYCLADES_DB_HOST,$CYCLADES_DB_PORT\" "
            "-U \"$CYCLADES_DB_USER\" -P \"$CYCLADES_DB_PASSWORD\" -d SUIVPRO -C -W -h -1 -s '|' -Q " + shlex.quote(query)
        )
    )
    # On spc-vm Cyclades is directly reachable. Development machines use the
    # preconfigured SSH alias to execute this same read-only command remotely.
    runner = ["/bin/sh", "-lc", command] if target == "local" else ["ssh", target, command]
    result = subprocess.run(runner, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Cyclades export failed")
    rows = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 3 and parts[0] and parts[1]:
            rows.append({"code": parts[0], "name": parts[1], "location": parts[2]})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-target", default=os.environ.get("CYCLEDES_SSH_TARGET", "spc-vm"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    machines = sql_export(args.ssh_target, MACHINES_QUERY)
    tools = sql_export(args.ssh_target, TOOLS_QUERY)
    # OUT_TYPEOUT is shown in the tool detail slot in the ProcessLog catalogue.
    for tool in tools:
        tool["material"] = tool.pop("location", "")
    payload = {"machines": machines, "tools": tools}
    if args.dry_run:
        print(json.dumps({"machines": len(machines), "tools": len(tools), "status": "dry-run"}))
        return
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "processlog", "python", "scripts/import_catalog.py"],
        input=json.dumps(payload), text=True, capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "SQLite import failed")
    print(result.stdout.strip())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Synchronizace selhala: {error}", file=sys.stderr)
        sys.exit(1)
