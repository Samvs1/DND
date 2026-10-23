"""Golden numbers for the M29.9a rules findings of playtest round 3 (SRD 5.1; T1 T19 T18).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5. Monsters have AC 13, 30 HP and all ability scores 10. Rolls are scripted.
"""

from __future__ import annotations

from aidm.models.combat_events import FeatureUsed
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import CreatureDied, HpChanged, ResourceSet
from aidm.models.state import Creature, GameState, RechargeKind, Resource
from aidm.rules.damage import resolve_damage
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import ScriptedRng
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, next_turn


def test_golden_m29_sleep_spares_undead() -> None:
    # SRD 5.1 Sleep: "Undead and creatures immune to being charmed aren't affected by this
    # spell." Pool 5d8 = 15 (five 3s). The undead gob (5 HP, lowest) is skipped without
    # spending the pool, so gob2 (12 HP) fits and falls asleep.
    wiz = caster("w", "wizard", spells=["sleep"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    state.creatures["gob"].hp, state.creatures["gob2"].hp = 5, 12
    state.creatures["gob"].creature_type = "undead"
    cast(state, "w", "sleep", ScriptedRng(3, 3, 3, 3, 3), zone="yard")
    assert conditions_of(state, "gob") == [] and conditions_of(state, "gob2") == ["asleep"]


def test_golden_m29_sleep_spares_the_charm_immune() -> None:
    wiz = caster("w", "wizard", spells=["sleep"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    state.creatures["gob"].hp, state.creatures["gob2"].hp = 5, 12
    state.creatures["gob"].condition_immunities = ["charmed"]
    cast(state, "w", "sleep", ScriptedRng(3, 3, 3, 3, 3), zone="yard")
    assert conditions_of(state, "gob") == [] and conditions_of(state, "gob2") == ["asleep"]


def test_golden_m29_acid_arrow_hit_and_later_acid() -> None:
    # SRD 5.1 Acid Arrow: on a hit 4d4 acid at once and 2d4 acid at the end of the target's
    # next turn. d20 15 + 5 = 20 hits AC 13; 4d4 = 1+2+3+4 = 10 (30 -> 20); at the end of
    # gob's turn 2d4 = 2+3 = 5 (20 -> 15), then the burn is gone.
    wiz = caster("w", "wizard", spells=["acid-arrow"], level=3, slots={2: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "acid-arrow", ScriptedRng(15, 1, 2, 3, 4), targets=["gob"])
    assert state.creatures["gob"].hp == 20 and conditions_of(state, "gob") == ["acid-burn"]
    next_turn(state, ScriptedRng())  # the wizard's turn ends: no later acid yet
    assert state.creatures["gob"].hp == 20
    next_turn(state, ScriptedRng(2, 3))  # gob's turn ends: 2d4 acid
    assert state.creatures["gob"].hp == 15 and conditions_of(state, "gob") == []


def test_golden_m29_acid_arrow_miss_half_damage() -> None:
    # SRD 5.1 Acid Arrow: "On a miss, the arrow splashes the target with acid for half as much
    # of the initial damage and no damage at the end of its next turn." d20 2 + 5 = 7 misses
    # AC 13; 4d4 = 16, half = 8 (30 -> 22); no burn.
    wiz = caster("w", "wizard", spells=["acid-arrow"], level=3, slots={2: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "acid-arrow", ScriptedRng(2, 4, 4, 4, 4), targets=["gob"])
    assert state.creatures["gob"].hp == 22 and conditions_of(state, "gob") == []


def _half_orc(hp: int) -> Creature:
    hero = make_pc("h", class_index="fighter")
    assert hero.pc is not None
    hero.pc.traits.append("relentless-endurance")
    hero.max_hp, hero.hp = 20, hp
    hero.resources["relentless-endurance"] = Resource(
        current=1, maximum=1, recharge=RechargeKind.LONG_REST
    )
    return hero


def test_golden_m29_relentless_endurance_drops_to_one() -> None:
    # SRD 5.1 Half-Orc Relentless Endurance: "When you are reduced to 0 hit points but not
    # killed outright, you can drop to 1 hit point instead ... once per long rest." 7 HP, max
    # 20, 12 slashing: 5 left over (< 20, not killed outright) -> 1 HP, the use spent.
    hero = _half_orc(7)
    events = resolve_damage(hero, [DamagePacket(amount=12, damage_type=DamageType.SLASHING)])
    hp = [e for e in events if isinstance(e, HpChanged)]
    assert [(e.delta, e.new_hp) for e in hp] == [(-6, 1)]
    spent = [e for e in events if isinstance(e, ResourceSet)]
    assert [(e.key, e.resource.current) for e in spent] == [("relentless-endurance", 0)]
    assert any(isinstance(e, FeatureUsed) and e.name == "Relentless Endurance" for e in events)
    second = _half_orc(7)
    second.resources["relentless-endurance"] = Resource(
        current=0, maximum=1, recharge=RechargeKind.LONG_REST
    )
    again = resolve_damage(second, [DamagePacket(amount=12, damage_type=DamageType.SLASHING)])
    assert [e.new_hp for e in again if isinstance(e, HpChanged)] == [0]


def test_golden_m29_relentless_endurance_not_when_killed_outright() -> None:
    # 7 HP, max 20, 27 damage: 20 left over (>= max HP) is SRD "Instant Death"; no endurance.
    hero = _half_orc(7)
    events = resolve_damage(hero, [DamagePacket(amount=27, damage_type=DamageType.SLASHING)])
    assert any(isinstance(e, CreatureDied) for e in events)
    assert not any(isinstance(e, ResourceSet) for e in events)


def test_golden_m29_relentless_endurance_replays() -> None:
    hero = _half_orc(7)
    state = GameState(campaign_id="t", seed=1, creatures={"h": hero})
    for event in resolve_damage(hero, [DamagePacket(amount=9, damage_type=DamageType.FIRE)]):
        apply(state, event)
    after = state.creatures["h"]
    assert after.hp == 1 and after.resources["relentless-endurance"].current == 0
    assert not after.dead and after.conditions == []
