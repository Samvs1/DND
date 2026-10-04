"""Golden tests for the generic condition interpreter (aidm.rules.conditions).

Expected effects follow SRD 5.1 (CC-BY-4.0) Appendix "Conditions" as encoded in
data/bg3/conditions.json.
"""

from __future__ import annotations

import pytest

from aidm.data.registry import UnknownEntryError
from aidm.models.abilities import Ability
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import AdvState
from aidm.models.state import ActiveCondition, Creature, CreatureKind
from aidm.rules.conditions import (
    attack_adv,
    attack_adv_counts,
    can_attack_target,
    can_take_actions,
    can_take_reactions,
    check_adv_counts,
    effective_conditions,
    is_incapacitated,
    melee_hit_auto_crits,
    save_adv_counts,
    save_auto_fails,
    save_with_conditions,
    speed_multiplier,
)
from aidm.rules.damage import damage_after_defenses


class FixedRng:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, a: int, b: int, /) -> int:
        return self.value


def make(cid: str = "a", *names: str, source: str | None = None) -> Creature:
    return Creature(
        id=cid,
        name=cid.upper(),
        kind=CreatureKind.PC,
        max_hp=20,
        hp=20,
        conditions=[ActiveCondition(name=n, source_id=source) for n in names],
    )


def test_implied_conditions_are_effective() -> None:
    assert effective_conditions(make("a", "paralyzed")) == {"paralyzed", "incapacitated"}
    assert effective_conditions(make("a")) == frozenset()


def test_unknown_condition_key_raises() -> None:
    with pytest.raises(UnknownEntryError):
        effective_conditions(make("a", "not-a-condition"))


@pytest.mark.parametrize(
    ("attacker", "target", "melee", "expected"),
    [
        ((), (), True, AdvState.NORMAL),
        (("poisoned",), (), True, AdvState.DISADVANTAGE),
        (("invisible",), (), False, AdvState.ADVANTAGE),
        ((), ("prone",), True, AdvState.ADVANTAGE),  # SRD Prone: within 5 ft advantage
        ((), ("prone",), False, AdvState.DISADVANTAGE),  # SRD Prone: otherwise disadvantage
        ((), ("restrained",), False, AdvState.ADVANTAGE),
        (("blinded",), ("blinded",), True, AdvState.NORMAL),  # one of each cancels
        (("poisoned", "prone"), ("stunned",), True, AdvState.NORMAL),  # SRD: any mix cancels
        ((), ("dodging",), True, AdvState.DISADVANTAGE),
        (("hidden",), (), True, AdvState.ADVANTAGE),
    ],
)
def test_golden_attack_advantage(
    attacker: tuple[str, ...], target: tuple[str, ...], melee: bool, expected: AdvState
) -> None:
    assert attack_adv(make("a", *attacker), make("t", *target), melee=melee) is expected


def test_attack_counts_and_extra_sources() -> None:
    a, t = make("a", "poisoned"), make("t", "paralyzed")
    assert attack_adv_counts(a, t, melee=True) == (1, 1)
    assert attack_adv(make("a"), make("t"), melee=True, dis_sources=1) is AdvState.DISADVANTAGE
    assert attack_adv(make("a"), make("t"), melee=True, adv_sources=2) is AdvState.ADVANTAGE


def test_golden_auto_crit_on_melee_hit() -> None:
    # SRD Paralyzed / Unconscious: a hit from within 5 feet is a critical hit.
    assert melee_hit_auto_crits(make("t", "paralyzed"))
    assert melee_hit_auto_crits(make("t", "unconscious"))
    assert not melee_hit_auto_crits(make("t", "stunned"))


def test_charmed_cannot_attack_the_charmer() -> None:
    charmed = make("a", "charmed", source="t")
    assert not can_attack_target(charmed, make("t"))
    assert can_attack_target(charmed, make("other"))
    assert can_attack_target(make("a", "prone", source="t"), make("t"))


def test_golden_saves() -> None:
    stunned = make("a", "stunned")
    assert save_auto_fails(stunned, Ability.DEX)
    assert save_auto_fails(stunned, Ability.STR)
    assert not save_auto_fails(stunned, Ability.WIS)
    assert save_adv_counts(make("a", "restrained"), Ability.DEX) == (0, 1)
    assert save_adv_counts(make("a", "dodging"), Ability.DEX) == (1, 0)
    assert save_adv_counts(make("a", "restrained"), Ability.CON) == (0, 0)


def test_check_disadvantage_sources() -> None:
    assert check_adv_counts(make("a", "poisoned", "frightened")) == (0, 2)
    assert check_adv_counts(make("a", "exhaustion")) == (0, 1)
    assert check_adv_counts(make("a")) == (0, 0)


def test_speed_actions_reactions() -> None:
    assert speed_multiplier(make("a")) == 1.0
    assert speed_multiplier(make("a", "grappled")) == 0.0
    assert can_take_actions(make("a", "poisoned"))
    assert not can_take_actions(make("a", "stunned"))
    assert not can_take_reactions(make("a", "incapacitated"))
    assert can_take_reactions(make("a", "prone"))
    surprised = make("a", "surprised")
    assert not can_take_actions(surprised)
    assert not is_incapacitated(surprised)
    assert is_incapacitated(make("a", "unconscious"))
    dead = make("a")
    dead.dead = True
    assert not can_take_actions(dead)
    assert not can_take_reactions(dead)


def test_save_with_conditions_auto_fail_still_rolls() -> None:
    result = save_with_conditions(FixedRng(20), make("a", "paralyzed"), Ability.DEX, 10)
    assert result.roll.natural == 20
    assert not result.success
    ok = save_with_conditions(FixedRng(20), make("a", "paralyzed"), Ability.WIS, 10)
    assert ok.success


def test_save_with_conditions_combines_advantage() -> None:
    result = save_with_conditions(FixedRng(12), make("a", "restrained"), Ability.DEX, 10)
    assert result.roll.adv is AdvState.DISADVANTAGE
    both = save_with_conditions(
        FixedRng(12), make("a", "restrained"), Ability.DEX, 10, adv_sources=1, bonus=2
    )
    assert both.roll.adv is AdvState.NORMAL
    assert both.roll.total == 14


def test_golden_petrified_damage_defences() -> None:
    # SRD Petrified: resistance to all damage, immune to poison.
    stone = make("a", "petrified")
    assert damage_after_defenses(stone, DamagePacket(amount=9, damage_type=DamageType.FIRE)) == 4
    assert damage_after_defenses(stone, DamagePacket(amount=9, damage_type=DamageType.POISON)) == 0
    plain = make("a")
    assert damage_after_defenses(plain, DamagePacket(amount=9, damage_type=DamageType.FIRE)) == 9
