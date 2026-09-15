import json
from datetime import datetime, timedelta, timezone

import pytest

from app.mes import MesCatalog, MesUnavailable


def test_mes_export_requires_fresh_valid_snapshot(tmp_path):
    path = tmp_path / "catalog.json"
    content = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "machines": [{"ref": "P1", "code": "P1", "name": "Lis"}],
               "tools": [{"ref": "MO1", "code": "MO1", "name": "Forma"}]}
    path.write_text(json.dumps(content), encoding="utf-8")
    catalog = MesCatalog(str(path), demo=False)
    assert catalog.get("machines", "P1")["name"] == "Lis"
    assert catalog.search("tools", "forma")[0]["ref"] == "MO1"
    content["generated_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(MesUnavailable, match="starší než 36 hodin"):
        catalog.get("machines", "P1")
