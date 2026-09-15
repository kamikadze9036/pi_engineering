"""Read-only MES catalogue adapter. The export mode reads an atomic host export.

The catalogue is never imported into the specs PostgreSQL database. `ref` is
temporarily the MES code used by the existing ProcessLog SQL; verify the stable
MES identifier on spc-vm before importing real prescriptions.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class MesUnavailable(Exception):
    pass


class MesCatalog:
    def __init__(self, path: str | None = None, demo: bool | None = None):
        self.demo = os.getenv("SPECS_DEMO_MODE", "false").lower() == "true" if demo is None else demo
        default = Path(__file__).resolve().parents[2] / "mes" / "demo_catalog.json"
        self.path = Path(path or os.getenv("SPECS_MES_CATALOG_PATH", str(default)))

    def load(self) -> dict:
        if not self.demo and not self.path.exists():
            raise MesUnavailable("Export Cyklades není dostupný. Připojte MES export na Ubuntu hostiteli.")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MesUnavailable("Číselník Cyklades nelze přečíst.") from exc
        if not self.demo:
            try:
                generated = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - generated.astimezone(timezone.utc)
            except (KeyError, ValueError, TypeError) as exc:
                raise MesUnavailable("Export Cyklades nemá platné datum.") from exc
            if age.total_seconds() > 36 * 3600:
                raise MesUnavailable("Export Cyklades je starší než 36 hodin.")
        if not isinstance(data.get("machines"), list) or not isinstance(data.get("tools"), list):
            raise MesUnavailable("Export Cyklades nemá seznam strojů a nástrojů.")
        return data

    def search(self, kind: str, q: str = "") -> list[dict]:
        if kind not in ("machines", "tools"):
            raise ValueError(kind)
        items = self.load()[kind]
        needle = q.casefold().strip()
        return [item for item in items if needle in (item["code"] + " " + item["name"]).casefold()][:50]

    def get(self, kind: str, ref: str) -> dict | None:
        return next((item for item in self.load()[kind] if item["ref"] == ref), None)
