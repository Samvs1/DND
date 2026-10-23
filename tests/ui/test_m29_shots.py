"""M29.7e: real-app screenshots for the owner at phone width 390 (artifacts/ui/): the master's
offer card with the sure parley (M29.7c R14) and the area-spell zone picker (M29.7d R26)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

from aidm.dm.fake_llm import FakeLLM, FakeStep, default_fake_step, fake_tool_call
from aidm.dm.llm_backend import CompletionRequest
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmMode
from aidm.server.settings import ServerSettings
from aidm.session.persistence import new_game_state
from tests.ui.conftest import COMBAT_SEED, LiveServer, _serve
from tests.ui.table_helpers import BOARD, MAIN, PHONE, WAIT, snap, start_with_screen
from tests.ui.wizard_helpers import HeroSpec

OFFER = """() => {
  const snap = window.aidm.store.get().snapshot;
  const offer = {
    id: 'offer-1', node_id: 'n1', foes: ['Ashmede Warden', 'Bone Acolyte'], boss_name: null,
    difficulty: 'hard', options: ['fight', 'surprise', 'escape', 'parley'], sure: ['parley'],
  };
  window.aidm.dispatch({ ...snap, type: 'snapshot', state: { ...snap.state, offer } });
}"""
WIZARD = HeroSpec(name="Vex", cls="wizard", race="elf", background="sage")
ROGUE = HeroSpec(name="Mira", race="elf", cls="rogue", background="criminal")
AMBUSH = "I ambush the goblins from the shadows"


def _rat_responder(request: CompletionRequest) -> FakeStep:
    """An "ambush" action starts a fight with two giant rats (weak, so the party gets turns)."""
    names = [t["function"]["name"] for t in request.tools or []]
    last = next((m for m in reversed(request.messages) if m.get("role") == "user"), {})
    done = any(m.get("role") == "tool" for m in request.messages)
    if "start_encounter" in names and "ambush" in str(last.get("content", "")).lower() and not done:
        return fake_tool_call("start_encounter", {"monster_ids": ["giant-rat", "giant-rat"]})
    return default_fake_step(request)


@pytest.fixture
def rat_server(tmp_path: Path) -> Iterator[LiveServer]:
    def make(settings: ServerSettings) -> LlmClient:
        return LlmClient(FakeLLM(responder=_rat_responder), settings.llm, LlmMode.FAKE, None)

    yield from _serve(tmp_path, make, state=new_game_state(seed=COMBAT_SEED))


def test_shot_offer_card_with_the_sure_parley(
    browser: Browser, live_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    _screen, host, _guest = start_with_screen(browser, live_server.base, errors)
    host.evaluate(OFFER)
    host.wait_for_selector("[data-testid=offer-parley]", timeout=20000)
    text = host.locator("[data-testid=offer-parley]").inner_text()
    assert text == "Parley (sure to hold)"
    for choice in ("fight", "surprise", "escape"):
        assert host.locator(f"[data-testid=offer-{choice}]").is_visible()
    snap(host, shots_dir, "m29_offer_sure_parley", 390)
    assert errors == []


def _wizard_turn(wizard: Page, rogue: Page) -> None:
    """End the rogue's turns until the wizard has the attack hotbar."""
    for _ in range(150):
        if wizard.locator("[data-testid=slot-spells]").count():
            return
        if rogue.locator(MAIN).count() and rogue.locator("[data-testid=end-turn]").count():
            rogue.click("[data-testid=end-turn]")
        wizard.wait_for_timeout(300)
    raise AssertionError("the wizard never got a turn")


def test_shot_area_preview_in_the_real_combat_screen(
    browser: Browser, rat_server: LiveServer, shots_dir: Path
) -> None:
    errors: list[str] = []
    screen, host, guest = start_with_screen(
        browser, rat_server.base, errors, PHONE, specs=(HeroSpec(name="Brienne"), WIZARD)
    )
    host.fill("[data-testid=action-input]", AMBUSH)
    host.click("[data-testid=action-send]")
    screen.wait_for_selector(BOARD, timeout=30000)
    for page in (host, guest):
        page.wait_for_selector(f"{MAIN}, {WAIT}", timeout=30000)
    _wizard_turn(guest, host)
    guest.click("[data-testid=slot-spells]")
    guest.click("[data-testid=cast-burning-hands]")
    guest.wait_for_selector("[data-testid=zone-caught]", timeout=20000)
    chips = guest.locator("[data-testid=zone-caught]").all_inner_texts()
    assert any(c.startswith("Hits:") for c in chips), chips
    guest.locator("[data-testid=places]").scroll_into_view_if_needed()
    snap(guest, shots_dir, "m29_area_preview_table", 390)
    assert errors == []
