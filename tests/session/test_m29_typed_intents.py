"""M29.7a typed intents (docs/playtests/M29_round2.md R22, R4), each reproduced from its round-2
live save: the typed words become the engine's own command, never a storyteller act."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.fight_intent import fight_command
from aidm.dm.precheck import precheck
from aidm.models.abilities import Skill
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.events import CheckResolved, DiceRolled
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.rules.acts import ParleyIntent
from aidm.session import combat_flow
from aidm.session.table import Table
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import Seat, assert_replays, join, menu_down, pick, running


async def _resumed(table: Table, hero: str) -> Seat:
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
    swing = pick(("attack:longsword", ["thug-1"], None))
    events = await _in_fight(tmp_path, "r2-full", 455, "pc-p2", text, swing)
    attacks = [e for e in events if isinstance(e, AttackRolled)]
    assert attacks and attacks[0].attack == "Longsword" and attacks[0].target_ac > 0
    assert not any(isinstance(e, CheckResolved) for e in events)
    assert not any(isinstance(e, DiceRolled) and e.label == "Creative action" for e in events)


R4_TEXT = (
    "Before I decide anything, I call out to Hearthkeeper Veles and ask what he guards and"
    " whether he will let us pass."
)


def test_m29_talk_while_an_offer_waits_is_the_parley() -> None:
    state = replay_until("r2-p5", 536)
    assert precheck(state, "pc-p2", R4_TEXT) == ParleyIntent("pc-p2", Skill.PERSUASION)
    threat = precheck(state, "pc-p2", "I threaten Veles with my blade")
    assert threat == ParleyIntent("pc-p2", Skill.INTIMIDATION)
    assert precheck(state, "pc-p2", "I lie to Veles about who sent us") == ParleyIntent(
        "pc-p2", Skill.DECEPTION
    )
    others = ("I lie low in the reeds", "I tell the others to get ready", "I ask my companions")
    for other in (*others, "I swing my longsword at Veles"):
        assert not isinstance(precheck(state, "pc-p2", other), ParleyIntent)
    assert precheck(replay_until("r2-p5", 520), "pc-p2", R4_TEXT) is None  # no offer waits


async def test_m29_typed_parley_rolls_once_for_the_offer(tmp_path: Path) -> None:
    """p5 536-540: a storyteller Persuasion check passed (20 vs 20), then the parley rolled
    again and failed: one act, two rolls, the first counting for nothing."""
    state = replay_until("r2-p5", 536)
    parley = pick(("offer:parley:persuasion", [], None))  # the menu chooser's (M36.10b)
    async with running(menu_down(tmp_path, parley), state) as (table, _):
        seat = await join(table, "Ann", "pc-p2")
        start = table.state.event_count
        seat.send(SubmitAction(text=R4_TEXT))
        await table.settle()
        assert table.state.event_count == start + 1  # M31.1a V4: only the words, then the card
        seat.send(ConfirmHostile())
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    resolved = [e for e in events if isinstance(e, OfferResolved)]
    assert [r.choice for r in resolved] == [OfferChoice.PARLEY]
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert [(c.reason, c.result.skill) for c in checks] == [("parley", "persuasion")]
