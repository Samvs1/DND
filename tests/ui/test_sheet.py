"""Browser tests of the Hero tab: sheet, inventory, spellbook, level-up."""

from pathlib import Path

from playwright.sync_api import Browser, Page

from aidm.models.events import HpChanged, InventoryChanged
from aidm.rules.leveling import gain_xp, xp_for_level
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, go_tab, snap, start_table
from tests.ui.wizard_helpers import HeroSpec

WIZARD = HeroSpec(name="Elowen", race="elf", cls="wizard", background="sage", method="roll_4d6")
SHEET = "window.aidm.store.get().sheet?.sheet"
POTION = "potion-of-healing"


def _open(page: Page) -> None:
    page.wait_for_function(f"Boolean({SHEET})", timeout=20000)
    go_tab(page, "hero")
    page.wait_for_selector("[data-testid=sheet]:not([hidden])")
    page.wait_for_selector("[data-testid=sh-ac]")


def _text(page: Page, testid: str) -> str:
    return page.locator(f"[data-testid={testid}] .sh-stat-value").inner_text()


def test_drawer_numbers_match_the_server_sheet(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host)
    sheet = host.evaluate(SHEET)
    assert _text(host, "sh-ac") == str(sheet["ac"])
    assert _text(host, "sh-hp") == f"{sheet['hp']}/{sheet['max_hp']}"
    assert _text(host, "sh-speed") == f"{sheet['speed']} ft"
    assert _text(host, "sh-passive") == str(sheet["passive_perception"])
    scores = host.eval_on_selector_all(
        "[data-ability] .sh-score", "els => els.map((e) => Number(e.textContent))"
    )
    assert scores == [a["score"] for a in sheet["abilities"]]
    assert host.locator("[data-testid=sh-skills] li").count() == 18
    assert host.locator(".sh-skill.prof, .sh-skill.expert").count() >= 2
    assert host.locator("[data-testid=sh-attacks] li").count() >= 2
    wind = host.locator("[data-testid=sh-fa-line][data-feature=second-wind]")
    assert "Second Wind" in wind.inner_text() and "1 of 1 uses" in wind.inner_text()
    # The party card agrees with the sheet (both come from the same server state).
    snapshot_ac = host.evaluate(
        "window.aidm.store.get().snapshot.state.party.find(c => c.name === 'Brienne').ac"
    )
    assert snapshot_ac == sheet["ac"]
    snap(host, shots_dir, "controller_hero_overview", 390)
    # The sheet is a tab, not a modal: Play hides it and the Hero tab brings it back.
    go_tab(host, "play")
    assert host.locator("[data-testid=sheet]").is_hidden()
    go_tab(host, "hero")
    assert host.locator("[data-testid=sh-ac]").is_visible()
    assert errors == []


def test_equip_and_unequip_change_the_armor_class(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host)
    before = host.evaluate(f"{SHEET}.ac")
    host.click("[data-testid=tab-inventory]")
    host.wait_for_selector("[data-testid=inv-list]")
    assert "gp" in host.locator("[data-testid=sh-gold]").inner_text()
    assert "lb" in host.locator(".inv-meta").first.inner_text()
    host.click("[data-testid=unequip-shield]")
    host.wait_for_function(f"{SHEET}.ac === {before - 2}", timeout=20000)
    host.wait_for_selector("[data-testid=equip-shield]")
    snap(host, shots_dir, "controller_hero_inventory", 390)
    host.click("[data-testid=equip-shield]")
    host.wait_for_function(f"{SHEET}.ac === {before}", timeout=20000)
    host.click("[data-testid=drop-dungeoneers-pack]")
    host.wait_for_selector("[data-testid=drop-dungeoneers-pack]", state="detached", timeout=20000)
    assert errors == []


def test_potion_use_outside_combat(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host)
    pid = host.evaluate("window.aidm.store.get().players.find(p => p.name === 'Ann').creature_id")
    assert live_server.app is not None and live_server.loop is not None
    table = live_server.app.state.registry.table

    async def wound_and_give() -> None:
        hero = table.state.creatures[pid]
        table.apply_all(
            [
                InventoryChanged(creature_id=pid, item=POTION, delta=1, qty=1),
                HpChanged(creature_id=pid, delta=1 - hero.hp, new_hp=1),
            ]
        )

    live_server.loop.call_soon_threadsafe(table.schedule, wound_and_give)
    host.wait_for_function(f"{SHEET}.hp === 1", timeout=20000)
    host.click("[data-testid=tab-inventory]")
    host.wait_for_selector(f"[data-testid=use-{POTION}]")
    assert (
        host.locator(f"[data-testid=use-target-{POTION}] option").first.inner_text() == "yourself"
    )
    host.click(f"[data-testid=use-{POTION}]")
    host.wait_for_function(f"{SHEET}.hp > 1", timeout=20000)
    host.wait_for_selector(f"[data-testid=use-{POTION}]", state="detached", timeout=20000)
    assert errors == []


def test_wizard_spellbook_and_level_up(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = start_table(
        browser, live_server.base, PHONE, errors, specs=(HeroSpec(name="Brienne"), WIZARD)
    )
    _open(guest)
    guest.click("[data-testid=tab-spells]")
    guest.wait_for_selector("[data-testid=slot-tracker]")
    assert guest.locator("[data-testid=slot-count]").first.inner_text() == "2 of 2"
    assert guest.locator("[data-testid=spell-line]").count() >= 4
    assert guest.locator("[data-testid=sh-casting]").inner_text().startswith("Spell attack")
    snap(guest, shots_dir, "controller_hero_spellbook", 390)
    # A scripted XP grant offers level 2: the dialog lists the new spells to learn.
    pid = guest.evaluate("window.aidm.store.get().players.find(p => p.name === 'Bo').creature_id")
    assert live_server.app is not None
    table = live_server.app.state.registry.table

    async def grant() -> None:
        table.apply_all(gain_xp(table.state.creatures[pid], xp_for_level(2)))

    assert live_server.loop is not None
    live_server.loop.call_soon_threadsafe(table.schedule, grant)
    guest.wait_for_selector("[data-testid=levelup-badge]", timeout=20000)
    guest.click("[data-testid=levelup-button]")
    guest.wait_for_selector("[data-testid=lu-group-spells]", timeout=20000)
    submit = guest.locator("[data-testid=lu-submit]")
    assert submit.is_disabled()
    boxes = guest.locator("[data-testid=lu-group-spells] input[type=checkbox]")
    for i in range(2):
        boxes.nth(i).check()
    snap(guest, shots_dir, "controller_hero_levelup", 390)
    submit.click()
    guest.wait_for_function(f"{SHEET}.level === 2", timeout=20000)
    guest.wait_for_selector("[data-testid=levelup-dialog]:not([open])", state="attached")
    assert guest.locator("[data-testid=levelup-badge]:not([hidden])").count() == 0
    assert errors == []


def test_sheet_on_a_phone(browser: Browser, live_server: LiveServer, shots_dir: Path) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host)
    assert host.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    snap(host, shots_dir, "controller_sheet_overview", 390)
    host.click("[data-testid=tab-inventory]")
    host.wait_for_selector("[data-testid=inv-list]")
    assert host.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    snap(host, shots_dir, "controller_sheet_inventory", 390)
    host.click("[data-testid=tab-spells]")
    host.wait_for_selector("[data-testid=no-spells]")
    assert errors == []
