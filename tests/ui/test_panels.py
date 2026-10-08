"""Browser tests of the phone panels (M7.6, M11.4): journal, map, shop, host, settings."""

from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, ViewportSize

from aidm.models.events import GoldChanged
from aidm.models.world import WorldNpc
from aidm.models.world_events import NpcIntroduced
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE, go_tab, snap, start_table, start_with_screen

FULL_HD = ViewportSize(width=1920, height=1080)
SNAPSHOT = "window.aidm.store.get().snapshot.state"
NO_SCROLL = "document.documentElement.scrollWidth <= window.innerWidth"


TAB_OF = {
    "journal": "journal",
    "map": "journal",
    "shop": "play",
    "host": "more",
    "settings": "more",
}


def _open(page: Page, name: str) -> None:
    """Open a panel: journal and map are tabs of the phone, shop, host and settings are dialogs."""
    if name in ("journal", "map"):
        go_tab(page, "journal")
        page.click(f"[data-testid=jtab-{name}]")
        page.wait_for_selector(f"[data-testid={name}]:not([hidden])")
        return
    go_tab(page, TAB_OF[name])
    page.click(f"[data-testid=open-{name}]")
    page.wait_for_selector(f"[data-testid={name}][open]")


def _close(page: Page, name: str) -> None:
    page.click(f"[data-testid={name}-close]")
    page.wait_for_selector(f"[data-testid={name}]:not([open])", state="attached")
    assert page.evaluate("document.activeElement?.dataset.testid") == f"open-{name}"


def _fits(page: Page, name: str) -> None:
    """The panel and the page never scroll sideways (a responsive check at the current size)."""
    assert page.evaluate(NO_SCROLL)
    assert page.evaluate(
        f"(() => {{ const d = document.querySelector('[data-testid={name}]');"
        " return d.scrollWidth <= d.clientWidth + 1; })()"
    )


def _journal(page: Page, shots: Path, width: int) -> None:
    _open(page, "journal")
    page.wait_for_selector("[data-testid=journal-quest]")
    titles = page.locator("[data-testid=journal-quest] strong").all_inner_texts()
    assert "The Missing Ledger" in titles
    states = page.eval_on_selector_all(
        "[data-testid=journal-quest]", "els => els.map((e) => e.dataset.state)"
    )
    assert states and set(states) <= {"active", "offered", "completed", "failed"}
    giver = page.locator("[data-testid=journal-quest] .jr-giver").first.inner_text()
    assert giver.startswith("Given by ")
    assert page.locator("[data-testid=journal-facts]").count() + page.locator(".hint").count() > 0
    _fits(page, "journal")
    snap(page, shots, "controller_journal_tab", width)


def _map(page: Page, shots: Path, width: int) -> None:
    _open(page, "map")
    page.wait_for_selector("[data-testid=map-node]")
    here = page.locator("[data-testid=map-node][data-state=here]")
    assert here.count() == 1
    current = page.evaluate(f"{SNAPSHOT}.scene.name")
    assert current in (here.text_content() or "")
    fogged = page.locator("[data-testid=map-node][data-state=fogged]")
    assert fogged.count() >= 1
    assert "Unexplored" in (fogged.first.text_content() or "")
    assert page.locator("[data-testid=map-banner] img").get_attribute("src")
    assert page.locator("[data-testid=map-travel]").count() >= 1
    _fits(page, "map")
    snap(page, shots, "controller_map_tab", width)


def test_journal_and_map_show_the_campaign(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _journal(host, shots_dir, 390)
    _map(host, shots_dir, 390)
    assert errors == []


def test_travel_from_the_map_opens_a_vote(browser: Browser, live_server: LiveServer) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host, "map")
    button = host.locator("[data-testid=map-travel]:not([disabled])").first
    node = button.get_attribute("data-node")
    assert node
    start = host.evaluate(f"{SNAPSHOT}.scene.node_id")
    button.click()
    host.wait_for_selector("[data-testid=pane-play]:not([hidden])")  # travelling returns to Play
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    assert host.evaluate(f"{SNAPSHOT}.vote.kind") == "travel"
    guest.wait_for_selector("[data-testid=vote-ready]", timeout=20000)
    guest.click("[data-testid=vote-ready]")
    host.wait_for_function(f"{SNAPSHOT}.scene.node_id === {node!r}", timeout=30000)
    assert start != node
    # The map follows the party: the new place is current and the old one is now visited.
    nodes = host.evaluate(f"{SNAPSHOT}.map.nodes")
    assert [n["id"] for n in nodes if n["current"]] == [node]
    assert any(n["id"] == start and n["visited"] for n in nodes)
    assert errors == []


def test_graph_marks_a_locked_gateway_and_wraps_names(
    browser: Browser, live_server: LiveServer
) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    result = page.evaluate(
        """async () => {
          const { buildGraph, wrapName } = await import('/web/js/map/graph.js');
          const map = {
            nodes: [
              { id: 'a', name: 'Harbour', visited: true, locked: false, current: true },
              { id: 'b', name: 'Unexplored', visited: false, locked: false, current: false },
              { id: 'c', name: 'The Sunken Vestry of Gulls', visited: false,
                locked: true, current: false },
            ],
            edges: [['a', 'b'], ['a', 'c']],
          };
          const svg = buildGraph(map, new Map([['b', 'Boathouse']]));
          const nodes = [...svg.querySelectorAll('[data-testid=map-node]')];
          const states = nodes.map((n) => [n.dataset.node, n.dataset.state]);
          return { states, text: svg.textContent, lines: wrapName('The Sunken Vestry of Gulls') };
        }"""
    )
    assert result["states"] == [["a", "here"], ["b", "fogged"], ["c", "locked"]]
    assert "Boathouse" in result["text"] and "Locked" in result["text"]
    assert len(result["lines"]) == 2 and all(len(line) <= 18 for line in result["lines"])


def test_host_panel_actions_and_non_hosts_do_not_see_it(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    go_tab(guest, "more")
    assert guest.locator("[data-testid=open-host]").is_hidden()
    assert guest.locator("[data-testid=host]").count() == 0
    _open(host, "host")
    host.click("[data-testid=host-pause]")
    host.wait_for_function(f"{SNAPSHOT}.paused === true", timeout=20000)
    host.wait_for_function(
        "document.querySelector('[data-testid=host-pause]').textContent.includes('Resume')"
    )
    go_tab(guest, "play")
    guest.wait_for_function(
        "document.querySelector('[data-testid=action-note]').textContent.includes('paused')",
        timeout=20000,
    )
    host.click("[data-testid=host-pause]")
    host.wait_for_function(f"{SNAPSHOT}.paused === false", timeout=20000)
    host.evaluate(
        """() => {
          const hp = document.querySelector('[data-testid=host-hp]');
          hp.value = '1.5';
          hp.dispatchEvent(new Event('input', { bubbles: true }));
          hp.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )
    host.wait_for_function(f"{SNAPSHOT}.monster_hp === 1.5", timeout=20000)
    host.click("[data-testid=host-tts]")
    host.wait_for_function(f"{SNAPSHOT}.tts_enabled === true", timeout=20000)
    host.click("[data-testid=host-save]")
    assert "Save" in host.locator("[data-testid=host-saved]").inner_text()
    host.wait_for_function(
        "document.querySelector('[data-testid=host-stats]').textContent.includes('calls')",
        timeout=20000,
    )
    _fits(host, "host")
    snap(host, shots_dir, "controller_host", 390)
    # Kick asks first: cancel keeps the player, confirm removes the seat.
    guest_id = host.evaluate("window.aidm.store.get().players.find(p => p.name === 'Bo').id")
    host.click(f"[data-testid=host-kick-{guest_id}]")
    host.click(f"[data-testid=host-kick-{guest_id}-no]")
    assert host.locator("[data-testid=host-player]").count() == 1
    host.click(f"[data-testid=host-kick-{guest_id}]")
    host.click(f"[data-testid=host-kick-{guest_id}-yes]")
    host.wait_for_function(
        "!window.aidm.store.get().players.some(p => p.name === 'Bo')", timeout=20000
    )
    # The save shows up in the Load list the next time the panel opens.
    _close(host, "host")
    _open(host, "host")
    host.wait_for_selector("[data-testid=host-load-select] option", state="attached", timeout=20000)
    assert errors == []


def _merchant(live_server: LiveServer, gold: int) -> None:
    assert live_server.app is not None and live_server.loop is not None
    table = live_server.app.state.registry.table

    async def stage() -> None:
        state = table.state
        npc = WorldNpc(
            id="npc-brom",
            name="Brom Tallow",
            role="merchant",
            archetype_id="commoner",
            node_id=state.world.current_node,
        )
        table.apply_all([NpcIntroduced(npc=npc)])
        for creature in state.creatures.values():
            if creature.pc is not None:
                table.apply_all(
                    [GoldChanged(creature_id=creature.id, delta=gold, gold=creature.pc.gold + gold)]
                )

    live_server.loop.call_soon_threadsafe(table.schedule, stage)


def _supplies_and_refusal(host: Page, stock: list[dict[str, Any]]) -> None:
    # Camp supplies go to the party pool, not the pack.
    supply = next(line for line in stock if line["supply"] > 0)
    before = host.evaluate(f"{SNAPSHOT}.camp_supplies")
    host.click(f"[data-testid=shop-buy][data-item={supply['item_id']}]")
    host.wait_for_function(
        f"{SNAPSHOT}.camp_supplies === {before + supply['supply']}", timeout=20000
    )
    assert (
        f"Camp supplies: {before + supply['supply']}"
        in host.locator("[data-testid=shop-supplies]").inner_text()
    )
    # A refusal is friendly text, never the server's words.
    host.evaluate(
        "window.aidm.client.send('shop_buy',"
        " { npc_id: window.aidm.store.get().shop.npc_id, item_id: 'no-such-item', qty: 1 })"
    )
    host.wait_for_function(
        "document.querySelector('[data-testid=shop-status]').textContent.includes('knows nothing')",
        timeout=20000,
    )


def test_shop_buy_and_sell_flow(browser: Browser, live_server: LiveServer, shots_dir: Path) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, PHONE, errors)
    host.evaluate("window.aidm.store.update({ panel: 'shop' })")
    host.wait_for_selector("[data-testid=shop][open]")
    assert "No shop" in host.locator("[data-testid=shop-closed]").inner_text()
    host.click("[data-testid=shop-close]")
    host.wait_for_selector("[data-testid=shop]:not([open])", state="attached")
    _merchant(live_server, 400)
    host.wait_for_selector("[data-testid=open-shop]:not([hidden])", timeout=20000)
    _open(host, "shop")
    host.click("[data-testid=shop-visit]")
    host.wait_for_selector("[data-testid=vote]:not([hidden])", timeout=20000)
    guest.wait_for_selector("[data-testid=vote-ready]", timeout=20000)
    guest.click("[data-testid=vote-ready]")
    host.wait_for_selector("[data-testid=shop-stock] [data-testid=shop-line]", timeout=30000)
    guest.wait_for_selector("[data-testid=shop][open]", timeout=20000)
    keeper = host.locator(".shop-keeper").inner_text()
    assert "Brom Tallow" in keeper or "Dessa Orrin" in keeper  # staged or the sample merchant
    gold_before = host.evaluate(
        f"{SNAPSHOT}.party.find(c => c.id === window.aidm.store.get().players"
        ".find(p => p.name === 'Ann').creature_id).gold"
    )
    assert f"{gold_before} gp" in host.locator("[data-testid=shop-gold]").inner_text()
    snap(host, shots_dir, "controller_shop", 390)
    stock = host.evaluate("window.aidm.store.get().shop.stock")
    gear = next(line for line in stock if line["supply"] == 0 and 4 <= line["price_gp"] < 100)
    item, price = gear["item_id"], gear["price_gp"]
    host.click(f"[data-testid=shop-buy][data-item={item}]")
    host.wait_for_function(
        f"{SNAPSHOT}.party.some(c => c.gold === {gold_before - price})", timeout=20000
    )
    host.wait_for_function(
        "document.querySelector('[data-testid=shop-status]').textContent.includes('Bought')"
    )
    host.wait_for_selector(f"[data-testid=shop-pack-line][data-item={item}]", timeout=20000)
    host.click(f"[data-testid=shop-sell][data-item={item}]")
    host.wait_for_function(
        f"{SNAPSHOT}.party.some(c => c.gold > {gold_before - price})", timeout=20000
    )
    _supplies_and_refusal(host, stock)
    assert errors == []


def test_shop_view_renders_a_fake_stock_message(browser: Browser, live_server: LiveServer) -> None:
    """Unit check of the shop view: a fake `shop_stock` plus a snapshot with that shop open."""
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    host.evaluate(
        """() => {
          const { store, dispatch } = window.aidm;
          const snap = store.get().snapshot;
          const scene = { ...snap.state.scene, shop_npc_id: 'npc-fake', shopkeepers: ['npc-fake'] };
          dispatch({ ...snap, state: { ...snap.state, scene, camp_supplies: 2 } });
          dispatch({ type: 'shop_stock', npc_id: 'npc-fake', npc_name: 'Fake Fenn', stock: [
            { item_id: 'camp-ration', name: 'Camp Ration', price_gp: 1,
              category: 'supply', supply: 1 },
            { item_id: 'longsword', name: 'Longsword', price_gp: 15,
              category: 'weapon', supply: 0 },
          ] });
        }"""
    )
    host.wait_for_selector("[data-testid=shop][open]")
    assert host.locator("[data-testid=shop-line]").count() == 2
    assert "Adds 1 camp supplies" in host.locator("[data-testid=shop-line]").first.inner_text()
    assert "Camp supplies: 2" in host.locator("[data-testid=shop-supplies]").inner_text()
    assert errors == []


def test_settings_persist_across_reload(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    _open(host, "settings")
    host.select_option("[data-testid=set-speed]", "slow")
    host.select_option("[data-testid=set-size]", "large")
    host.check("[data-testid=set-motion]")
    host.fill("[data-testid=set-volume]", "35")
    host.dispatch_event("[data-testid=set-volume]", "change")
    host.check("[data-testid=set-mute]")
    snap(host, shots_dir, "controller_settings", 390)
    stored = host.evaluate("JSON.parse(window.localStorage.getItem('aidm.settings'))")
    assert stored == {
        "mute": True,
        "muteSet": True,
        "musicMute": False,
        "musicMuteSet": False,
        "narrationVolume": 35,
        "musicVolume": 50,
        "speed": "slow",
        "size": "large",
        "reduceMotion": True,
    }
    host.reload()
    host.wait_for_selector("[data-testid=controller]", timeout=20000)
    assert host.evaluate("document.documentElement.dataset.motion") == "reduced"
    assert (
        host.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--text-scale')")
        == "1.15"
    )
    _open(host, "settings")
    assert host.input_value("[data-testid=set-speed]") == "slow"
    assert host.input_value("[data-testid=set-size]") == "large"
    assert host.is_checked("[data-testid=set-motion]") and host.is_checked("[data-testid=set-mute]")
    assert host.input_value("[data-testid=set-volume]") == "35"
    assert errors == []


def test_every_panel_fits_a_phone(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, _guest = start_table(browser, live_server.base, PHONE, errors)
    assert host.evaluate(NO_SCROLL)
    _journal(host, shots_dir, 390)
    _map(host, shots_dir, 390)
    _merchant(live_server, 100)
    go_tab(host, "play")
    host.wait_for_selector("[data-testid=open-shop]:not([hidden])", timeout=20000)
    for name in ("shop", "host", "settings"):
        _open(host, name)
        _fits(host, name)
        snap(host, shots_dir, f"controller_{name}_dialog", 390)
        _close(host, name)
    assert errors == []


def test_controller_at_768_and_screen_at_1920(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    tablet = ViewportSize(width=768, height=1024)
    screen, host, _guest = start_with_screen(
        browser, live_server.base, errors, size=tablet, screen_size=FULL_HD
    )
    for page in (host, screen):
        assert page.evaluate(NO_SCROLL)
    snap(host, shots_dir, "controller_play", 768)
    snap(screen, shots_dir, "screen_table", 1920)
    assert errors == []
