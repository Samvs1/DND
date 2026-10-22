"""Gear in a fight (M27.6, docs/next/GOAL_ITEMS.md "Items"): each combat item through the combat
command path (`use_item` -> THE item interpreter), applied by the reducer, replayable.

SRD 5.1 Adventuring Gear: Alchemist's Fire (ranged attack as an improvised weapon, burning 1d4
fire at the start of each turn, a DC 10 Dexterity check as an action ends it), Acid (2d6 acid),
Holy Water (2d6 radiant to a fiend or undead), Caltrops (DC 15 Dexterity save or 1 piercing),
Ball Bearings (DC 10 Dexterity save or prone), Healer's Kit (stabilize without a check, ten uses).
SRD 5.1 "Improvised Weapons": no proficiency bonus; the fixture hero has STR 16 (+3)."""

import random

import pytest

from aidm.models.combat_events import AttackRolled
from aidm.models.commands import (
    EndConditionCommand,
    EndTurnCommand,
    MoveCommand,
    RefusalCode,
    UseItemCommand,
)
from aidm.models.damage import DamageType
from aidm.models.dice import RollKind
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, DiceRolled, LoggedEvent, Stabilized
from aidm.models.item_events import ItemUsed, LightEnded, LightLit
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from aidm.rules.turns import begin_turn
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import ScriptedRng, do, economy, monster
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.item_fixtures import CAVE, DOCKS, gear_fight, hero, qty

FIRE, ACID, HOLY = "alchemists-fire-flask", "acid-vial", "holy-water-flask"


def _foe(cid: str = "gob", *, kind: str | None = None, **extra: int) -> Creature:
    foe = monster(cid, ac=12, **extra)
    foe.creature_type = kind
    return foe


def _throwing(*gear: str, foe: Creature | None = None, node: str = DOCKS) -> GameState:
    """The hero in zone a carrying `gear`; the foe one zone away (b, inside the 20 ft throw)."""
    return gear_fight(node, hero(gear=list(gear)), (foe or _foe(), Side.HOSTILE, "b"))


def _throw(
    state: GameState,
    item: str,
    rng: ScriptedRng,
    *,
    target_id: str | None = None,
    target_zone: str | None = None,
) -> list[AnyEvent]:
    cmd = UseItemCommand(actor_id="hero", item=item, target_id=target_id, target_zone=target_zone)
    return do(state, cmd, rng)


def _refused(state: GameState, cmd: UseItemCommand) -> str:
    with pytest.raises(CommandRefused) as refused:
        do(state, cmd, ScriptedRng())
    assert refused.value.code is RefusalCode.GEAR_REFUSED
    return refused.value.reason


def _next_turn(state: GameState, rng: ScriptedRng | random.Random) -> list[AnyEvent]:
    events = begin_turn(rng, state)
    for event in events:
        apply(state, event)
    return events


def _names(state: GameState, cid: str) -> list[str]:
    return [c.name for c in state.creatures[cid].conditions]


def test_golden_alchemists_fire_hits_burns_and_ticks() -> None:
    state = _throwing(FIRE)
    # d20 10 + STR 3 (no proficiency: improvised) = 13 vs AC 12: a hit; 1d4 fire rolls 3.
    events = _throw(state, FIRE, ScriptedRng(10, 3), target_id="gob")
    assert [e.use_id for e in events if isinstance(e, ItemUsed)] == ["alchemists-fire-throw"]
    assert state.creatures["gob"].hp == 10 - 3
    assert _names(state, "gob") == ["burning"]
    assert qty(state, "hero", FIRE) == 0 and not economy(state, "hero").action
    do(state, EndTurnCommand(actor_id="hero"), ScriptedRng())
    ticks = _next_turn(state, ScriptedRng(2))  # the goblin's turn starts: burning 1d4 rolls 2
    burn = [e for e in ticks if isinstance(e, DiceRolled) and e.kind is RollKind.DAMAGE]
    assert [(e.label, e.roll.total) for e in burn] == [("Burning", 2)]
    assert state.creatures["gob"].hp == 10 - 3 - 2


def test_a_missed_throw_is_still_spent_and_burns_nothing() -> None:
    state = _throwing(FIRE)
    _throw(state, FIRE, ScriptedRng(2), target_id="gob")  # 2 + 3 = 5 misses AC 12
    assert state.creatures["gob"].hp == 10 and _names(state, "gob") == []
    assert qty(state, "hero", FIRE) == 0


def test_burning_is_put_out_with_an_action_and_a_dc10_dex_check() -> None:
    state = _throwing()
    state.creatures["hero"].conditions.append(new_condition("burning", source_id="gob"))
    do(state, EndConditionCommand(actor_id="hero", condition="burning"), ScriptedRng(8))
    assert _names(state, "hero") == ["burning"]  # 8 + DEX 1 = 9 < 10
    assert not economy(state, "hero").action
    with pytest.raises(CommandRefused):  # one action per turn
        do(state, EndConditionCommand(actor_id="hero", condition="burning"), ScriptedRng(9))


def test_an_ally_in_the_zone_puts_the_flames_out() -> None:
    ally = make_pc("ally")
    state = gear_fight(DOCKS, hero(), (ally, Side.PARTY, "a"), (_foe(), Side.HOSTILE, "b"))
    state.creatures["ally"].conditions.append(new_condition("burning", source_id="gob"))
    cmd = EndConditionCommand(actor_id="hero", condition="burning", target_id="ally")
    do(state, cmd, ScriptedRng(9))  # 9 + DEX 1 = 10 meets DC 10
    assert _names(state, "ally") == []
    with pytest.raises(CommandRefused) as refused:
        do(state, EndConditionCommand(actor_id="hero", condition="burning"), ScriptedRng())
    assert refused.value.code is RefusalCode.INVALID_TARGET  # nothing to put out


def test_golden_acid_through_the_one_damage_path() -> None:
    state = _throwing(ACID)
    _throw(state, ACID, ScriptedRng(10, 3, 4), target_id="gob")  # 2d6 acid = 7
    assert state.creatures["gob"].hp == 3
    tough = _foe("gob")
    tough.resistances = [DamageType.ACID]
    resisted = _throwing(ACID, foe=tough)
    _throw(resisted, ACID, ScriptedRng(10, 3, 4), target_id="gob")  # resistance halves: 3
    assert resisted.creatures["gob"].hp == 7


def test_golden_holy_water_harms_undead() -> None:
    state = _throwing(HOLY, foe=_foe(kind="undead"))
    _throw(state, HOLY, ScriptedRng(10, 5, 6), target_id="gob")  # 2d6 radiant = 11
    assert state.creatures["gob"].hp == 0


def test_holy_water_on_a_beast_is_thrown_and_spent() -> None:
    # owner 2026-10-22: data adds effects, it never forbids the throw. SRD 5.1 Holy Water: only
    # a fiend or undead takes the 2d6 radiant; the attack is made and the flask is spent.
    beast = _throwing(HOLY, foe=_foe(kind="beast"))
    events = _throw(beast, HOLY, ScriptedRng(10), target_id="gob")  # 10 + 3 = 13 hits AC 12
    assert [e.hit for e in events if isinstance(e, AttackRolled)] == [True]
    assert next(e for e in events if isinstance(e, ItemUsed)).no_effect
    assert qty(beast, "hero", HOLY) == 0 and not economy(beast, "hero").action
    assert beast.creatures["gob"].hp == 10


def test_oil_then_a_thrown_torch_ignites_it_and_ends_the_light() -> None:
    ally = make_pc("ally")
    me = hero(gear=["oil-flask"])
    state = gear_fight(DOCKS, me, (ally, Side.PARTY, "a"), (_foe(), Side.HOSTILE, "b"))
    apply(state, LightLit(creature_id="ally", item="torch"))
    _throw(state, "oil-flask", ScriptedRng(), target_zone="b")
    assert _surfaces(state, "b") == ["oil"]
    do(state, EndTurnCommand(actor_id="hero"), ScriptedRng())
    _next_turn(state, random.Random(1))  # the ally's turn
    cmd = UseItemCommand(actor_id="ally", item="torch", target_zone="b")
    events = do(state, cmd, random.Random(4))
    assert LightEnded(creature_id="ally", reason="thrown", item="torch") in events
    assert state.world.lights == []
    assert _surfaces(state, "b") == ["fire"]
    assert state.creatures["gob"].hp < 10  # the burst (2d6 fire, DEX save for half)


def test_a_torch_thrown_where_nothing_burns_lands_and_ends_the_light() -> None:
    state = _throwing()
    apply(state, LightLit(creature_id="hero", item="torch"))
    events = _throw(state, "torch", ScriptedRng(), target_zone="b")  # owner 2026-10-22
    assert next(e for e in events if isinstance(e, ItemUsed)).no_effect
    assert LightEnded(creature_id="hero", reason="thrown", item="torch") in events
    assert state.world.lights == [] and _surfaces(state, "b") == []
    no_light = _throwing("torch")  # an unlit torch cannot be thrown alight: impossible
    reason = _refused(no_light, UseItemCommand(actor_id="hero", item="torch", target_zone="b"))
    assert "no lit torch" in reason


def test_torch_thrown_at_a_goblin_deals_one_fire_and_ends_the_light() -> None:
    state = _throwing()
    apply(state, LightLit(creature_id="hero", item="torch"))
    # d20 10 + STR 3 = 13 hits AC 12; SRD 5.1 Torch: 1 fire damage (a flat amount, no roll)
    events = _throw(state, "torch", ScriptedRng(10), target_id="gob")
    assert [e.use_id for e in events if isinstance(e, ItemUsed)] == ["torch-hit"]
    assert state.creatures["gob"].hp == 10 - 1
    assert LightEnded(creature_id="hero", reason="thrown", item="torch") in events
    assert state.world.lights == []


def _scatter_then_enter(item: str, save: int) -> GameState:
    """The hero scatters `item` in b (touching a); the goblin then walks from c into b."""
    state = gear_fight(DOCKS, hero(gear=[item]), (_foe(), Side.HOSTILE, "c"))
    _throw(state, item, ScriptedRng(), target_zone="b")
    do(state, EndTurnCommand(actor_id="hero"), ScriptedRng())
    _next_turn(state, ScriptedRng())
    do(state, MoveCommand(actor_id="gob", zone_id="b"), ScriptedRng(save))
    return state


def test_golden_caltrops_hurt_a_creature_that_fails_its_dc15_save() -> None:
    assert _scatter_then_enter("caltrops", 14).creatures["gob"].hp == 9  # 14 < 15: 1 piercing
    assert _scatter_then_enter("caltrops", 15).creatures["gob"].hp == 10  # 15 meets DC 15


def test_golden_ball_bearings_knock_down_on_a_failed_dc10_save() -> None:
    assert "prone" in _names(_scatter_then_enter("ball-bearings-bag-of-1000", 9), "gob")
    assert "prone" not in _names(_scatter_then_enter("ball-bearings-bag-of-1000", 10), "gob")


def test_healers_kit_stabilizes_a_fallen_ally_and_spends_a_charge() -> None:
    ally = make_pc("ally")
    state = gear_fight(
        DOCKS, hero(gear=["healers-kit"]), (ally, Side.PARTY, "a"), (_foe(), Side.HOSTILE, "c")
    )
    fallen = state.creatures["ally"]
    fallen.hp = 0
    fallen.conditions.append(new_condition("unconscious", source_id="zero_hp"))
    events = do(
        state, UseItemCommand(actor_id="hero", item="healers-kit", target_id="ally"), ScriptedRng()
    )
    assert any(isinstance(e, Stabilized) for e in events) and state.creatures["ally"].stable
    used = [e for e in events if isinstance(e, ItemUsed)]
    assert used[0].charges_left == 9  # ten uses (SRD), one spent; no check rolled
    assert qty(state, "hero", "healers-kit") == 1 and not economy(state, "hero").action


def test_a_torch_is_lit_in_a_dark_fight_as_a_bonus_action() -> None:
    state = _throwing("torch", node=CAVE)
    events = _throw(state, "torch", ScriptedRng())
    assert any(isinstance(e, LightLit) for e in events)
    eco = economy(state, "hero")
    assert (eco.action, eco.bonus_action) == (True, False)


def test_a_fight_with_thrown_gear_replays_to_the_same_state() -> None:
    state = _throwing(FIRE, ACID)
    base = state.model_copy(deep=True)
    log = _throw(state, FIRE, ScriptedRng(10, 3), target_id="gob")
    log += do(state, EndTurnCommand(actor_id="hero"), ScriptedRng())
    log += _next_turn(state, ScriptedRng(4))
    logged = [LoggedEvent(seq=i, event=e) for i, e in enumerate(log)]
    assert replay_log(base, logged) == state
    assert state.creatures["gob"].hp == 10 - 3 - 4


def _surfaces(state: GameState, zone: str) -> list[str]:
    enc = state.encounter
    assert enc is not None
    return [s.kind for s in enc.zone_map.zone(zone).surfaces]
