"""Attack options (`AttackProfile`) for a creature: the inputs of the ONE attack path.

PC options come from the equipped weapons (`aidm.rules.weapon_attacks`), so the hotbar, the
sheet and the resolution use the same numbers. Monster options (M3.8) will map SRD actions to the
same `AttackProfile` shape.

Public API:
- `IMPROVISED_THROW` (1d4 bludgeoning, 20/60 ft; SRD 5.1 "Improvised Weapons"),
  `UNARMED_KEY` ("unarmed"), `THROW_KEY` ("throw").
- `weapon_die(dice) -> int`: the die size of the first dice term ("1d8+3" -> 8; 0 for flat).
- `with_mod(dice, mod) -> str`: "1d4" with +2 -> "1d4+2" (no term for 0).
- `attack_options(creature, regs) -> list[AttackProfile]`: main hand, off hand (a bonus-action
  attack, BG3), ranged weapon and unarmed strike; keyed by hand. Empty without `pc`.
- `find_option(creature, regs, key) -> AttackProfile | None`.
- `throw_profile(creature, item, regs) -> AttackProfile`: a weapon with the "thrown" property
  uses its own numbers at its throw range (finesse: the better of STR/DEX, else STR); any other
  object (or `item` None) is an improvised 1d4 bludgeoning throw with STR and no proficiency.
  Throwing is an action (BG3).
"""

from aidm.data.character_data import CharacterRegistries
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.abilities import Ability
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.damage import DamageType
from aidm.models.features import AttackContext
from aidm.models.sheet import AttackLine
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.dice import parse_dice
from aidm.rules.features import attack_bonus_mods, damage_bonus_mods
from aidm.rules.weapon_attacks import (
    attack_context,
    attack_lines,
    weapon_attack_ability,
    weapon_proficient,
)

IMPROVISED_THROW = "1d4"
IMPROVISED_RANGE = (20, 60)
UNARMED_KEY = "unarmed"
THROW_KEY = "throw"
MELEE_REACH = 5


def weapon_die(dice: str) -> int:
    terms = parse_dice(dice).terms
    return terms[0].sides if terms else 0


def with_mod(dice: str, mod: int) -> str:
    if mod > 0:
        return f"{dice}+{mod}"
    return f"{dice}-{-mod}" if mod < 0 else dice


def _profile(line: AttackLine, context: AttackContext) -> AttackProfile:
    ranged = line.range_band == "ranged"
    return AttackProfile(
        key=line.hand,
        name=line.name,
        attack_bonus=line.attack_bonus,
        damage=line.damage,
        damage_type=line.damage_type,
        ranged=ranged,
        range_normal=line.range_normal or MELEE_REACH,
        range_long=line.range_long if ranged else None,
        context=context.model_copy(update={"weapon_die": weapon_die(line.damage)}),
        economy=AttackEconomy.BONUS_ACTION if line.hand == "off_hand" else AttackEconomy.ATTACK,
    )


def attack_options(creature: Creature, regs: CharacterRegistries) -> list[AttackProfile]:
    pc = creature.pc
    if pc is None:
        return []
    options: list[AttackProfile] = []
    for line in attack_lines(creature, regs):
        weapon = regs.equipment.find(line.item) if line.item else None
        if weapon is None or line.hand == UNARMED_KEY:
            options.append(_profile(line, AttackContext()))
            continue
        options.append(_profile(line, attack_context(pc, weapon, line.hand)))
    return options


def find_option(creature: Creature, regs: CharacterRegistries, key: str) -> AttackProfile | None:
    return next((o for o in attack_options(creature, regs) if o.key == key), None)


def _improvised(creature: Creature, name: str) -> AttackProfile:
    mod = ability_modifier(creature.abilities[Ability.STR])
    normal, long = IMPROVISED_RANGE
    return AttackProfile(
        key=THROW_KEY,
        name=f"Throw {name}",
        attack_bonus=mod,
        damage=with_mod(IMPROVISED_THROW, mod),
        damage_type=DamageType.BLUDGEONING,
        ranged=True,
        range_normal=normal,
        range_long=long,
        context=AttackContext(ranged=True, weapon_die=weapon_die(IMPROVISED_THROW)),
        economy=AttackEconomy.ACTION,
    )


def throw_profile(
    creature: Creature, item: SrdEquipment | None, regs: CharacterRegistries
) -> AttackProfile:
    pc = creature.pc
    thrown = item is not None and any(p.index == "thrown" for p in item.properties)
    if item is None or pc is None or not thrown or item.damage is None:
        return _improvised(creature, item.name if item is not None else "object")
    finesse = any(p.index == "finesse" for p in item.properties)
    ability = weapon_attack_ability(creature, item) if finesse else Ability.STR
    mod = ability_modifier(creature.abilities[ability])
    prof = creature.proficiency_bonus if weapon_proficient(pc, item, regs.proficiencies) else 0
    dice = item.damage.damage_dice
    ctx = AttackContext(ranged=True, finesse=finesse, weapon_die=weapon_die(dice))
    reach = item.throw_range
    return AttackProfile(
        key=THROW_KEY,
        name=f"Throw {item.name}",
        attack_bonus=mod + prof + attack_bonus_mods(creature, regs.features, ctx),
        damage=with_mod(dice, mod + damage_bonus_mods(creature, regs.features, ctx)),
        damage_type=DamageType(item.damage.damage_type.index),
        ranged=True,
        range_normal=reach.normal if reach else IMPROVISED_RANGE[0],
        range_long=reach.long if reach else IMPROVISED_RANGE[1],
        context=ctx,
        economy=AttackEconomy.ACTION,
    )
