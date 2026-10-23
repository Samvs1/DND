"""Plain-language tooltip text for spells, built from the spell DSL data only (M28.1).

A spell has no description text in our data, so the tip is made from its casting time, range in
zones (`zones.hops_for_range`), targeting and effects. It cannot disagree with the engine because
it reads the same fields the interpreter reads. Pure: no I/O.

Public API: `spell_tip(spell) -> Tip`.
"""

from aidm.data.condition_defs import condition_defs
from aidm.data.spell_defs import (
    AcBuffEffect,
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    HpPoolEffect,
    MultiTargetEffect,
    RemoveConditionEffect,
    ReviveEffect,
    SaveEffect,
    SpellDef,
    StabilizeEffect,
    SurfaceEffect,
    TeleportEffect,
    TempHpEffect,
)
from aidm.data.srd import srd
from aidm.data.surface_defs import surface_defs
from aidm.models.tips import Tip
from aidm.rules.zones import hops_for_range

_TIME = {
    "action": "action",
    "bonus_action": "bonus action",
    "reaction": "reaction",
    "minutes": "takes minutes",
}


def _cond(index: str) -> str:
    found = condition_defs().find(index)
    return found.name if found is not None else index


def _rounds(rounds: int | None) -> str:
    if rounds is None:
        return ""
    return f" for {rounds} round{'s' if rounds != 1 else ''}"


def _zones(n: int) -> str:
    return f"{n} zone{'s' if n != 1 else ''}"


def _damage(e: DamageEffect) -> str:
    text = f"{e.dice} {e.damage_type}"
    if e.add_modifier:
        text += " plus your spellcasting modifier"
    return text + (" (more dice at levels 5, 11 and 17)" if e.cantrip_scaling else "")


def _simple(e: Effect) -> str | None:
    if isinstance(e, DamageEffect):
        return _damage(e)
    if isinstance(e, HealEffect):
        return f"heals {e.dice}" + (" plus your spellcasting modifier" if e.add_modifier else "")
    if isinstance(e, TempHpEffect):
        return f"gives {e.dice} temporary hit points"
    if isinstance(e, ApplyConditionEffect):
        ends = f", ends on a {e.save_ends.upper()} save each turn" if e.save_ends else ""
        return f"{_cond(e.condition)}{_rounds(e.rounds)}{ends}"
    if isinstance(e, RemoveConditionEffect):
        return "ends " + ", ".join(_cond(c) for c in e.conditions)
    if isinstance(e, AcBuffEffect):
        bonus = condition_defs().get(e.condition).ac_bonus
        return f"{bonus:+d} AC{_rounds(e.rounds)}"
    if isinstance(e, SurfaceEffect):
        found = surface_defs().find(e.surface)
        return f"leaves {found.name if found else e.surface} in the zone"
    if isinstance(e, StabilizeEffect):
        return "stabilizes a dying creature"
    if isinstance(e, ReviveEffect):
        return f"returns a dead creature to life with {e.hp} hit point{'s' if e.hp != 1 else ''}"
    if isinstance(e, TeleportEffect):
        return "moves you to the chosen zone"
    return None


def _effects(effects: tuple[Effect, ...]) -> list[str]:
    out: list[str] = []
    for e in effects:
        if isinstance(e, AttackRollEffect):
            out.append("on a hit " + "; ".join(_effects(e.on_hit)) + _miss(e))
        elif isinstance(e, SaveEffect):
            out.append(_save(e))
        elif isinstance(e, HpPoolEffect):
            inner = "; ".join(_effects(e.effects))
            out.append(
                f"rolls {e.dice} hit points of creatures, lowest first; each one that fits: {inner}"
            )
        elif isinstance(e, MultiTargetEffect):
            reach = (
                "the zone and its neighbours"
                if e.area == "zone_and_adjacent"
                else "the target's zone"
            )
            out.append(f"also hits others in {reach}: " + "; ".join(_effects(e.effects)))
        elif (text := _simple(e)) is not None:
            out.append(text)
    return out


def _miss(e: AttackRollEffect) -> str:
    if e.on_miss == "half":
        return ", half the damage on a miss"
    if e.on_miss == "none":
        return ""
    return "; on a miss " + "; ".join(_effects(e.on_miss))


def _save(e: SaveEffect) -> str:
    fail = "; ".join(_effects(e.on_fail))
    if e.on_success == "half":
        return f"on a failed save {fail}, half on a success"
    if e.on_success == "none":
        return f"on a failed save {fail}"
    return f"on a failed save {fail}; on a success {'; '.join(_effects(e.on_success))}"


def _first_roll(effects: tuple[Effect, ...]) -> str | None:
    for e in effects:
        if isinstance(e, AttackRollEffect):
            return f"{e.attack.capitalize()} spell attack"
        if isinstance(e, SaveEffect):
            return f"{e.ability.upper()} save"
        if isinstance(e, HpPoolEffect | MultiTargetEffect) and (inner := _first_roll(e.effects)):
            return inner
    return None


def _who(spell: SpellDef) -> str:
    t = spell.targeting
    spared = [
        *t.exclude_creature_types,
        *(f"those immune to {c}" for c in t.exclude_condition_immune),
    ]
    if spared:
        return _who_kind(spell) + " (not " + " or ".join(spared) + ")"
    return _who_kind(spell)


def _who_kind(spell: SpellDef) -> str:
    t = spell.targeting
    if t.kind == "self":
        return "on you"
    if t.kind == "point":
        return "at a zone"
    if t.kind == "area":
        wide = " and the zones next to it" if t.area == "zone_and_adjacent" else ""
        return f"hits everyone else in a zone{wide}"
    if t.kind == "creatures":
        more = f", +{t.count_per_slot} per higher slot" if t.count_per_slot else ""
        return f"up to {t.count} creatures{more}"
    return "one creature"


def _reach(spell: SpellDef) -> str:
    r = spell.range
    if r.kind == "self":
        return "on you"
    if r.kind == "touch" or r.feet is None:
        return "touch, same zone"
    hops = hops_for_range(r.feet)
    return "in your zone" if hops == 0 else f"up to {_zones(hops)} away"


def _upcast(effects: tuple[Effect, ...]) -> list[str]:
    out: list[str] = []
    for e in effects:
        if isinstance(e, DamageEffect | HealEffect | TempHpEffect) and e.upcast_dice:
            out.append(f"+{e.upcast_dice} per slot level above its own")
        elif isinstance(e, AttackRollEffect):
            out += _upcast(e.on_hit)
        elif isinstance(e, SaveEffect):
            out += _upcast(e.on_fail)
        elif isinstance(e, HpPoolEffect):
            out += (
                [f"+{e.upcast_dice} hit points per slot level above its own"]
                if e.upcast_dice
                else []
            )
    return out


def spell_tip(spell: SpellDef) -> Tip:
    name = srd().spells.get(spell.index).name
    level = "Cantrip" if spell.level == 0 else f"Level {spell.level}"
    head = f"{level}, {_TIME[spell.casting_time]}" + (
        ", concentration" if spell.concentration else ""
    )
    roll, reach = _first_roll(spell.effects), _reach(spell)
    parts = [roll] if roll else []
    parts.append(reach)
    if spell.targeting.kind != "self" and not (roll and spell.targeting.kind == "creature"):
        parts.append(_who(spell))
    where = ", ".join(parts)
    lines = [head + ".", where[0].upper() + where[1:] + "."]
    acts = _effects(spell.effects)
    if acts:
        lines.append("; ".join(acts)[0].upper() + "; ".join(acts)[1:] + ".")
    lines += [f"Higher slot: {u}." for u in _upcast(spell.effects)[:1]]
    return Tip(title=name, lines=tuple(lines))
