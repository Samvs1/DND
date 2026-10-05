"""Browser test of hero files: export on the finished sheet, import on the first step (M7.3b)."""

import json
from pathlib import Path

from playwright.sync_api import Browser, ViewportSize

from tests.ui.conftest import LiveServer
from tests.ui.wizard_helpers import HeroSpec, fill_wizard, join

WIDE = ViewportSize(width=1280, height=900)


def test_export_then_import_a_hero_file(
    browser: Browser, live_server: LiveServer, tmp_path: Path
) -> None:
    errors: list[str] = []
    ann = browser.new_context(viewport=WIDE).new_page()
    ann.on("pageerror", lambda exc: errors.append(str(exc)))
    join(ann, live_server.base, "Ann")
    fill_wizard(ann, HeroSpec(name="Brienne"))
    ann.click("[data-testid=create-hero]")
    ann.wait_for_selector("[data-testid=sheet-summary]")
    with ann.expect_download() as download:
        ann.click("[data-testid=export-hero]")
    saved = tmp_path / download.value.suggested_filename
    download.value.save_as(saved)
    assert saved.name == "brienne.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["format"] == "aidm.character"

    bo = browser.new_context(viewport=WIDE).new_page()
    bo.on("pageerror", lambda exc: errors.append(str(exc)))
    join(bo, live_server.base, "Bo")
    bo.wait_for_selector("[data-testid=import-block]")
    bad = tmp_path / "broken.json"
    bad.write_text("{not a hero", encoding="utf-8")
    bo.set_input_files("[data-testid=import-file]", str(bad))
    bo.wait_for_selector("[data-testid=import-errors]")
    assert "not a hero saved from this game" in bo.inner_text("[data-testid=import-errors]")
    bo.set_input_files("[data-testid=import-file]", str(saved))
    bo.wait_for_selector("[data-testid=sheet-summary]")
    assert bo.inner_text("[data-testid=sheet-name]") == "Brienne"
    bo.click("[data-testid=hero-ready]")
    bo.wait_for_selector("[data-testid=roster]")
    assert errors == []
