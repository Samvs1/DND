"""M23.7 what players see of the quests: the journal (main quest pinned with its routes, groups,
ticked steps, leads), the header and the Now card show the main objective, quest toasts on the
phone, Give on a keepsake. No text of a step that is not done yet may reach the browser."""

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page

from aidm.models.campaign import CampaignPlan
from aidm.models.character import Keepsake
from aidm.models.quest_events import QuestLeadAdded, QuestStepDone
from aidm.models.world import QuestLead
from aidm.models.world_events import KeepsakeGained
from aidm.rules.quest_plan import main_quests
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, go_tab, snap, start_with_screen

SNAPSHOT = "window.aidm.store.get().snapshot.state"


def _apply(live: LiveServer, events: list[Any]) -> None:
    assert live.app is not None and live.loop is not None
    table = live.app.state.registry.table

    async def go() -> None:
        table.apply_all(events)

    live.loop.call_soon_threadsafe(table.schedule, go)


def _main_id(page: Page) -> str:
    return page.evaluate(
        f"{SNAPSHOT}.quests.find((q) => q.kind === 'main' && q.state === 'active').id"
    )


def _plan(live: LiveServer) -> CampaignPlan:
    assert live.app is not None
    campaign = live.app.state.registry.table.state.campaign
    assert campaign is not None
    return campaign.plan


def _next_texts(live: LiveServer) -> list[str]:
    """Texts of every route step after the first (never sent before it is done)."""
    plan = _plan(live)
    out: list[str] = []
    for quest in main_quests(plan)[:1]:
        for route in quest.routes:
            out += [s.text for s in route.steps[1:]]
    return out


def test_journal_pins_the_main_quest_and_groups_the_rest(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    main = _main_id(host)
    route = main_quests(_plan(live_server))[0].routes[0]
    _apply(
        live_server,
        [
            QuestStepDone(quest_id=main, route_id=route.id, step=0, log_line="Explored it."),
            QuestLeadAdded(lead=QuestLead(quest_id="lead-x", text="Rumour of a sunken bell")),
        ],
    )
    go_tab(host, "journal")
    host.wait_for_selector("[data-testid=journal-main]")
    assert (
        host.locator("[data-testid=journal-main] .jr-main-label")
        .evaluate("(n) => n.firstChild.textContent")
        .lower()
        == "main quest"
    )
    host.wait_for_selector("[data-testid=journal-route-steps]", timeout=20000)
    first = host.locator("[data-testid=journal-route]").first
    assert route.steps[0].text in first.inner_text()
    host.wait_for_selector("[data-testid=journal-leads]")
    assert "Rumour of a sunken bell" in host.locator("[data-testid=journal-leads]").inner_text()
    assert host.locator("[data-testid=journal-offered] [data-testid=journal-quest]").count() >= 1
    html = host.locator("[data-testid=journal]").inner_html()
    for text in _next_texts(live_server):
        assert text not in html
    assert text_free(host.evaluate(f"JSON.stringify({SNAPSHOT})"), _next_texts(live_server))
    assert host.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    snap(host, shots_dir, "m23_journal", 390)
    assert errors == []


def text_free(blob: str, texts: list[str]) -> bool:
    data = json.dumps(json.loads(blob))
    return not any(json.dumps(t)[1:-1] in data for t in texts)


def test_header_and_now_card_show_the_main_objective(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    goal = host.evaluate(f"{SNAPSHOT}.quests.find((q) => q.kind === 'main').objective")
    assert goal
    screen.wait_for_selector("[data-testid=objective]:not([hidden])")
    assert goal in screen.locator("[data-testid=objective]").inner_text()
    assert "Missing Ledger" not in screen.locator("[data-testid=objective]").inner_text()
    assert goal in host.locator("[data-testid=now-goal]").inner_text()
    snap(screen, shots_dir, "m23_header", 1280)
    assert errors == []


def test_accepting_the_offer_toasts_and_a_step_toasts(
    browser: Browser, live_server: LiveServer
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.wait_for_selector("[data-testid=quest-offer]:not([hidden])", timeout=20000)
    host.click("[data-testid=quest-offer-accept]")
    host.wait_for_selector("[data-testid=quest-toast]:not([hidden])", timeout=20000)
    assert "The Missing Ledger - taken on" in host.locator("[data-testid=quest-toast]").inner_text()
    go_tab(host, "journal")
    host.wait_for_selector(
        "[data-testid=journal-active] [data-quest=missing-ledger]", timeout=20000
    )
    main = _main_id(host)
    route = main_quests(_plan(live_server))[0].routes[0]
    _apply(live_server, [QuestStepDone(quest_id=main, route_id=route.id, step=0, log_line="Done.")])
    host.wait_for_function(
        "document.querySelector('[data-testid=quest-toast]').textContent.includes('step done')",
        timeout=20000,
    )
    assert route.steps[0].text in host.locator("[data-testid=quest-toast]").inner_text()
    assert errors == []


def test_give_a_keepsake_to_a_person_here(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    assert host.viewport_size == PHONE
    pid = host.evaluate("window.aidm.store.get().players.find(p => p.name === 'Ann').creature_id")
    note = Keepsake(id="keepsake-oilcloth", name="Oilcloth Scrap", description="A charcoal map.")
    _apply(live_server, [KeepsakeGained(creature_id=pid, keepsake=note)])
    host.click("[data-testid=ct-tab-hero]")
    host.click("[data-testid=tab-inventory]")
    row = host.locator("[data-testid=keepsake]")
    row.wait_for(timeout=20000)
    assert "Keepsake" in row.locator("[data-testid=keepsake-note]").inner_text()
    host.click("[data-testid=give-keepsake]")
    snap(host, shots_dir, "m23_give", 390)
    host.locator("[data-testid=give-to]").first.click()
    host.wait_for_selector("[data-testid=keepsake]", state="detached", timeout=20000)
    assert errors == []
