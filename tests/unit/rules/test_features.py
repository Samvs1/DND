"""Feature hook interpreter goldens (SPEC 7.4). SRD 5.1 class and race feature text cited inline."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from aidm.data.character_data import character_registries
from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.models.abilities import SKILL_ABILITY, Ability, Skill
from aidm.models.creation import CreationChoices, CreationErrorCode
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import AdvState
from aidm.models.events import AnyEvent, ConditionApplied, ConditionRemoved, HpChanged, ResourceSet
from aidm.models.features import ActionEconomy, AttackContext
from aidm.models.state import Creature, GameState, RechargeKind, Resource
from aidm.rules.abilities import ability_modifier
from aidm.rules.checks import skill_bonus
from aidm.rules.creation import build_character, validate_creation
from aidm.rules.damage import resolve_damage
from aidm.rules.feature_build import (
    SlotRecoveryError,
    granted_spells,
    recover_spell_slots,
    scroll_copy_cost,
)
from aidm.rules.features import (
    attack_bonus_mods,
    attacks_per_action,
    crit_threshold,
    damage_bonus_mods,
    damage_reroll_below,
    damage_riders,
    feature_actions,
    healing_bonus,
    kill_temp_hp,
    offhand_adds_ability,
    rerolls_natural_ones,
    save_advantage_sources,
    toggle_feature,
)
from aidm.rules.spellcasting import spend_slot
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices

REGS = character_registries()
FEATS = REGS.features
E = CreationErrorCode


def _build(cls: str, race: str = "human", sub: str | None = None, **update: object) -> Creature:
    choices = default_choices(cls, race, sub)
    if update:
        choices = CreationChoices.model_validate({**choices.model_dump(), **update})
    return build_character(choices, REGS, "pc1")


def _at(creature: Creature, level: int, *features: str) -> Creature:
    assert creature.pc is not None
    pc = creature.pc.model_copy(
        update={"level": level, "features": [*creature.pc.features, *features]}
    )
    return creature.model_copy(update={"pc": pc})


def _apply_all(creature: Creature, events: Sequence[AnyEvent]) -> Creature:
    state = GameState(campaign_id="c", seed=1, creatures={creature.id: creature})
    for event in events:
        apply(state, event)
    return state.creatures[creature.id]


FINESSE_ADV = AttackContext(finesse=True, adv=AdvState.ADVANTAGE, weapon_die=6)


def test_golden_rogue_sneak_attack_by_level() -> None:
    # SRD Rogue table: Sneak Attack 1d6 at 1st, 2d6 at 3rd, 3d6 at 5th level.
    rogue = _build("rogue")
    dice = [damage_riders(_at(rogue, lvl), FEATS, FINESSE_ADV)[0].dice for lvl in (1, 3, 5)]
    assert dice == ["1d6", "2d6", "3d6"]
    rider = damage_riders(_at(rogue, 3), FEATS, FINESSE_ADV)[0]
    assert (rider.feature, rider.once_per_turn, rider.damage_type) == ("sneak-attack", True, None)


def test_sneak_attack_conditions() -> None:
    rogue = _at(_build("rogue"), 3)
    assert damage_riders(rogue, FEATS, AttackContext(finesse=True)) == []
    assert damage_riders(rogue, FEATS, AttackContext(adv=AdvState.ADVANTAGE)) == []  # no finesse
    ally = AttackContext(ranged=True, ally_adjacent=True)
    assert len(damage_riders(rogue, FEATS, ally)) == 1
    blocked = ally.model_copy(update={"adv": AdvState.DISADVANTAGE})
    assert damage_riders(rogue, FEATS, blocked) == []
    used = FINESSE_ADV.model_copy(update={"used_once_per_turn": ("sneak-attack",)})
    assert damage_riders(rogue, FEATS, used) == []


def test_golden_champion_crit_19() -> None:
    # SRD Champion Improved Critical: crit on a roll of 19 or 20 from 3rd level.
    fighter = _build("fighter")
    assert crit_threshold(fighter, FEATS) == 20
    assert crit_threshold(_at(fighter, 3, "improved-critical"), FEATS) == 19


def test_golden_fighter_archery_plus_two() -> None:
    # SRD Fighting Style Archery: +2 bonus to attack rolls with ranged weapons.
    fighter = _build("fighter")  # the default pick is archery
    assert attack_bonus_mods(fighter, FEATS, AttackContext(ranged=True)) == 2
    assert attack_bonus_mods(fighter, FEATS, AttackContext()) == 0


def test_golden_defense_style_ac() -> None:
    # Chain mail 16 + shield 2 = 18; Defense +1 while armored (SRD Fighting Style).
    picks = {"fighting-style": ["fighter-fighting-style-defense"]}
    fighter = _build("fighter", "dwarf", "hill-dwarf", class_choices=picks)
    assert fighter.ac == 19


def test_dueling_gwf_and_two_weapon_styles() -> None:
    def styled(style: str) -> Creature:
        return _build(
            "fighter", class_choices={"fighting-style": [f"fighter-fighting-style-{style}"]}
        )

    dueling = styled("dueling")
    assert damage_bonus_mods(dueling, FEATS, AttackContext()) == 2
    assert damage_bonus_mods(dueling, FEATS, AttackContext(other_hand_weapon=True)) == 0
    gwf = styled("great-weapon-fighting")
    assert damage_reroll_below(gwf, FEATS, AttackContext(two_handed=True)) == 3
    assert damage_reroll_below(gwf, FEATS, AttackContext()) == 0
    twf = styled("two-weapon-fighting")
    assert offhand_adds_ability(twf, FEATS, AttackContext(offhand=True))
    assert not offhand_adds_ability(dueling, FEATS, AttackContext(offhand=True))


def test_golden_dwarf_poison_resistance_and_save_advantage() -> None:
    # SRD Dwarven Resilience: advantage on saves against poison, resistance to poison damage.
    dwarf = _build("fighter", "dwarf", "hill-dwarf")
    assert DamageType.POISON in dwarf.resistances
    events = resolve_damage(dwarf, [DamagePacket(amount=9, damage_type=DamageType.POISON)])
    assert [e.delta for e in events if isinstance(e, HpChanged)] == [-4]
    assert save_advantage_sources(dwarf, FEATS, Ability.CON, {"poisoned"}) == ["dwarven-resilience"]
    assert save_advantage_sources(dwarf, FEATS, Ability.WIS, {"charmed"}) == []


def test_golden_hill_dwarf_hp() -> None:
    # Fighter d10 10 + CON (13+2 -> +2) + Dwarven Toughness 1 = 13 at 1st level.
    assert _build("fighter", "dwarf", "hill-dwarf").max_hp == 13


def test_race_resistances_and_advantages() -> None:
    assert _build("wizard", "tiefling").resistances == [DamageType.FIRE]
    red = {"draconic-ancestry": ["draconic-ancestry-red"]}
    dragonborn = _build("fighter", "dragonborn", feature_choices=red)
    assert dragonborn.resistances == [DamageType.FIRE]
    assert dragonborn.pc is not None and "draconic-ancestry-red" in dragonborn.pc.traits
    assert "breath-weapon" in dragonborn.resources
    gnome = _build("wizard", "gnome", "rock-gnome")
    assert save_advantage_sources(gnome, FEATS, Ability.INT, {"magic"}) == ["gnome-cunning"]
    assert save_advantage_sources(gnome, FEATS, Ability.DEX, {"magic"}) == []
    halfling = _build("rogue", "halfling", "lightfoot-halfling")
    assert save_advantage_sources(halfling, FEATS, Ability.WIS, {"frightened"}) == ["brave"]
    assert rerolls_natural_ones(halfling, FEATS, "save")
    assert not rerolls_natural_ones(dragonborn, FEATS, "save")


def test_ancestry_pick_required_and_checked() -> None:
    base = default_choices("fighter", "dragonborn", None)
    missing = base.model_copy(update={"feature_choices": {}})
    field = "feature_choices.draconic-ancestry"
    assert (E.PICK_COUNT, field) in [(e.code, e.field) for e in validate_creation(missing, REGS)]
    wrong = base.model_copy(update={"feature_choices": {"draconic-ancestry": ["fire"]}})
    assert (E.PICK_NOT_ALLOWED, field) in [
        (e.code, e.field) for e in validate_creation(wrong, REGS)
    ]
    stray = base.model_copy(
        update={"feature_choices": {**base.feature_choices, "sneak-attack": ["x"]}}
    )
    codes = [(e.code, e.field) for e in validate_creation(stray, REGS)]
    assert (E.PICK_NOT_ALLOWED, "feature_choices.sneak-attack") in codes


def test_rogue_expertise_doubles_and_validates() -> None:
    rogue = _build("rogue")
    assert rogue.pc is not None
    picked = [Skill(s) for s in rogue.pc.feature_choices["rogue-expertise-1"]]
    assert rogue.skill_expertise == picked
    governing = ability_modifier(rogue.abilities[SKILL_ABILITY[picked[0]]])
    assert skill_bonus(rogue, picked[0]) == governing + 2 * 2  # SRD Expertise: double PB
    base = default_choices("rogue", "human", None)
    bad = base.model_copy(update={"feature_choices": {"rogue-expertise-1": ["arcana", "nature"]}})
    codes = [(e.code, e.field) for e in validate_creation(bad, REGS)]
    assert (E.PICK_NOT_ALLOWED, "feature_choices.rogue-expertise-1") in codes


def test_life_domain_heavy_armor_and_healing_bonus() -> None:
    # SRD Life Domain: Bonus Proficiency (heavy armor); Disciple of Life 2 + spell level.
    cleric = _build("cleric", "dwarf", "hill-dwarf")
    assert cleric.pc is not None and "heavy-armor" in cleric.pc.armor_proficiencies
    assert healing_bonus(cleric, FEATS, 1) == 3
    assert healing_bonus(cleric, FEATS, 0) == 0
    assert healing_bonus(_build("wizard"), FEATS, 1) == 0


def test_fighter_resources_and_actions() -> None:
    fighter = _build("fighter")
    assert fighter.resources["second-wind"].maximum == 1
    assert "action-surge" not in fighter.resources
    (wind,) = feature_actions(fighter, FEATS)
    assert (wind.action, wind.economy, wind.heal, wind.available) == (
        "second_wind",
        ActionEconomy.BONUS_ACTION,
        "1d10+1",
        True,
    )
    empty = fighter.resources["second-wind"].model_copy(update={"current": 0})
    spent = fighter.model_copy(update={"resources": {"second-wind": empty}})
    assert not feature_actions(spent, FEATS)[0].available


def test_cunning_action_and_extra_attack() -> None:
    rogue = _at(_build("rogue"), 2, "cunning-action")
    actions = {a.action for a in feature_actions(rogue, FEATS)}
    assert actions == {"dash", "disengage", "hide"}
    assert attacks_per_action(_build("fighter"), FEATS) == 1
    assert attacks_per_action(_at(_build("fighter"), 5, "extra-attack-1"), FEATS) == 2


def test_savage_attacks_and_colossus_slayer() -> None:
    orc = _build("fighter", "half-orc")
    (rider,) = damage_riders(orc, FEATS, AttackContext(crit=True, weapon_die=12))
    assert (rider.dice, rider.doubles_on_crit) == ("1d12", False)
    assert damage_riders(orc, FEATS, AttackContext(weapon_die=12)) == []
    ranger = _at(_build("ranger"), 3, "hunters-prey-colossus-slayer")
    (slayer,) = damage_riders(ranger, FEATS, AttackContext(target_wounded=True))
    assert slayer.dice == "1d8" and slayer.once_per_turn


def test_dark_ones_blessing_temp_hp() -> None:
    # SRD: Charisma modifier + warlock level (minimum 1). Standard array CHA 8 -> -1, +1 level.
    warlock = _build("warlock")
    assert kill_temp_hp(warlock, FEATS) == 1
    assert kill_temp_hp(_build("fighter"), FEATS) == 0


def test_toggle_fixture_rage_style() -> None:
    raw = {
        "index": "fixture-rage",
        "name": "Fixture Rage",
        "summary": "A rage-style toggle used only by tests.",
        "hooks": [
            {"kind": "resource", "key": "rage", "uses": 2, "recharge": "long_rest"},
            {
                "kind": "toggle",
                "key": "rage",
                "condition": "dodging",
                "resource": "rage",
                "while_active": [{"kind": "damage_rider", "flat": 2, "weapon": "melee"}],
            },
        ],
    }
    feats = Registry([*FEATS.all(), FeatureDef.model_validate(raw)])
    base = _at(_build("fighter"), 1, "fixture-rage")
    rage = Resource(current=2, maximum=2, recharge=RechargeKind.LONG_REST)
    base = base.model_copy(update={"resources": {**base.resources, "rage": rage}})
    assert damage_riders(base, feats, AttackContext()) == []
    on = toggle_feature(base, feats, "rage", on=True)
    assert [type(e) for e in on] == [ResourceSet, ConditionApplied]
    raging = _apply_all(base, on)
    assert raging.resources["rage"].current == 1
    (rider,) = damage_riders(raging, feats, AttackContext())
    assert rider.flat == 2 and rider.feature == "fixture-rage"
    assert damage_riders(raging, feats, AttackContext(ranged=True)) == []
    assert toggle_feature(raging, feats, "rage", on=True) == []
    off = toggle_feature(raging, feats, "rage", on=False)
    assert [type(e) for e in off] == [ConditionRemoved]
    assert damage_riders(_apply_all(raging, off), feats, AttackContext()) == []


def test_golden_arcane_recovery() -> None:
    # SRD Arcane Recovery: slots totalling half the wizard level (rounded up), once per day.
    wizard = _build("wizard")
    assert wizard.resources["arcane-recovery"].current == 1
    with pytest.raises(SlotRecoveryError):
        recover_spell_slots(wizard, FEATS, [1])  # nothing spent yet
    spent = _apply_all(wizard, spend_slot(wizard, 1))
    with pytest.raises(SlotRecoveryError):
        recover_spell_slots(spent, FEATS, [1, 1])  # budget 1 at level 1
    recovered = _apply_all(spent, recover_spell_slots(spent, FEATS, [1]))
    assert recovered.resources["spell-slot-1"].current == 2
    assert recovered.resources["arcane-recovery"].current == 0
    with pytest.raises(SlotRecoveryError):
        recover_spell_slots(recovered, FEATS, [1])
    with pytest.raises(SlotRecoveryError):
        recover_spell_slots(_build("fighter"), FEATS, [1])


def test_golden_scroll_copy_cost() -> None:
    # BG3/SRD: 50 gold per spell level; Evocation Savant halves evocation copies.
    wizard = _build("wizard")
    assert wizard.pc is not None
    ids = wizard.pc.features
    assert scroll_copy_cost(ids, 1, FEATS, 2, "evocation") == 100
    savant = [*ids, "evocation-savant"]
    assert scroll_copy_cost(savant, 2, FEATS, 1, "evocation") == 25
    assert scroll_copy_cost(savant, 2, FEATS, 1, "abjuration") == 50
    assert scroll_copy_cost(["second-wind"], 1, FEATS, 1, "evocation") is None


def test_fiend_expanded_list_and_domain_grants() -> None:
    base = default_choices("warlock", "human", None)
    picks = base.model_copy(update={"spells": ["burning-hands", "command"]})
    assert validate_creation(picks, REGS) == []
    cleric = _build("cleric")
    assert cleric.pc is not None
    grants = granted_spells(cleric.pc.features, 1, "life", FEATS)
    assert [(g.spell, g.mode) for g in grants] == [
        ("bless", "always_prepared"),
        ("cure-wounds", "always_prepared"),
    ]
    assert granted_spells(cleric.pc.features, 1, "other", FEATS) == []
    tiefling = _build("fighter", "tiefling")
    assert tiefling.pc is not None
    spells = [g.spell for g in granted_spells(tiefling.pc.traits, 5, None, FEATS)]
    assert spells == ["thaumaturgy", "hellish-rebuke", "darkness"]
    assert "infernal-legacy-hellish-rebuke" not in tiefling.resources
