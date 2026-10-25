"""Labels for the action menu, written for a model choosing from them (M36.2, SPEC 6.2). Pure.

Short, with descriptors from data, never numbers the hero could not see on the buttons:
- targets: name, distance and a plain state word ("Kobold A, 15 ft, unhurt"; "here" for the
  hero's own zone). State words follow the board's coarse states: unhurt (full), hurt (more than
  half), wounded (half or less), bloodied (a quarter or less), down (0 hit points).
- attacks: "Longsword (melee, 1d8+3)"; with one target its hit chance ("Shortbow (ranged,
  1d6+3, 73% vs Swarm of Rats)"); a stowed weapon says "draws first".
- spells: "Fire Bolt (cantrip, fire, 120 ft)", "Burning Hands (level 1, fire, DEX save, 15 ft
  cone, 2 slots left)" from the spell's own data (level, damage types, healing, saves, range,
  area, concentration).
- features: "Turn Undead (Channel Divinity, 1 left, undead nearby: Cantor Ashmere Voll)".

Public API: `state_word(creature)`, `distance_text(feet)`, `creature_label(creature, feet)`,
`zone_label(name, feet)`, `percent(p)`, `chance_note(p, feet)`,
`strike_label(name, band, damage, chance, draw)`, `spell_label(spell, line, slots_left)`,
`feature_label(line, extra)`, `resource_name(key)`, `item_label(name, heal, qty)`,
`area_words(area)`.
"""

from collections.abc import Iterator, Sequence

from aidm.data.spell_defs import (
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    HpPoolEffect,
    MultiTargetEffect,
    SaveEffect,
    SpellDef,
    TempHpEffect,
)
from aidm.models.sheet import FeatureActionLine, SpellLine
from aidm.models.state import Creature

HURT_AT = 1.0
WOUNDED_AT = 0.5
BLOODIED_AT = 0.25
_ECONOMY_WORDS = {
    "action": "action",
    "bonus_action": "bonus action",
    "extra_action": "extra action",
}
_AREA_WORDS = {"zone": "in your area", "zone_and_adjacent": "nearby"}


def state_word(creature: Creature) -> str:
    if creature.dead:
        return "dead"
    if creature.hp <= 0:
        return "down"
    ratio = creature.hp / max(1, creature.max_hp)
    if ratio <= BLOODIED_AT:
        return "bloodied"
    if ratio <= WOUNDED_AT:
        return "wounded"
    return "hurt" if ratio < HURT_AT else "unhurt"


def distance_text(feet: int | None) -> str:
    if feet is None:
        return "out of reach"
    return "here" if feet == 0 else f"{feet} ft"


def creature_label(creature: Creature, feet: int | None) -> str:
    return f"{creature.name}, {distance_text(feet)}, {state_word(creature)}"


def zone_label(name: str, feet: int | None) -> str:
    return f"{name}, {distance_text(feet)}"


def percent(probability: float) -> str:
    return f"{round(probability * 100)}%"


def chance_note(probability: float | None, feet: int) -> str:
    parts = [f"moves {feet} ft first"] if feet else []
    if probability is not None:
        parts.append(percent(probability))
    return ", ".join(parts)


def strike_label(name: str, band: str, damage: str, chance: str = "", draw: bool = False) -> str:
    parts = [band, damage if "d" in damage else f"{damage} damage"]
    if draw:
        parts.append("draws first")
    if chance:
        parts.append(chance)
    return f"{name} ({', '.join(parts)})"


def _walk(effects: Sequence[Effect]) -> Iterator[Effect]:
    for effect in effects:
        yield effect
        if isinstance(effect, AttackRollEffect):
            yield from _walk(effect.on_hit)
            if isinstance(effect.on_miss, tuple):
                yield from _walk(effect.on_miss)
        elif isinstance(effect, SaveEffect):
            yield from _walk(effect.on_fail)
            if isinstance(effect.on_success, tuple):
                yield from _walk(effect.on_success)
        elif isinstance(effect, (HpPoolEffect, MultiTargetEffect)):
            yield from _walk(effect.effects)


def _effect_words(spell: SpellDef) -> list[str]:
    words: list[str] = []
    for effect in _walk(spell.effects):
        if isinstance(effect, DamageEffect):
            word = str(effect.damage_type)
        elif isinstance(effect, (HealEffect, TempHpEffect)):
            word = "healing"
        elif isinstance(effect, SaveEffect):
            word = f"{str(effect.ability).upper()} save"
        else:
            continue
        if word not in words:
            words.append(word)
    return words


def _range_words(spell: SpellDef) -> str:
    shape = spell.targeting.shape
    if shape is not None:
        return f"{shape.feet} ft {shape.kind}"
    if spell.range.kind == "feet" and spell.range.feet is not None:
        return f"{spell.range.feet} ft"
    return spell.range.kind


def spell_label(spell: SpellDef, line: SpellLine, slots_left: int | None) -> str:
    parts = ["cantrip" if spell.level == 0 else f"level {spell.level}"]
    parts += _effect_words(spell)
    parts.append(_range_words(spell))
    if spell.casting_time == "bonus_action":
        parts.append("bonus action")
    if spell.concentration:
        parts.append("concentration")
    if slots_left is not None:
        parts.append(f"{slots_left} slot{'s' if slots_left != 1 else ''} left")
    return f"{line.name} ({', '.join(parts)})"


def resource_name(key: str) -> str:
    return key.replace("-", " ").title()


def area_words(area: str | None) -> str:
    return _AREA_WORDS.get(area or "zone", "in your area")


def feature_label(line: FeatureActionLine, extra: Sequence[str] = ()) -> str:
    parts: list[str] = []
    pool = resource_name(line.resource) if line.resource else ""
    if pool and pool.lower() != line.name.lower():
        parts.append(pool)
    parts.append(_ECONOMY_WORDS.get(line.economy, line.economy))
    if line.heal:
        parts.append(f"heals {line.heal}")
    if line.uses_left is not None:
        parts.append(f"{line.uses_left} left")
    parts += extra
    return f"{line.name} ({', '.join(parts)})"


def item_label(name: str, heal: str | None, qty: int) -> str:
    parts = ["bonus action"]
    if heal:
        parts.append(f"heals {heal}")
    parts.append(f"{qty} left")
    return f"{name} ({', '.join(parts)})"
