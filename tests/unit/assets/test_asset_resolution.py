"""Every data-derived asset key resolves to a real file or a valid SVG placeholder (A1, A.5)."""

import json
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from aidm.data.class_defs import class_defs
from aidm.data.condition_defs import condition_defs
from aidm.data.encounter_monsters import encounter_monsters
from aidm.data.item_catalogue import ItemCategory
from aidm.data.race_defs import race_defs
from aidm.data.spell_defs import shipped_spell_ids
from aidm.server.app import WEB_DIR, create_app
from aidm.server.asset_keys import AUDIO_KINDS, split_key
from aidm.server.assets import AssetCatalog, asset_url
from aidm.server.settings import server_settings_from_env
from tests.asset_helpers import image_placeholder

MANIFEST = json.loads((WEB_DIR / "static" / "assets" / "manifest.json").read_text(encoding="utf-8"))
SVG_NS = "{http://www.w3.org/2000/svg}svg"


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    saves = tmp_path_factory.mktemp("saves")
    settings = server_settings_from_env({"AIDM_FAKE_LLM": "1"}, saves_dir=saves)
    settings = replace(settings, llm=replace(settings.llm, log_path=None))
    return TestClient(create_app(settings))


def _check(client: TestClient, key: str) -> None:
    assert key in MANIFEST, f"{key} is missing from the manifest"
    url = asset_url(key)
    kind, _ = split_key(key)
    if kind in AUDIO_KINDS:
        assert url == "" or (WEB_DIR / url.removeprefix("/")).is_file()
        return
    if url.startswith("/static/"):
        assert (WEB_DIR / url.removeprefix("/")).is_file()
        return
    assert url.startswith(f"/assets/placeholder/{kind}/") and url.endswith(".svg")
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "max-age" in response.headers["cache-control"]
    root = ET.fromstring(response.text)
    assert root.tag == SVG_NS
    assert root.get("viewBox")


@pytest.mark.parametrize("cls", [c.index for c in class_defs().all()])
def test_class_keys_resolve(client: TestClient, cls: str) -> None:
    _check(client, f"portrait.class.{cls}")
    _check(client, f"portrait.icon.{cls}")


@pytest.mark.parametrize("race", [r.index for r in race_defs().all()])
@pytest.mark.parametrize("sex", ["f", "m"])
def test_race_keys_resolve(client: TestClient, race: str, sex: str) -> None:
    _check(client, f"portrait.race.{race}.{sex}")


@pytest.mark.parametrize("monster", [m.index for m in encounter_monsters().all()])
def test_monster_keys_resolve(client: TestClient, monster: str) -> None:
    _check(client, f"monster_token.{monster}")


@pytest.mark.parametrize("category", [c.value for c in ItemCategory])
def test_item_category_keys_resolve(client: TestClient, category: str) -> None:
    _check(client, f"item_icon.{category}")


@pytest.mark.parametrize("spell", sorted(shipped_spell_ids()))
def test_spell_keys_resolve(client: TestClient, spell: str) -> None:
    _check(client, f"spell_icon.{spell}")


@pytest.mark.parametrize("condition", [c.index for c in condition_defs().all()])
def test_condition_keys_resolve(client: TestClient, condition: str) -> None:
    _check(client, f"condition_icon.{condition}")


def test_every_manifest_key_resolves(client: TestClient) -> None:
    for key in MANIFEST:
        _check(client, key)


def test_manifest_endpoint_lists_every_key_with_a_url(client: TestClient) -> None:
    response = client.get("/api/assets/manifest")
    assert response.status_code == 200
    urls = response.json()
    assert set(urls) == set(MANIFEST)
    assert urls["portrait.class.fighter"].startswith("/static/")
    placeholder = image_placeholder(MANIFEST)
    kind = MANIFEST[placeholder]["kind"]
    assert urls[placeholder].startswith(f"/assets/placeholder/{kind}/")
    assert urls["music.social"] == ""


UNKNOWN_PATHS = [
    "/assets/placeholder/nonsense/whatever.svg",
    "/assets/placeholder/portrait/%20%3Cscript%3E.svg",
    "/assets/placeholder/monster_token/not-a-monster.svg",
    "/assets/placeholder/spell_icon/" + "x" * 400 + ".svg",
    "/assets/placeholder/zone_card/unknown-terrain.svg",
]


@pytest.mark.parametrize("path", UNKNOWN_PATHS)
def test_unknown_keys_get_a_generic_valid_svg(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert ET.fromstring(response.text).tag == SVG_NS


def test_asset_url_for_unknown_key_is_a_placeholder_and_audio_is_silence() -> None:
    assert asset_url("monster_token.no-such-beast").startswith("/assets/placeholder/monster_token/")
    assert asset_url("nothing") == "/assets/placeholder/nothing/unknown.svg"
    assert asset_url("music.no-such-state") == ""
    assert asset_url("sfx.no-such-sound") == ""


def test_missing_manifest_still_resolves_to_placeholders(tmp_path: Path) -> None:
    catalog = AssetCatalog(tmp_path)
    assert catalog.url("portrait.class.fighter").startswith("/assets/placeholder/portrait/")
    assert catalog.urls() == {}
