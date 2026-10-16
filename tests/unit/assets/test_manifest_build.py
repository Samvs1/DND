"""build_manifest.py: derivation, preservation, staleness and the drop-a-file flip (A1)."""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.testclient import TestClient

from aidm.server.asset_routes import add_asset_routes
from aidm.server.assets import AssetCatalog
from tests.asset_helpers import artless_manifest, image_placeholder
from tests.unit.scripts.helpers import load_script

bm = load_script("build_manifest")
REAL_WEB = bm.default_web_root()
KEY = "monster_token.barbed-devil"
PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
PNG = PNG_HEAD + (64).to_bytes(4, "big") * 2 + b"\x08\x06\x00\x00\x00"
FIELDS = {"kind", "file", "size", "transparent", "status", "prompt", "source", "license"}
KINDS = {
    "portrait",
    "monster_token",
    "item_icon",
    "spell_icon",
    "condition_icon",
    "zone_card",
    "zone_hex",
    "zone_icon",
    "surface_icon",
    "region_banner",
    "music",
    "sfx",
    "scene",
    "ui_icon",
    "ui_skin",  # M24 dark pixel skin: frame, ribbons, slots, stone
}


def _web(tmp_path: Path) -> Path:
    (tmp_path / "static").mkdir(parents=True)
    return tmp_path


def _manifest(web: Path) -> dict[str, dict[str, object]]:
    return json.loads(bm.manifest_path(web).read_text(encoding="utf-8"))


def test_committed_manifest_is_fresh() -> None:
    assert bm.run(REAL_WEB, check=True) == 0


def test_check_fails_when_stale(tmp_path: Path) -> None:
    web = _web(tmp_path)
    assert bm.run(web, check=True) == 1
    assert bm.run(web, check=False) == 0
    assert bm.run(web, check=True) == 0
    path = bm.manifest_path(web)
    text = path.read_text(encoding="utf-8").replace("placeholder", "real", 1)
    path.write_text(text, encoding="utf-8")
    assert bm.run(web, check=True) == 1


def test_entries_have_the_documented_fields_and_v1_files_are_real(tmp_path: Path) -> None:
    manifest = bm.build_manifest(REAL_WEB)
    entry = manifest["portrait.class.fighter"]
    assert entry["status"] == "real" and entry["source"] == "v1" and entry["license"]
    assert entry["size"] == [824, 490]
    token = manifest[KEY]
    assert token["transparent"] is True and set(token) >= FIELDS  # generated adds review fields
    bare = artless_manifest(tmp_path)  # every picture is real art now: build one without any
    placeholder = bare[image_placeholder(bare)]
    assert placeholder["status"] == "placeholder" and set(placeholder) == FIELDS
    assert {e["kind"] for e in manifest.values()} == KINDS


def test_rebuild_preserves_prompt_source_and_license(tmp_path: Path) -> None:
    web = _web(tmp_path)
    bm.run(web, check=False)
    data = _manifest(web)
    data[KEY].update({"prompt": "a goblin", "source": "generated:test", "license": "CC0"})
    bm.manifest_path(web).write_text(json.dumps(data), encoding="utf-8")
    bm.run(web, check=False)
    entry = _manifest(web)[KEY]
    assert (entry["prompt"], entry["source"], entry["license"]) == (
        "a goblin",
        "generated:test",
        "CC0",
    )


def test_dropping_a_file_flips_the_entry_to_real_and_serves_it(tmp_path: Path) -> None:
    web = _web(tmp_path)
    bm.run(web, check=False)
    entry = _manifest(web)[KEY]
    assert entry["status"] == "placeholder"
    catalog = AssetCatalog(web)
    assert catalog.url(KEY).startswith("/assets/placeholder/monster_token/")
    target = web / "static" / str(entry["file"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PNG)
    bm.run(web, check=False)
    flipped = _manifest(web)[KEY]
    assert flipped["status"] == "real" and flipped["size"] == [64, 64]
    assert flipped["source"] == "manual"
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=web / "static"), name="static")
    add_asset_routes(app, catalog)
    url = catalog.url(KEY)
    assert url == f"/static/{entry['file']}"
    http = TestClient(app)
    served = http.get(url)
    assert served.status_code == 200 and served.content == PNG
    assert http.get("/api/assets/manifest").json()[KEY] == url


def test_removed_data_keys_leave_the_manifest(tmp_path: Path) -> None:
    web = _web(tmp_path)
    bm.run(web, check=False)
    data = _manifest(web)
    data["monster_token.long-gone"] = data[KEY]
    bm.manifest_path(web).write_text(json.dumps(data), encoding="utf-8")
    bm.run(web, check=False)
    assert "monster_token.long-gone" not in _manifest(web)


def test_gate_script_runs_the_manifest_check() -> None:
    gate = (REAL_WEB.parent.parent / "scripts" / "gate.ps1").read_text(encoding="utf-8")
    assert "build_manifest.py --check" in gate
