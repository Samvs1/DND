"""Round damage danger (M29.7d, round 2): a foe's expected damage per round counts in the label.

Round 2 rated its worst fights "trivial" or "easy": a brown bear (200 XP) and a sahuagin dropped
20-HP casters in one turn (p8), a cult fanatic's Inflict Wounds did 22 to a 26-HP wizard (full),
a bugbear behind three-quarters cover took 12 rounds (p4). SRD XP sees none of that. Here each
foe's best action in a round (a multiattack routine, one attack, an at-will save action, or a
damaging spell of its kit) is averaged against heroes of the party's average AC; its share of
the heroes' average hit point maximum maps to a difficulty through
`EncounterTables.round_damage_rating` (data). A foe with a ranged attack whose fight zone has
cover adds `EncounterTables.cover_rating_step[cover]` steps (data). Limited-use area blasts are
`rules.encounter_danger.area_rating`'s; SRD numbers are never changed.

Public API:
- `round_damage(catalog, spells, hero_ac) -> float`: the foe's expected damage in one round.
- `attack_damage(catalog, hero_ac) -> float`: M31.1d, its best single attack's expected damage
  (what a master's turn adds, `rules.master_boost`).
- `round_rating(damage, hero_hp, tables) -> Difficulty | None`.
- `shoots(catalog, spells) -> bool`: the foe has a ranged attack or a ranged attack-roll spell.
- `stepped(rated, steps) -> Difficulty | None`: `rated` raised by `steps` (None counts as below
  easy, so one step from None is easy), never past deadly.
"""

from collections.abc import Sequence

from aidm.data.encounter_tables import EncounterTables
from aidm.data.registry import Registry
from aidm.data.spell_defs import AttackRollEffect, DamageEffect, Effect, SaveEffect, SpellDef
from aidm.models.combat import AttackProfile
from aidm.models.encounter import Difficulty
from aidm.rules.ai_estimates import crit_extra, dice_average
from aidm.rules.monster_catalog import MonsterCatalog, MonsterOption, MonsterSpell

_ORDER = list(Difficulty)
_REFERENCE_SAVE = 2  # a hero's typical save bonus at levels 1-5
_CRIT = 0.05


def _hit(bonus: int, ac: int) -> float:
    return min(0.95, max(0.05, (21 + bonus - ac) / 20))


def _attack(profile: AttackProfile | None, ac: int) -> float:
    if profile is None:
        return 0.0
    dice = [profile.damage, *(x.dice for x in profile.extra_damage)]
    mean = sum(dice_average(d) for d in dice if d)
    extra = sum(crit_extra(d) for d in dice if d)
    return _hit(profile.attack_bonus, ac) * mean + _CRIT * extra


def _best_attack(option: MonsterOption | None, ac: int, mode: str = "any") -> float:
    if option is None:
        return 0.0
    melee = _attack(option.melee, ac) if mode != "ranged" else 0.0
    ranged = _attack(option.ranged, ac) if mode != "melee" else 0.0
    return max(melee, ranged)


def _fail(dc: int) -> float:
    return min(0.95, max(0.05, (dc - 1 - _REFERENCE_SAVE) / 20))


def _damage(effects: Sequence[Effect], modifier: int) -> float:
    total = 0.0
    for effect in effects:
        if isinstance(effect, DamageEffect):
            total += dice_average(effect.dice) + (modifier if effect.add_modifier else 0)
    return total


def _effects(effects: Sequence[Effect], kit: MonsterSpell, ac: int) -> float:
    total = 0.0
    for effect in effects:
        if isinstance(effect, AttackRollEffect):
            total += _hit(kit.attack_bonus, ac) * _damage(effect.on_hit, kit.modifier)
        elif isinstance(effect, SaveEffect):
            fail = _fail(kit.save_dc)
            half = 0.5 if effect.on_success == "half" else 0.0
            total += (fail + (1 - fail) * half) * _damage(effect.on_fail, kit.modifier)
    return total


def _save(option: MonsterOption, ac: int) -> float:
    if option.save is None or option.resource is not None:
        return 0.0
    kit = MonsterSpell(option.key, option.name, 0, None, option.dc, 0, 0, 1)
    return _effects(option.save.effects, kit, ac)


def round_damage(catalog: MonsterCatalog, spells: Registry[SpellDef] | None, hero_ac: int) -> float:
    best = 0.0
    for option in catalog.options:
        if option.shape == "attack":
            best = max(best, _best_attack(option, hero_ac))
        elif option.shape == "multiattack":
            for routine in option.routines:
                steps = [_best_attack(catalog.option(s.action), hero_ac, s.mode) for s in routine]
                best = max(best, sum(steps))
        elif option.shape == "save":
            best = max(best, _save(option, hero_ac))
    for kit in catalog.spells:
        spell = spells.find(kit.index) if spells is not None else None
        if spell is not None:
            best = max(best, _effects(spell.effects, kit, hero_ac))
    return best


def attack_damage(catalog: MonsterCatalog, hero_ac: int) -> float:
    found = [
        _best_attack(o, hero_ac)
        for o in catalog.options
        if o.shape == "attack" and o.resource is None
    ]
    return max(found, default=0.0)


def round_rating(damage: float, hero_hp: float, tables: EncounterTables) -> Difficulty | None:
    if damage <= 0 or hero_hp <= 0:
        return None
    share = damage / hero_hp
    reached = [Difficulty(k) for k, v in tables.round_damage_rating.items() if share >= v]
    return max(reached, key=_ORDER.index) if reached else None


def shoots(catalog: MonsterCatalog, spells: Registry[SpellDef] | None) -> bool:
    if any(o.ranged is not None for o in catalog.options):
        return True
    found = [spells.find(k.index) for k in catalog.spells] if spells is not None else []
    return any(
        isinstance(e, AttackRollEffect) and e.attack == "ranged"
        for spell in found
        if spell is not None
        for e in spell.effects
    )


def stepped(rated: Difficulty | None, steps: int) -> Difficulty | None:
    if steps <= 0:
        return rated
    start = _ORDER.index(rated) if rated is not None else _ORDER.index(Difficulty.EASY) - 1
    return _ORDER[min(len(_ORDER) - 1, start + steps)]
