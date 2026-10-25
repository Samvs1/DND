"""Shared fixtures of the menu chooser tests (M36.5): replayed round-6 states, their menus and a
FakeLLM-backed client with per-tool scripts. Never touches the network."""

from collections.abc import Iterable, Mapping
from functools import cache
from pathlib import Path

from aidm.data.combat_data import combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.dm.fake_llm import FakeLLM, FakeStep
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode
from aidm.models.action_menu import ActionMenu
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_trade import TradeData
from tests.session.playtest_saves import events_of, replay_until

REGS = combat_registries()
TRADE = TradeData(item_catalogue(), shop_table())
TYPED, QUESTS = "m35-r6-typed", "m35-r6-quests"
FIGHT_SEQ = 496  # Brienne's turn: "I run across to the Caved-In Crypt and cut down the kobold"
GIFT_SEQ = 563  # Brienne at Halan's Rest with Widow Cabrelle and the peddler, 5 incense
RECENT = 60


@cache
def state_at(run: str, seq: int) -> GameState:
    return replay_until(run, seq)


@cache
def menu_at(run: str, seq: int, actor_id: str) -> ActionMenu:
    return build_menu(state_at(run, seq), actor_id, REGS, TRADE)


def recent_at(run: str, seq: int) -> list[AnyEvent]:
    return [e.event for e in events_of(run) if e.seq < seq][-RECENT:]


def chooser_client(
    tmp_path: Path,
    by_tool: Mapping[str, Iterable[FakeStep]] | None = None,
    script: Iterable[FakeStep] = (),
    *,
    mode: LlmMode = LlmMode.FAKE,
    strict: bool = False,
    max_retries: int = 2,
) -> tuple[LlmClient, FakeLLM]:
    settings = LlmSettings(
        api_key=None,
        log_path=tmp_path / "llm.jsonl",
        timeout_s=5.0,
        max_retries=max_retries,
        strict_tools=strict,
    )
    fake = FakeLLM(script, by_tool=by_tool)
    return LlmClient(fake, settings, mode, LlmCallLog(settings.log_path)), fake
