"""M30.0b: typed-intent findings T5, T7 and T9 of playtest round 3 (docs/playtests/M29_round3.md),
each reproduced from its live save (tests/session/playtest_saves.py) and routed by the one
intent router."""

from pathlib import Path

import pytest

from aidm.dm.fake_llm import FakeStep
from aidm.dm.intent_router import fight_intent
from aidm.dm.llm_client import LlmClient
from aidm.dm.precheck import precheck
from aidm.dm.tool_context import tool_registries
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.commands import AttackCommand
from aidm.models.events import CheckResolved, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.world_events import EquipmentChanged
from aidm.rules.acts import CastIntent, GiveIntent
from aidm.rules.acts_fight import DrawAttack
from aidm.rules.equipment import EquipRefused, draw_events
from aidm.session import combat_flow
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, menu_llm, pick, running

LOCKBOX = "qi-pay-the-ferryman-own-0-0"
RENN = "old-renn-pitwater"


def _menu(tmp_path: Path, choice: FakeStep) -> LlmClient:
    """The menu chooser's reading (M36.10a); every other AI call fails as with no key."""
    return menu_llm(tmp_path, choice, storyteller_down=True)[0]


def _typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


def test_m30_r3_set_before_an_npc_is_a_give() -> None:
    """T5, r3-casters 288: "Rook sets the dripping Drowned Lockbox on the ferry boards in front
    of Old Renn Pitwater and says it was found whole ..." hands the keepsake over."""
    state = replay_until("r3-casters", 288)
    actor, text = _typed("r3-casters", 288)
    assert precheck(state, actor, text) == GiveIntent(actor, RENN, LOCKBOX)
    for line in ("Rook sets the lockbox down at Old Renn's feet", "I lay the lockbox before Renn"):
        assert precheck(state, actor, line) == GiveIntent(actor, RENN, LOCKBOX)


def test_m30_r3_set_down_with_nobody_named_is_no_give() -> None:
    state = replay_until("r3-casters", 288)
    assert precheck(state, "pc-p6", "Rook sets the lockbox on the boards") is None
    assert precheck(state, "pc-p6", "I set my torch before the door") is None


async def test_m30_r3_set_before_renn_moves_the_keepsake(tmp_path: Path) -> None:
    state = replay_until("r3-casters", 288)
    _, text = _typed("r3-casters", 288)
    give = pick(("give:drowned-lockbox", [RENN], 1))  # the menu chooser's reading (M36.10a)
    async with running(_menu(tmp_path, give), state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", "pc-p6")
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        rook = table.state.creatures["pc-p6"].pc
    given = [e for e in events if isinstance(e, KeepsakeGiven)]
    assert [(e.keepsake_id, e.npc_id) for e in given] == [(LOCKBOX, RENN)]
    assert rook is not None and LOCKBOX not in [k.id for k in rook.keepsakes]


def test_m30_r3_typed_cast_out_of_a_fight_is_read() -> None:
    """T7: a known spell typed out of a fight is cast by the engine, on heroes only."""
    state = replay_until("r3-casters", 288)
    bless = precheck(state, "pc-p4", "Elowen casts bless on Rook and Tamsin")
    assert bless == CastIntent("pc-p4", "bless", ("pc-p6", "pc-p8"))
    assert precheck(state, "pc-p4", "I cast guidance") == CastIntent(
        "pc-p4", "guidance", ("pc-p4",)
    )
    # a spell that needs a battlefield, or one aimed at an NPC here, stays with the storyteller
    assert precheck(state, "pc-p2", "Brienne casts magic missile at the ferryman") is None
    assert precheck(state, "pc-p4", "Elowen casts guidance on Old Renn") is None
    # the round-3 line itself: Rook's player tells of Brienne's light, a spell nobody knows
    actor, text = _typed("r3-casters", 276)
    assert precheck(replay_until("r3-casters", 276), actor, text) is None


async def test_m30_r3_typed_cast_spends_the_slot(tmp_path: Path) -> None:
    state = replay_until("r3-casters", 288)
    slots = state.creatures["pc-p4"].resources["spell-slot-1"].current
    bless = pick(("cast:bless", ["pc-p6", "pc-p8"], None))
    async with running(_menu(tmp_path, bless), state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", "pc-p4")
        start = table.state.event_count
        seat.send(SubmitAction(text="Elowen casts bless on Rook and Tamsin"))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        left = table.state.creatures["pc-p4"].resources["spell-slot-1"].current
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("bless", ("pc-p6", "pc-p8"))]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-1" for e in events)
    assert left == slots - 1


async def test_m30_r3_unprepared_typed_cast_is_refused_plainly(tmp_path: Path) -> None:
    """M36.10a: an unprepared spell is not on the menu (nor the hotbar), so the chooser says
    `other`: nothing is cast, no slot is spent and no check is rolled."""
    state = replay_until("r3-casters", 288)  # False Life is in Brienne's book, not prepared
    async with running(_menu(tmp_path, pick(other="")), state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", "pc-p2")
        start = table.state.event_count
        seat.send(SubmitAction(text="Brienne casts false life"))
        await table.settle()
        events = [e.event for e in table.log if e.seq >= start]
    assert not any(isinstance(e, SpellCast | ResourceSet | CheckResolved) for e in events)


def test_m30_r3_bring_my_mace_down_is_an_attack() -> None:
    """T9, r3-items 902 and 1112: "I bring my mace down on the ice mephit" was a Str check."""
    for seq, foe in ((902, "ice-mephit-1"), (1112, "dire-wolf-1")):
        actor, text = _typed("r3-items", seq)
        found = fight_intent(replay_until("r3-items", seq), actor, text)
        assert found == AttackCommand(actor_id=actor, target_id=foe, option="main_hand")


def test_m30_r3_cut_down_with_a_weapon_is_an_attack() -> None:
    actor, _ = _typed("r2-full", 510)  # round 2: "I cut down the last skeleton with my longsword"
    found = fight_intent(replay_until("r2-full", 510), actor, "I cut down Skeleton B with my sword")
    assert found == AttackCommand(actor_id=actor, target_id="skeleton-2", option="main_hand")


def test_m30_r3_stowed_rapier_is_drawn_then_attacks() -> None:
    """T9, r3-items 875 and 909: the rapier was stowed after `equip dagger`; drawing it is the
    free object interaction of the attack (SRD 5.1), so the attack was possible."""
    for seq in (875, 909):
        actor, text = _typed("r3-items", seq)
        found = fight_intent(replay_until("r3-items", seq), actor, text)
        attack = AttackCommand(actor_id=actor, target_id="ice-mephit-1", option="main_hand")
        assert found == DrawAttack("rapier", attack)


async def test_m30_r3_typed_attack_with_stowed_rapier_rolls_against_ac(tmp_path: Path) -> None:
    state = replay_until("r3-items", 875)
    _, text = _typed("r3-items", 875)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", "pc-p4")
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    drawn = [e for e in events if isinstance(e, EquipmentChanged) and e.creature_id == "pc-p4"]
    assert [e.equipped.main_hand for e in drawn] == ["rapier"]
    rolled = [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == "pc-p4"]
    assert [(e.attack, e.target_id) for e in rolled] == [("Rapier", "ice-mephit-1")]
    assert not any(isinstance(e, CheckResolved) and e.creature_id == "pc-p4" for e in events)


def test_m30_r3_draw_is_for_carried_weapons_and_free() -> None:
    state = replay_until("r3-items", 875)
    elowen = state.creatures["pc-p4"]
    chars = tool_registries().combat.chars
    drawn = draw_events(elowen, "rapier", chars)
    assert [type(e) for e in drawn] == [EquipmentChanged]
    assert draw_events(elowen, "dagger", chars) == []  # already in hand: nothing to draw
    with pytest.raises(EquipRefused):
        draw_events(elowen, "torch", chars)  # not a weapon
    economy = state.encounter.combatants["pc-p4"].economy if state.encounter else None
    assert economy is not None and economy.action  # the draw spends nothing by itself
