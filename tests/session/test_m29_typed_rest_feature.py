"""M29.5b-2 leftovers (docs/playtests/M29_round1.md G17 rest half, p6 702), from the live saves:
a rest asked in a wordy sentence opens the same rest vote as the short command, and a typed
feature or heal in a fight runs as the hotbar's command (charged by the rules)."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.fight_intent import fight_command
from aidm.dm.precheck import precheck
from aidm.models.character import InventoryItem
from aidm.models.commands import CastCommand
from aidm.models.events import HpChanged, InventoryChanged, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import VoteOpen
from aidm.models.protocol_views import VoteKind
from aidm.rules.acts import RestIntent, RestKind
from aidm.session import combat_flow
from aidm.session.table import Table
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    join,
    menu_down,
    menu_llm,
    of_type,
    pick,
    running,
)

WORDY = (
    (
        353,
        "pc-p6",
        "We make camp among the thorns and take a short rest, so Rook can bind his wounds and"
        " catch his breath.",
        RestKind.SHORT,
    ),
    (
        355,
        "pc-p2",
        "The party sets watches and rests for the night at the camp, leaving the thorns behind.",
        RestKind.LONG,
    ),
    (
        357,
        "pc-p6",
        "Rook takes a long rest to recover his hit points, and the others keep watch.",
        RestKind.LONG,
    ),
)


def test_m29_wordy_rest_sentences_are_rest_intents() -> None:
    """p2 353-357: each went to the storyteller (no rest tool), so HP stayed unchanged."""
    for seq, hero, text, kind in WORDY:
        assert precheck(replay_until("p2", seq), hero, text) == RestIntent(kind)
    state = replay_until("p2", 353)
    for text in ("We do not rest for the night, we press on", "I search the camp for tracks"):
        assert precheck(state, "pc-p2", text) is None


async def test_m29_wordy_rest_opens_the_rest_vote_and_rests(tmp_path: Path) -> None:
    seq, hero, text, _ = WORDY[1]
    state = replay_until("p2", seq)
    hurt = state.creatures["pc-p6"].hp
    camp = pick(("rest:long", [], None))  # the menu chooser's reading (M36.10a)
    llm = menu_llm(tmp_path, camp, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", hero)
        seat.send(SubmitAction(text=text))
        await table.settle()
        opened = of_type(seat.drain(), VoteOpen)
        assert [v.kind for v in opened] == [VoteKind.LONG_REST]
        rook = table.state.creatures["pc-p6"]
        assert rook.hp == rook.max_hp > hurt
        assert_replays(table)


async def _resumed(table: Table, hero: str) -> Seat:
    """The saved fight goes on as after a load: the hero's open turn is prompted again."""
    table.in_combat = True
    seat = await join(table, "Ann", hero)
    table.schedule(lambda: combat_flow.advance(table))
    await table.settle()
    assert table.turn_key is not None
    return seat


async def _in_fight(
    tmp_path: Path, run: str, seq: int, hero: str, text: str, chosen: FakeStep
) -> list[object]:
    """`chosen`: the menu chooser's scripted reading of `text` (M36.10b)."""
    state = replay_until(run, seq)
    async with running(menu_down(tmp_path, chosen), state) as (table, _):
        seat = await _resumed(table, hero)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


async def test_m29_typed_second_wind_in_a_fight_uses_the_feature(tmp_path: Path) -> None:
    """p6 702: "Brienne uses Second Wind" on her turn got narration only, no heal, no use."""
    wind = pick(("feature:second-wind", [], None))
    events = await _in_fight(tmp_path, "p6", 702, "pc-p2", "Brienne uses Second Wind", wind)
    spent = [e for e in events if isinstance(e, ResourceSet) and e.key == "second-wind"]
    assert spent and spent[0].resource.current == 0
    assert any(isinstance(e, HpChanged) and e.creature_id == "pc-p2" for e in events)


async def test_m29_typed_potion_in_a_fight_is_the_hotbar_use(tmp_path: Path) -> None:
    """A draught drunk by typing in a fight is the hotbar's Use (an action per the rules)."""
    state = replay_until("p6", 702)
    brienne = state.creatures["pc-p2"]
    assert brienne.pc is not None
    brienne.pc.inventory.append(InventoryItem(item="potion-of-healing", qty=1))
    drink = pick(("item:potion-of-healing", ["pc-p2"], None))  # the menu chooser's (M36.10b)
    async with running(menu_down(tmp_path, drink), state) as (table, _):
        seat = await _resumed(table, "pc-p2")
        start = table.state.event_count
        seat.send(SubmitAction(text="I drink my potion of healing"))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    used = [(e.creature_id, e.item, e.delta) for e in events if isinstance(e, InventoryChanged)]
    assert used == [("pc-p2", "potion-of-healing", -1)]
    assert any(isinstance(e, HpChanged) and e.creature_id == "pc-p2" for e in events)


def test_m29_typed_cure_wounds_in_a_fight_is_the_cast_command() -> None:
    state = replay_until("p6", 702)
    command = fight_command(state, "pc-p4", "Elowen casts cure wounds on Brienne")
    assert command == CastCommand(actor_id="pc-p4", spell_id="cure-wounds", target_ids=("pc-p2",))
    assert fight_command(state, "pc-p2", "Brienne swings her longsword wildly") is None
