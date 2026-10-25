"""M27.8: darkness and light are never hidden (GOAL_ITEMS "What players see"): the dark board
(dimmed zones, the Dark mark, the legend, a flame on the bearer), the phone's Dark / Lit badges,
the Torch lit chip and the free Put out light button, the darkvision eye, boon chips and the
item card's Use."""

from pathlib import Path

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.dark_helpers import OUT, darken, shot
from tests.ui.table_helpers import HD, PHONE, split_turn, start_fight, start_table

LEGEND = "Dark: heroes without darkvision attack into it at disadvantage."
DIMMED = "[data-testid=zone].dark"


def test_dark_board_and_phone_badges_in_a_fight(
    browser: Browser, combat_server: LiveServer
) -> None:
    errors: list[str] = []
    screen, host, guest = start_fight(browser, combat_server.base, errors, screen_size=HD)
    screen.wait_for_selector("[data-testid=init-entry].ally.current", timeout=30000)
    active, _other = split_turn(host, guest)
    me = darken(active, light=False, boons=("Rope=Athletics",))
    for page in (screen, _other):
        darken(page, light=False, boons=("Rope=Athletics",), me=me)
    # Unlit: every zone is dimmed with the Dark mark, the legend says what it means.
    screen.wait_for_selector(DIMMED)
    assert screen.locator("[data-testid=zone].glow").count() == 0
    assert LEGEND in screen.inner_text("[data-testid=hex-legend]")
    assert "Dark" in screen.locator(f"{DIMMED} [data-testid=hex-mark]").first.inner_text()
    # Darkvision is real race data: the elf rogue (Mira) has the eye, the human fighter does not.
    elf = screen.locator("[data-testid=party-card]", has_text="Elf Rogue")
    human = screen.locator("[data-testid=party-card]", has_text="Human Fighter")
    assert elf.locator("[data-testid=darkvision-eye]").count() == 1
    assert human.locator("[data-testid=darkvision-eye]").count() == 0
    assert screen.locator("[data-testid=init-entry] [data-testid=darkvision-eye]").count() == 1
    shot(screen, "01_dark_board_tv1920")
    # The phone: a Dark badge on the foe chips and on the Move list, the Light torch (bonus) slot.
    active.wait_for_selector("[data-testid=target-dark]")
    badges = active.locator("[data-testid=zone-badge]").all_inner_texts()
    assert "Dark" in badges and "Lit" not in badges
    assert active.locator("[data-testid=slot-light-torch]").inner_text().startswith("Light torch")
    assert active.locator("[data-testid=boon-chip]").all_inner_texts() == ["Rope: Athletics +"]
    assert active.locator("[data-testid=now-dark]").is_hidden()  # in a fight the board says it
    shot(active, "02_phone_dark_fight_phone390")
    active.locator("[data-testid=targets]").screenshot(
        path=str(OUT / "02b_target_dark_chip_phone390.png")
    )
    active.locator("[data-testid=slot-light-torch]").scroll_into_view_if_needed()
    shot(active, "02c_light_torch_slot_phone390")
    # Lit: the bearer's zone glows with a flame on the token, the chip and Put out light show.
    for page in (active, screen, _other):
        darken(page, light=True, boons=("Rope=Athletics",), me=me)
    screen.wait_for_selector("[data-testid=zone].glow [data-testid=token-flame]")
    assert screen.locator("[data-testid=zone].glow").count() == 1
    assert "Torch lit" in screen.inner_text("[data-testid=party]")
    shot(screen, "03_lit_board_tv1920")
    active.wait_for_selector("[data-testid=light-chip]")
    assert "Torch lit" in active.inner_text("[data-testid=light-chip]")
    assert "Lit" in active.locator("[data-testid=zone-badge]").all_inner_texts()
    assert active.locator("[data-testid=slot-light-torch]").count() == 0  # already lit
    active.click("[data-testid=slot-items]")
    active.click("[data-testid=put-out-light]")
    assert active.evaluate("window.__sent.at(-1)") == {
        "type": "submit_action",
        "text": "put out your light",
    }
    shot(active, "04_torch_lit_putout_phone390")
    assert errors == []


def test_out_of_a_fight_dark_scene_chip_and_card(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    door = {
        "id": "f1",
        "kind": "door",
        "name": "Cellar door",
        "description": "",
        "locked": "medium",
    }
    darken(host, light=False, features=[door])
    host.wait_for_selector("[data-testid=dark-badge]:not([hidden])")
    assert host.inner_text("[data-testid=now-dark]") == "It is dark here."
    assert host.locator("[data-kind=light]").inner_text().strip() == "Light a torch"
    host.click("[data-kind=light]")
    assert host.input_value("[data-testid=action-input]") == "light my torch"
    host.add_style_tag(
        content="[data-testid=quest-offer] { display: none !important; }"
    )  # only for the picture
    host.evaluate("window.scrollTo(0, 0)")
    shot(host, "05_dark_scene_phone390")
    assert host.locator("[data-testid=lock-badge]").inner_text() == "Locked"
    host.locator("[data-testid=ideas]").scroll_into_view_if_needed()
    host.locator("[data-testid=ideas]").screenshot(
        path=str(OUT / "08_idea_chips_lock_and_light_phone390.png")
    )
    darken(host, light=True, boons=("Rope=Athletics",))
    host.wait_for_selector("[data-testid=put-out-light]")
    assert host.locator("[data-kind=light]").count() == 0
    assert host.inner_text("[data-testid=now-dark]") == "Your torch lights the way."
    assert host.inner_text("[data-testid=dark-badge]").lower() == "lit"
    assert host.locator("[data-testid=boon-chip]").count() == 1
    host.click("[data-testid=put-out-light]")
    assert host.evaluate("window.__sent.at(-1)")["text"] == "put out your light"
    shot(host, "06_torch_lit_now_card_phone390")
    assert errors == []


CARD = (Path(__file__).parent / "js" / "item_card.js").read_text(encoding="utf-8")


def test_item_card_use_says_what_it_does_here(browser: Browser, live_server: LiveServer) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    page.evaluate(CARD, {"dark": False})
    assert page.locator("[data-testid=use-here-torch-light]").is_disabled()
    assert "Only works in a dark place." in page.inner_text("[data-testid=inv-use]")
    page.evaluate(CARD, {"dark": True})
    assert "Light this dark place" in page.inner_text("[data-testid=inv-use]")
    page.click("[data-testid=use-here-torch-light]")
    assert page.evaluate("window.__sent") == [{"type": "submit_action", "text": "Light the torch"}]
    page.click("[data-testid=inv-item][data-item=crowbar]")
    assert page.locator("[data-testid=use-here-target-crowbar-force] option").all_inner_texts() == [
        "Cellar door"
    ]
    page.click("[data-testid=use-here-crowbar-force]")
    force = "Force this open with the crowbar Cellar door"  # the menu's own label (M36.10b)
    assert page.evaluate("window.__sent.at(-1)")["text"] == force
    shot(page, "07_item_card_use_phone390")
