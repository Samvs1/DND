"""Hit-chance preview: exact d20 math over every advantage source (SPEC 7.2 hotbar)."""

from __future__ import annotations

import random
from fractions import Fraction

import pytest

from aidm.models.combat import HitChance
from aidm.models.dice import AdvState
from aidm.models.encounter import Side
from aidm.models.state import GameState
from aidm.models.zones import CoverLevel, Zone, ZoneEdge, ZoneMap
from aidm.rules.attack_profiles import find_option
from aidm.rules.attacks import roll_attack
from aidm.rules.condition_timing import new_condition
from aidm.rules.hit_chance import dice_distribution, hit_chance, hit_chances, natural_chances
from tests.unit.rules.combat_fixtures import REGS, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc

FEATS = REGS.chars.features


def _chance(state: GameState, option: str = "main_hand", target: str = "gob") -> HitChance:
    profile = find_option(state.creatures["a"], REGS.chars, option)
    assert profile is not None
    return hit_chance(state, "a", target, profile, FEATS)


def _melee_fight(**target_kw: int) -> GameState:
    return fight(
        [(make_pc("a"), Side.PARTY, "gate"), (monster("gob", **target_kw), Side.HOSTILE, "gate")]
    )


def test_golden_hit_chance_normal() -> None:
    # SRD 5.1 Making an Attack: longsword +5 vs AC 15 hits on a natural 10+: 11/20.
    chance = _chance(_melee_fight())
    assert chance.probability == pytest.approx(0.55)
    assert chance.crit_chance == pytest.approx(0.05)
    assert chance.adv is AdvState.NORMAL
    assert (chance.target_ac, chance.attack_bonus) == (15, 5)


def test_golden_hit_chance_advantage_on_prone_target() -> None:
    # Prone target, melee attacker: advantage. P(hit) = 1 - (9/20)^2 = 319/400.
    state = _melee_fight()
    state.creatures["gob"].conditions.append(new_condition("prone"))
    chance = _chance(state)
    assert chance.adv is AdvState.ADVANTAGE
    assert chance.probability == pytest.approx(319 / 400)
    assert chance.crit_chance == pytest.approx(39 / 400)


def test_ranged_up_to_high_ground_has_disadvantage() -> None:
    # Target on the wall (high ground), shooter below: disadvantage, (11/20)^2.
    state = fight([(make_pc("a"), Side.PARTY, "gate"), (monster("gob"), Side.HOSTILE, "wall")])
    chance = _chance(state, "ranged")
    assert chance.adv is AdvState.DISADVANTAGE
    assert chance.probability == pytest.approx(121 / 400)


def test_cover_adds_to_ac_for_ranged_attacks_only() -> None:
    zmap = ZoneMap(
        zones=[Zone(id="gate", name="Gate"), Zone(id="ruin", name="Ruin", cover=CoverLevel.HALF)],
        edges=[ZoneEdge(a="gate", b="ruin", feet=30)],
    )
    state = fight(
        [(make_pc("a"), Side.PARTY, "gate"), (monster("gob"), Side.HOSTILE, "ruin")], zmap
    )
    chance = _chance(state, "ranged")
    assert chance.target_ac == 17
    assert chance.probability == pytest.approx(9 / 20)


def test_out_of_range_melee_is_zero() -> None:
    state = fight([(make_pc("a"), Side.PARTY, "gate"), (monster("gob"), Side.HOSTILE, "yard")])
    chance = _chance(state)
    assert not chance.in_range
    assert chance.probability == 0.0


def test_natural_one_always_misses_and_paralyzed_melee_crits() -> None:
    state = _melee_fight(ac=1)
    state.creatures["gob"].conditions.append(new_condition("paralyzed"))
    chance = _chance(state)
    assert chance.probability == pytest.approx(1 - 1 / 400)
    assert chance.crit_chance == pytest.approx(chance.probability)


def test_improved_critical_doubles_crit_chance() -> None:
    state = _melee_fight()
    pc = state.creatures["a"].pc
    assert pc is not None
    pc.level = 3
    pc.features.append("improved-critical")
    assert _chance(state).crit_chance == pytest.approx(0.10)


def test_hit_chances_lists_every_option() -> None:
    chances = hit_chances(_melee_fight(), "a", "gob", REGS.chars)
    assert [c.option for c in chances] == ["main_hand", "ranged", "unarmed"]


def test_natural_chances_sum_to_one() -> None:
    for adv in AdvState:
        assert sum(natural_chances(adv).values()) == Fraction(1)


def test_dice_distribution_1d4_plus_1() -> None:
    assert dice_distribution("1d4+1") == {v: Fraction(1, 4) for v in (2, 3, 4, 5)}


def test_preview_matches_rolled_frequency() -> None:
    state = _melee_fight()
    state.creatures["gob"].conditions.append(new_condition("prone"))
    profile = find_option(state.creatures["a"], REGS.chars, "main_hand")
    assert profile is not None
    rng = random.Random(7)
    trials = 4000
    hits = sum(roll_attack(rng, state, "a", "gob", profile, FEATS).hit for _ in range(trials))
    assert abs(hits / trials - 319 / 400) < 0.03
