"""The monster action catalog (M3.8): shapes derived from SRD stat blocks, keys, resources,
creature type and traits, and the readiness baseline the M3.9 catalogue builds on."""

from __future__ import annotations

import pytest

from aidm.models.abilities import Ability
from aidm.models.commands import RefusalCode
from aidm.models.damage import DamageType
from aidm.models.encounter import Side
from aidm.models.state import RechargeKind
from aidm.rules.command_checks import CommandRefused
from aidm.rules.features import save_advantage_sources
from aidm.rules.monster_catalog import MonsterCatalog, MultiattackStep, monster_catalog
from aidm.rules.monster_keys import ability_slug, legendary_cost
from aidm.rules.monster_stats import creature_tags, creature_type_of
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, fight
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.monster_fixtures import act, resource, srd_monster
from tests.unit.rules.spell_fixtures import cast, caster, slots_left


def _catalog(index: str) -> MonsterCatalog:
    return monster_catalog(REGS.monsters.get(index), REGS.monster_overlay, REGS.spells)


def test_slugs_drop_legendary_costs() -> None:
    assert ability_slug("Wing Attack (Costs 2 Actions)") == "wing-attack"
    assert ability_slug("Sneak Attack (1/Turn)") == "sneak-attack-1-turn"
    assert legendary_cost("Heal Self (Costs 3 Actions)") == 3
    assert legendary_cost("Tail Attack") == 1


def test_owlbear_multiattack_routine() -> None:
    option = _catalog("owlbear").option("multiattack")
    assert option is not None
    assert option.routines == (
        (MultiattackStep("beak", "melee"), MultiattackStep("claws", "melee")),
    )


def test_bandit_captain_routines_and_dual_dagger() -> None:
    catalog = _catalog("bandit-captain")
    multi, dagger = catalog.option("multiattack"), catalog.option("dagger")
    assert multi is not None and dagger is not None
    assert [[s.action for s in r] for r in multi.routines] == [
        ["scimitar", "scimitar", "dagger"],
        ["dagger", "dagger"],
    ]
    assert [s.mode for s in multi.routines[1]] == ["ranged", "ranged"]
    assert dagger.melee is not None and dagger.ranged is not None
    assert (dagger.ranged.key, dagger.ranged.range_normal, dagger.ranged.range_long) == (
        "dagger-ranged",
        20,
        60,
    )


def test_bite_extra_fire_damage_and_reach() -> None:
    bite = _catalog("young-red-dragon").option("bite")
    assert bite is not None and bite.melee is not None
    assert (bite.melee.damage, bite.melee.damage_type, bite.melee.range_normal) == (
        "2d10+6",
        DamageType.PIERCING,
        10,
    )
    assert [(e.dice, e.damage_type) for e in bite.melee.extra_damage] == [("1d6", DamageType.FIRE)]


def test_versatile_choice_keeps_one_handed_damage() -> None:
    longsword = _catalog("veteran").option("longsword")
    assert longsword is not None and longsword.melee is not None
    assert longsword.melee.damage == "1d8+3"


def test_assassin_poison_is_a_save_rider() -> None:
    sword = _catalog("assassin").option("shortsword")
    assert sword is not None and sword.on_hit is not None
    assert sword.dc == 15
    assert sword.melee is not None and sword.melee.extra_damage == ()


def test_ghoul_claws_overlay_rider() -> None:
    claws = _catalog("ghoul").option("claws")
    assert claws is not None and claws.on_hit is not None
    assert (claws.dc, claws.exempt) == (10, ("elf", "undead"))


def test_dual_breath_shares_recharge_and_lists_unsupported() -> None:
    catalog = _catalog("adult-brass-dragon")
    breath = catalog.option("fire-breath")
    assert breath is not None and breath.resource == "recharge-breath-weapons"
    assert "Sleep Breath" in catalog.unsupported
    assert "Frightful Presence" in catalog.unsupported


def test_legendary_options() -> None:
    catalog = _catalog("adult-red-dragon")
    tail, wing = catalog.legendary_option("tail-attack"), catalog.legendary_option("wing-attack")
    assert tail is not None and tail.melee is not None and tail.melee.name == "Tail"
    assert wing is not None and (wing.shape, wing.cost, wing.dc) == ("save", 2, 22)
    assert "legendary Detect" in catalog.unsupported


def test_mage_spell_kit() -> None:
    catalog = _catalog("mage")
    bolt = catalog.spell("fire-bolt")
    assert bolt is not None
    assert (bolt.save_dc, bolt.attack_bonus, bolt.caster_level, bolt.resource) == (14, 6, 9, None)
    assert catalog.option("spell:magic-missile") is not None
    assert "spell counterspell" in catalog.unsupported


def test_innate_spell_spends_its_per_day_use() -> None:
    # SRD Drow: Innate Spellcasting (Cha, DC 11): darkness 1/day.
    catalog = _catalog("drow")
    darkness = catalog.spell("darkness")
    assert darkness is not None
    assert (darkness.resource, darkness.save_dc, darkness.attack_bonus) == (
        "innate-darkness",
        11,
        3,
    )
    assert "spell dancing-lights" in catalog.unsupported
    state = fight(
        [(srd_monster("drow", "d1"), Side.HOSTILE, "gate"), (make_pc("p1"), Side.PARTY, "yard")]
    )
    act(state, "d1", "spell:darkness", ScriptedRng(), zone="yard")
    assert resource(state, "d1", "innate-darkness") == 0
    assert state.creatures["d1"].concentrating_on is not None


def test_creature_from_monster_m38_fields() -> None:
    goblin = srd_monster("goblin", "g1")
    assert (goblin.monster_index, goblin.creature_type, goblin.traits) == (
        "goblin",
        "humanoid",
        ["nimble-escape"],
    )
    dragon = srd_monster("adult-red-dragon", "d1")
    assert dragon.resources["recharge-fire-breath"].turn_recharge == 5
    legendary = dragon.resources["legendary-actions"]
    assert (legendary.maximum, legendary.turn_recharge) == (3, 1)
    mage = srd_monster("mage", "m1")
    assert mage.resources["spell-slot-5"].maximum == 1
    duergar = srd_monster("duergar", "du1")
    assert duergar.resources["rest-enlarge"].recharge is RechargeKind.SHORT_REST
    dretch = srd_monster("dretch", "dr1")
    assert dretch.resources["per-day-fetid-cloud"].recharge is RechargeKind.LONG_REST


def test_creature_types_and_tags() -> None:
    assert creature_type_of(srd_monster("ghoul", "g")) == "undead"
    pc = make_pc("p1")
    assert creature_type_of(pc) == "humanoid"
    assert "human" in creature_tags(pc)


def test_magic_resistance_trait_is_a_feature() -> None:
    golem = srd_monster("unicorn", "u1")
    assert "magic-resistance" in golem.traits
    sources = save_advantage_sources(golem, REGS.chars.features, Ability.WIS, {"magic"})
    assert sources == ["magic-resistance"]


def test_hold_person_refuses_non_humanoids() -> None:
    # SRD Hold Person: "Choose a humanoid that you can see within range."
    wiz = caster("wiz", "wizard", spells=["hold-person"], level=3, slots={2: 2})
    state = fight(
        [
            (wiz, Side.PARTY, "gate"),
            (srd_monster("wolf", "wolf"), Side.HOSTILE, "gate"),
            (srd_monster("goblin", "gob"), Side.HOSTILE, "gate"),
        ]
    )
    with pytest.raises(CommandRefused) as refused:
        cast(state, "wiz", "hold-person", ScriptedRng(), targets=["wolf"])
    assert refused.value.code is RefusalCode.INVALID_TARGET
    assert slots_left(state.creatures["wiz"], 2) == 2
    cast(state, "wiz", "hold-person", ScriptedRng(2), targets=["gob"])
    assert any(c.name == "paralyzed" for c in state.creatures["gob"].conditions)


def test_readiness_baseline_cr8() -> None:
    """Every SRD monster yields a catalog; most CR <= 8 ones need nothing unsupported (M3.9)."""
    ready, empty = 0, []
    for block in REGS.monsters.all():
        catalog = monster_catalog(block, REGS.monster_overlay, REGS.spells)
        if block.challenge_rating > 8:
            continue
        if not [o for o in catalog.options if o.shape != "spell"]:
            empty.append(block.index)
        elif not catalog.unsupported:
            ready += 1
    assert ready >= 200
    assert empty == ["frog", "rug-of-smothering", "sea-horse", "shrieker"]
