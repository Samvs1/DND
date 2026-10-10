"""Helping a downed ally up outside a fight, on the phone (M20.2, playtest 3: the warlock lay at
0 HP between two fights and nothing on the phone could raise her). FakeLLM server; no network."""

from pathlib import Path

from playwright.sync_api import Browser, ViewportSize

from aidm.models.damage import DamagePacket, DamageType
from aidm.rules.damage import resolve_damage
from aidm.session.table import Table
from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import start_table

SMALL = ViewportSize(width=393, height=702)
HELP = "[data-testid=help-up]"


def _down(live: LiveServer, name: str) -> None:
    assert live.app is not None and live.loop is not None
    table: Table = live.app.state.registry.table

    async def run() -> None:
        hero = next(c for c in table.state.creatures.values() if c.name == name)
        packet = DamagePacket(amount=hero.hp, damage_type=DamageType.PIERCING)
        table.apply_all(resolve_damage(hero, [packet]))
        table.broadcast_snapshot()

    live.loop.call_soon_threadsafe(table.schedule, run)


def test_phone_help_up_a_downed_ally_393x702(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    host, guest = start_table(browser, live_server.base, SMALL, errors)
    assert host.locator(HELP).count() == 0
    _down(live_server, "Mira")
    host.wait_for_selector(HELP, timeout=20000)
    assert host.inner_text(HELP) == "Help Mira up"
    guest.wait_for_function(
        "document.querySelector('[data-testid=now-line]').textContent.includes('help you up')",
        timeout=20000,
    )
    assert guest.locator(HELP).count() == 0  # a downed hero cannot help
    host.wait_for_load_state("networkidle")
    host.wait_for_timeout(500)
    host.screenshot(path=str(shots_dir / "phone_help_up_393x702.png"))
    host.click(HELP)
    host.wait_for_selector(HELP, state="detached", timeout=20000)
    guest.wait_for_function(
        "!document.querySelector('[data-testid=now-line]').textContent.includes('help you up')",
        timeout=20000,
    )
    assert errors == []
