"""GET /api/tips: every tooltip as static JSON (M28.1)."""

from pathlib import Path

from starlette.testclient import TestClient

from aidm.rules.explain import all_tips
from tests.session.server_fixtures import make_app


def test_api_tips_serves_every_tip(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        res = client.get("/api/tips")
        assert res.status_code == 200 and "application/json" in res.headers["content-type"]
        tips = res.json()["tips"]
        assert set(tips) == set(all_tips())
        assert tips["spell:fire-bolt"]["title"] == "Fire Bolt"
        assert tips["word:half-cover"]["lines"][0].endswith("+2 AC.")
