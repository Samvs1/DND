"""M29.7a typed intents (docs/playtests/M29_round2.md R22, R4), each reproduced from its round-2
live save: the typed words become the engine's own command, never a storyteller act."""

from pathlib import Path

from aidm.dm.fight_intent import fight_command
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.events import CheckResolved, DiceRolled
from aidm.models.protocol_client import SubmitAction
from aidm.session import combat_flow
from aidm.session.table import Table
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import Seat, assert_replays, disabled_llm, join, running


async def _resumed(table: Table, hero: str) -> Seat:
    table.in_combat = True
    seat = await join(table, "Ann", hero)
    table.schedule(lambda: combat_flow.advance(table))
    await table.settle()
    assert table.turn_key is not None
    return seat


async def _in_fight(tmp_path: Path, run: str, seq: int, hero: str, text: str) -> list[object]:
    state = replay_until(run, seq)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await _resumed(table, hero)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


def test_m29_typed_weapon_attack_is_the_attack_command() -> None:
    """full 455-460: "I swing my longsword at Mirrorwarden Luth" was a creative action."""
    state = replay_until("r2-full", 455)
    plain = AttackCommand(actor_id="pc-p2", target_id="thug-1", option="main_hand")
    for text in (
        "I swing my longsword at Mirrorwarden Luth",
        "Brienne swings her longsword at Mirrorwarden Luth",
        "attack Mirrorwarden Luth with my sword",
    ):
        assert fight_command(state, "pc-p2", text) == plain
    shot = fight_command(state, "pc-p2", "I shoot Mirrorwarden Luth")
    assert shot == AttackCommand(actor_id="pc-p2", target_id="thug-1", option="ranged")
    for creative in (
        "I swing from the chandelier into Mirrorwarden Luth",
        "stab Mirrorwarden Luth with my dagger",  # no dagger in hand
        "I swing my longsword at Elowen",  # not a foe
    ):
        assert fight_command(state, "pc-p2", creative) is None


async def test_m29_typed_weapon_attack_rolls_against_ac(tmp_path: Path) -> None:
    text = "I swing my longsword at Mirrorwarden Luth"
    events = await _in_fight(tmp_path, "r2-full", 455, "pc-p2", text)
    attacks = [e for e in events if isinstance(e, AttackRolled)]
    assert attacks and attacks[0].attack == "Longsword" and attacks[0].target_ac > 0
    assert not any(isinstance(e, CheckResolved) for e in events)
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)
