"""Attack command and THE attack path: hit, crit, nat 1, riders, Extra Attack, concentration."""

from __future__ import annotations

import pytest

from aidm.models.abilities import Ability
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand, RefusalCode, ThrowCommand
from aidm.models.conditions import Concentration
from aidm.models.encounter import Side
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConditionRemoved,
    CreatureDied,
    DamageTaken,
    TempHpSet,
)
from aidm.models.state import ActiveCondition, GameState
from aidm.rules.attacks import roll_damage_dice
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from tests.unit.rules.combat_fixtures import ScriptedRng, do, economy, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc


def _duel(cls: str = "fighter", gob_zone: str = "gate", **gob_kw: int) -> GameState:
    return fight(
        [
            (make_pc("a", class_index=cls), Side.PARTY, "gate"),
            (monster("gob", **gob_kw), Side.HOSTILE, gob_zone),
        ]
    )


def _of[T](events: list[AnyEvent], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def _hit(cmd_rng: ScriptedRng, state: GameState, option: str = "main_hand") -> list[AnyEvent]:
    return do(state, AttackCommand(actor_id="a", target_id="gob", option=option), cmd_rng)


def test_golden_longsword_hit() -> None:
    # SRD 5.1: longsword 1d8 slashing + STR 3; attack +5 (STR 3 + prof 2). d20 12 -> 17 vs AC 15.
    state = _duel()
    events = _hit(ScriptedRng(12, 5), state)
    rolled = _of(events, AttackRolled)[0]
    assert (rolled.hit, rolled.crit, rolled.roll.total) == (True, False, 17)
    assert _of(events, DamageTaken)[0].total == 8
    assert state.creatures["gob"].hp == 2
    assert not economy(state, "a").action


def test_golden_crit_doubles_dice_not_modifier() -> None:
    # SRD 5.1 Critical Hits: 2d8+3 -> 3 + 6 + 3 = 12.
    state = _duel(hp=20)
    events = _hit(ScriptedRng(20, 3, 6), state)
    damage = _of(events, DamageTaken)[0]
    assert damage.crit and damage.total == 12
    assert state.creatures["gob"].hp == 8


def test_natural_one_misses_against_any_ac() -> None:
    state = _duel(ac=1)
    events = _hit(ScriptedRng(1), state)
    assert not _of(events, AttackRolled)[0].hit
    assert not _of(events, DamageTaken)
    assert state.creatures["gob"].hp == 10


def test_melee_hit_on_paralyzed_target_is_a_crit() -> None:
    state = _duel(hp=30)
    state.creatures["gob"].conditions.append(new_condition("paralyzed"))
    events = _hit(ScriptedRng(12, 3, 4, 4), state)
    rolled = _of(events, AttackRolled)[0]
    assert rolled.roll.rolls == (12, 3) and rolled.crit
    assert _of(events, DamageTaken)[0].total == 11


def test_kill_drops_monster() -> None:
    state = _duel(hp=5)
    events = _hit(ScriptedRng(15, 8), state)
    assert _of(events, CreatureDied)
    assert state.creatures["gob"].dead


def test_extra_attack_allows_two_attacks_per_action() -> None:
    state = _duel(hp=100, ac=5)
    pc = state.creatures["a"].pc
    assert pc is not None
    pc.level = 5
    pc.features.append("extra-attack-1")
    _hit(ScriptedRng(10, 4), state)
    assert (economy(state, "a").action, economy(state, "a").attacks_left) == (False, 1)
    _hit(ScriptedRng(10, 4), state)
    assert economy(state, "a").attacks_left == 0
    with pytest.raises(CommandRefused) as refused:
        _hit(ScriptedRng(10, 4), state)
    assert refused.value.code is RefusalCode.NO_ACTION


def test_golden_sneak_attack_once_per_turn() -> None:
    # Rogue dagger 1d4+3 with advantage (prone target) adds Sneak Attack 1d6 (SRD 5.1 Rogue).
    state = _duel("rogue", hp=40, ac=12)
    state.creatures["gob"].conditions.append(new_condition("prone"))
    events = _hit(ScriptedRng(15, 2, 3, 4), state)
    assert _of(events, DamageTaken)[0].total == 10
    assert economy(state, "a").once_per_turn_used == ("sneak-attack",)
    events = _hit(ScriptedRng(15, 2, 2), state, option="off_hand")
    assert _of(events, DamageTaken)[0].total == 2
    assert not economy(state, "a").bonus_action


def test_great_weapon_fighting_rerolls_low_dice_once() -> None:
    rolled = roll_damage_dice("2d6+3", ScriptedRng(1, 6, 4), reroll_below=3)
    assert rolled.total == 13
    assert [(d.value, d.kept) for d in rolled.dice] == [(1, False), (4, True), (6, True)]


def test_damage_forces_concentration_check() -> None:
    state = _duel(hp=30)
    state.creatures["gob"].concentrating_on = Concentration(spell_id="bless")
    events = _hit(ScriptedRng(15, 5, 2), state)
    checks = _of(events, CheckResolved)
    assert checks and checks[0].reason == "concentration bless"
    assert state.creatures["gob"].concentrating_on is None


def test_hidden_attacker_gains_advantage_and_is_revealed() -> None:
    state = _duel(hp=30)
    state.creatures["a"].conditions.append(ActiveCondition(name="hidden", source_id="a"))
    events = _hit(ScriptedRng(3, 14, 5), state)
    assert _of(events, AttackRolled)[0].roll.rolls == (3, 14)
    assert _of(events, ConditionRemoved)[0].name == "hidden"
    assert state.creatures["a"].conditions == []


def test_kill_grants_dark_ones_blessing_temp_hp() -> None:
    state = _duel("warlock", hp=3, ac=5)
    state.creatures["a"].abilities[Ability.CHA] = 16
    events = _hit(ScriptedRng(15, 4), state)
    assert _of(events, TempHpSet)[-1].temp_hp == 4


def test_out_of_range_and_unknown_option_are_refused() -> None:
    state = _duel(gob_zone="yard")
    with pytest.raises(CommandRefused) as refused:
        _hit(ScriptedRng(), state)
    assert refused.value.code is RefusalCode.OUT_OF_RANGE
    with pytest.raises(CommandRefused) as refused:
        _hit(ScriptedRng(), state, option="tail")
    assert refused.value.code is RefusalCode.UNKNOWN_OPTION
    assert economy(state, "a").action


def test_charmed_attacker_cannot_attack_charmer() -> None:
    state = _duel()
    state.creatures["a"].conditions.append(ActiveCondition(name="charmed", source_id="gob"))
    with pytest.raises(CommandRefused) as refused:
        _hit(ScriptedRng(), state)
    assert refused.value.code is RefusalCode.INVALID_TARGET


def test_golden_improvised_throw() -> None:
    # SRD 5.1 Improvised Weapons: 1d4 + STR 3, no proficiency (+3), 20/60 ft; yard is 1 hop.
    state = _duel(gob_zone="yard")
    events = do(state, ThrowCommand(actor_id="a", target_id="gob"), ScriptedRng(12, 3))
    rolled = _of(events, AttackRolled)[0]
    assert rolled.roll.total == 15 and rolled.hit
    assert _of(events, DamageTaken)[0].total == 6
    assert not economy(state, "a").action


def test_thrown_dagger_uses_finesse_and_proficiency() -> None:
    state = _duel("rogue", gob_zone="yard")
    events = do(
        state, ThrowCommand(actor_id="a", target_id="gob", item="dagger"), ScriptedRng(10, 2)
    )
    assert _of(events, AttackRolled)[0].roll.total == 15
    assert _of(events, DamageTaken)[0].total == 5
