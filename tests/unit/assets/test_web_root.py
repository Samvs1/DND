"""`AIDM_WEB_ROOT` serves another copy of aidm/web; missing art becomes placeholders (A3)."""

import shutil
from dataclasses import replace
from pathlib import Path

from starlette.testclient import TestClient

from aidm.server.app import WEB_DIR, create_app
from aidm.server.settings import server_settings_from_env


def _client(tmp_path: Path, env: dict[str, str]) -> TestClient:
    settings = server_settings_from_env({"AIDM_FAKE_LLM": "1", **env}, saves_dir=tmp_path / "saves")
    return TestClient(create_app(replace(settings, llm=replace(settings.llm, log_path=None))))


def test_web_root_defaults_to_none_and_reads_the_env() -> None:
    assert server_settings_from_env({}).web_root is None
    assert server_settings_from_env({"AIDM_WEB_ROOT": " "}).web_root is None
    assert server_settings_from_env({"AIDM_WEB_ROOT": "x/web"}).web_root == Path("x/web")


def test_web_root_override_hides_real_art_and_serves_placeholders(tmp_path: Path) -> None:
    web = tmp_path / "web"
    shutil.copytree(WEB_DIR, web, ignore=shutil.ignore_patterns("img"))
    with _client(tmp_path, {"AIDM_WEB_ROOT": str(web)}) as hidden:
        urls = hidden.get("/api/assets/manifest").json()
        assert urls and not [u for u in urls.values() if u.startswith("/static/img")]
        assert any(u.startswith("/assets/placeholder/") for u in urls.values())
        assert hidden.get("/static/img/portraits/Cleric_p_icon.png").status_code == 404
        assert hidden.get("/").status_code == 200
    with _client(tmp_path, {}) as normal:
        real = normal.get("/api/assets/manifest").json()
        assert any(u.startswith("/static/img") for u in real.values())
        assert normal.get("/static/img/portraits/Cleric_p_icon.png").status_code == 200
