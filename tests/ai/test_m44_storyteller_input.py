"""M44.4 round 9 BB8 + BB9: the storyteller is told who has acted and what the open shop sells.

Real round-9 states and events (fixtures m43-r9-typed, m43-r9-full, m43-r9-quests); FakeLLM only,
never the network. The asserts read the prompt the storyteller receives, never model prose.
"""

from pathlib import Path

from aidm.dm.entities import entity_registry
from aidm.dm.fake_llm import FakeLLM
from aidm.dm.guard import prose_checker
from aidm.dm.narrator import narrate, narrate_round_segment
from aidm.models.events import AnyEvent
from aidm.models.trade_events import ItemsTraded
from aidm.models.world_events import ShopOpened
from tests.ai.chooser_fixtures import chooser_client, state_at
from tests.session.playtest_saves import events_of

TYPED, FULL, QUESTS = "m43-r9-typed", "m43-r9-full", "m43-r9-quests"
WAITING = "Foes whose turn has not come since the last telling"
SURPRISED = "Surprised foes"
WARES = "Wares of"
_RECORDS = ("action_declared", "line_read", "narration_recorded")


def _segment(run: str, seq: int) -> list[AnyEvent]:
    """The events a live telling at `seq` is handed: every engine event since the narration
    before it (the typed-line records never join a telling)."""
    log = [e for e in events_of(run) if e.seq < seq]
    last = max((e.seq for e in log if e.event.type == "narration_recorded"), default=-1)
    return [e.event for e in log if e.seq > last and e.event.type not in _RECORDS]


def _line(prompt: str, head: str) -> str:
    return next(line for line in prompt.splitlines() if line.startswith(f"- {head}"))


async def _told_segment(tmp_path: Path, run: str, seq: int) -> str:
    llm, fake = chooser_client(tmp_path)
    await narrate_round_segment(state_at(run, seq), _segment(run, seq), llm).collect()
    return _prompt(fake)


def _prompt(fake: FakeLLM) -> str:
    return "\n".join(str(m["content"]) for m in fake.requests[0].messages)


async def test_v1_m44_foes_not_acted_at_a_hero_line_r9_typed_589(tmp_path: Path) -> None:
    """r9-typed 589: Rook's Fire Bolt told before the foes' turn (the real blows at 592-624);
    the telling depicted the acolyte's fire and both bandits striking Elowen. The prompt now says
    the four foes have not had their turn, and gives no foe an action."""
    prompt = await _told_segment(tmp_path, TYPED, 589)
    waiting = _line(prompt, WAITING)
    assert all(n in waiting for n in ("Acolyte", "Bandit A", "Bandit B", "Thug"))
    acts = _line(prompt, "Actions of these events")
    assert "Rook: fire bolt at Bandit A" in acts
    assert not any(f"{n}:" in acts for n in ("Acolyte", "Bandit", "Thug"))


async def test_v1_m44_second_wind_told_before_the_foes_r9_typed_579(tmp_path: Path) -> None:
    """r9-typed 579: Brienne's Second Wind; the telling had the bandits lunge and cut Elowen."""
    prompt = await _told_segment(tmp_path, TYPED, 579)
    assert "Bandit A" in _line(prompt, WAITING) and "Thug" in _line(prompt, WAITING)


async def test_v1_m44_animated_armor_never_acts_r9_full_988(tmp_path: Path) -> None:
    """r9-full 988: the animated armour never attacks in its fight, yet was told hooking and
    swinging after Rook's miss. It is named as not having had its turn."""
    prompt = await _told_segment(tmp_path, FULL, 988)
    assert "Animated Armor" in _line(prompt, WAITING)
    assert "Animated Armor:" not in _line(prompt, "Actions of these events")


async def test_v1_m44_surprised_foes_lose_their_turn_r9_full_250(tmp_path: Path) -> None:
    """r9-full 250: the surprised stirge's turn passed with nothing; the telling had it dive and
    the wolf spring. Both are named surprised, with no step, swing, shot or spell."""
    prompt = await _told_segment(tmp_path, FULL, 250)
    surprised = _line(prompt, SURPRISED)
    assert "Stirge" in surprised and "Wolf" in surprised
    assert WAITING not in prompt


async def test_v1_m44_open_shop_wares_and_prices_r9_quests_166(tmp_path: Path) -> None:
    """r9-quests 166: "name his prices: the healer's kit, the coil of rope, and the oiled hide. Is
    there a bucket or a case-map?" was told with invented rope and oiled hide. The prompt now
    carries the Hollowsalt Peddler's real wares with their prices, and nothing else for sale."""
    state = state_at(QUESTS, 166)
    llm, fake = chooser_client(tmp_path)
    text = "I ask the peddler to name his prices: the healer's kit, the coil of rope."
    await narrate(state, [ShopOpened(npc_id="hollowsalt-peddler")], llm, player_text=text).collect()
    wares = _line(_prompt(fake), WARES)
    assert wares.startswith("- Wares of Hollowsalt Peddler")
    assert "Healer's Kit 5 gp" in wares and "Bucket 20 for 1 gp" in wares
    assert "Rope" not in wares and "Hide" not in wares


async def test_v1_m44_stocked_scroll_known_to_prompt_and_guard_r9_typed_1549(
    tmp_path: Path,
) -> None:
    """r9-typed 1549: the Scroll of Revivify is stocked at 300 gp, but the guard flagged
    `unknown_name:Scroll/Revivify` and the retry denied the stock. It is in the prompt and in the
    names the guard knows, so naming the real ware is not flagged."""
    state = state_at(TYPED, 1549)
    llm, fake = chooser_client(tmp_path)
    await narrate(state, [], llm, actor_id="pc-p4").collect()
    assert "Scroll of Revivify 300 gp" in _line(_prompt(fake), WARES)
    assert "Scroll of Revivify" in entity_registry(state).items
    report = prose_checker(state)("The peddler lifts the Scroll of Revivify from the cart.")
    assert not [v for v in report.violations if v.kind.value == "unknown_name"]


async def test_v1_m44_trades_since_the_last_telling_told_r9_full_512(tmp_path: Path) -> None:
    """r9-full 512: Rook bought 10 camp rations at the shop panel (506-508), then Tamsin's shop
    line was told "No one moves to buy". The telling is handed only its own `shop_opened`; the
    trade is carried in `Memory.untold` and told, then cleared by the narration."""
    state = state_at(FULL, 512)
    assert [e.item for e in state.memory.untold if isinstance(e, ItemsTraded)] == ["camp-ration"]
    llm, fake = chooser_client(tmp_path)
    opened = ShopOpened(npc_id="mirecross-inn-peddler")
    await narrate(state, [opened], llm, actor_id="pc-p8").collect()
    assert "Rook bought 10 x Camp Ration from Mirecross Inn Peddler for 5 gold." in _prompt(fake)
    assert state_at(FULL, 513).memory.untold == []
