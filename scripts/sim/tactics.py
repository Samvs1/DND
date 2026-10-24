"""Careful-table tactics of the campaign bots (M31.1f), read from the foes' public SRD data.

A foe token names its stat block (`monster_index`, the art key every player's screen has); the
bots read what a careful table knows about that kind of creature, never its hidden dice:
- `spread_command`: against a foe with an area blast (a breath weapon or an area damage spell its
  kit can cast: `rules.encounter_danger.area_damage` with the spell registry, the same rule the
  plan check uses), a hero who can strike from afar and shares a zone with an ally (and with no
  foe) steps into a touching zone that holds nobody and no surface. Heroes in a foe's zone stay:
  the melee positioning is unchanged; one step per turn.
- `factor(target, damage_type)`: the share of damage of that type the foe takes, by THE rules'
  damage check (`rules.damage.damage_after_defenses` on the stat block's creature).
- `attack_option`: when the target's defences change the pick, the in-range weapon option with
  the most expected damage after them (hit chance x average x factor); else None (the default,
  the best hit chance).
- `cantrip_for`: a caster swaps a cantrip the target resists for a known damaging one it takes
  more of; any other hero whose every weapon is resisted casts a known damaging cantrip the foe
  does not resist.
- `best_damage_spell`: among leveled damage spells (in preference order), the one the target
  takes most of; one it is immune to is never picked.
- `resist_gear`: a hero whose every weapon is resisted throws carried gear that deals damage of a
  type the foe takes more of (holy water, alchemist's fire, acid; data/bg3/item_uses.json) when
  its average beats the best weapon after defences.

Public API: `spread_command`, `factor`, `attack_option`, `cantrip_for`, `best_damage_spell`,
`resist_gear`, `touching`, `weapons_resisted`.
"""

from collections.abc import Sequence
from functools import cache

from aidm.data.item_uses import DamageUse, item_use_data
from aidm.data.spell_defs import (
    AttackRollEffect,
    DamageEffect,
    Effect,
    MultiTargetEffect,
    SaveEffect,
    spell_defs,
)
from aidm.data.srd import srd
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.state import Creature
from aidm.rules.damage import damage_after_defenses
from aidm.rules.dice import dice_max, dice_min
from aidm.rules.encounter_danger import area_damage
from aidm.rules.monster_stats import creature_from_monster, creature_type_of
from scripts.sim.client import Msg
from scripts.sim.combat import Plan, token_of

PROBE = 100


@cache
def _foe(monster_index: str) -> Creature | None:
    monster = srd().monsters.find(monster_index)
    return None if monster is None else creature_from_monster(monster, "probe")


@cache
def _area_threat(monster_index: str) -> bool:
    monster = srd().monsters.find(monster_index)
    return monster is not None and area_damage(monster, spell_defs()) > 0


def _average(dice: str) -> float:
    return (dice_min(dice) + dice_max(dice)) / 2


def factor(target: Msg, damage_type: str) -> float:
    index = target.get("monster_index")
    foe = _foe(index) if index else None
    if foe is None:
        return 1.0
    packet = DamagePacket(amount=PROBE, damage_type=DamageType(damage_type))
    return damage_after_defenses(foe, packet) / PROBE


def touching(combat: Msg, zone: str) -> set[str]:
    edges = combat.get("edges") or []
    return {e["b"] for e in edges if e["a"] == zone} | {e["a"] for e in edges if e["b"] == zone}


def _clear(combat: Msg, zone_id: str) -> bool:
    zone = next((z for z in combat.get("zones", []) if z["id"] == zone_id), {})
    return not zone.get("surfaces") and not zone.get("rough")


def _reaches_afar(plan: Plan, sheet: Msg | None) -> bool:
    attacks = (sheet or {}).get("attacks", [])
    return plan.cantrip is not None or any(a.get("range_band") == "ranged" for a in attacks)


def spread_command(plan: Plan, combat: Msg, foes: list[Msg], sheet: Msg | None) -> Msg | None:
    """One step apart from the party against an area blast (module docstring), or None."""
    me = token_of(combat, plan.hero_id)
    eco = combat.get("economy") or {}
    if me is None or plan.spread_to is not None or eco.get("movement_left", 0) <= 0:
        return None
    if not any(_area_threat(f["monster_index"]) for f in foes if f.get("monster_index")):
        return None
    here = me["zone_id"]
    others = [
        t
        for t in combat["tokens"]
        if t["creature_id"] != plan.hero_id and not t["dead"] and not t.get("withdrawn")
    ]
    crowded = any(t["zone_id"] == here and t["side"] == me["side"] for t in others)
    engaged = any(f["zone_id"] == here for f in foes)
    if engaged or not crowded or not _reaches_afar(plan, sheet):
        return None
    taken = {t["zone_id"] for t in others}
    free = sorted(z for z in touching(combat, here) if z not in taken and _clear(combat, z))
    if not free:
        return None
    plan.spread_to = free[0]
    return {"type": "move", "actor_id": plan.hero_id, "zone_id": free[0]}


def _weapon_lines(sheet: Msg | None) -> dict[str, Msg]:
    return {a["hand"]: a for a in (sheet or {}).get("attacks", [])}


def weapons_resisted(sheet: Msg | None, target: Msg) -> bool:
    lines = _weapon_lines(sheet).values()
    return bool(lines) and all(factor(target, a["damage_type"]) < 1 for a in lines)


def _best_weapon(sheet: Msg | None, target: Msg) -> float:
    lines = _weapon_lines(sheet).values()
    return max((_average(a["damage"]) * factor(target, a["damage_type"]) for a in lines), default=0)


def attack_option(chances: list[Msg], sheet: Msg | None, target: Msg) -> str | None:
    lines = _weapon_lines(sheet)
    usable = [c for c in chances if c.get("in_range", True) and c["option"] in lines]
    weights = {c["option"]: factor(target, lines[c["option"]]["damage_type"]) for c in usable}
    if all(w == 1.0 for w in weights.values()):
        return None

    def expected(chance: Msg) -> float:
        line = lines[chance["option"]]
        return chance["probability"] * _average(line["damage"]) * weights[chance["option"]]

    return max(usable, key=expected)["option"]


def _types(effects: Sequence[Effect]) -> list[str]:
    found: list[str] = []
    for effect in effects:
        if isinstance(effect, DamageEffect):
            found.append(effect.damage_type)
        elif isinstance(effect, SaveEffect):
            found += _types(effect.on_fail)
        elif isinstance(effect, AttackRollEffect):
            found += _types(effect.on_hit)
        elif isinstance(effect, MultiTargetEffect):
            found += _types(effect.effects)
    return found


@cache
def _spell_types(spell_id: str) -> tuple[str, ...]:
    found = spell_defs().find(spell_id)
    return () if found is None else tuple(_types(found.effects))


def spell_factor(spell_id: str, target: Msg) -> float | None:
    """The share of the spell's damage the target takes (its worst type); None: no damage."""
    types = _spell_types(spell_id)
    return min(factor(target, t) for t in types) if types else None


def best_damage_spell(options: list[str], target: Msg) -> str | None:
    rated = [(s, spell_factor(s, target)) for s in options]
    usable = [(s, 1.0 if f is None else f) for s, f in rated if f is None or f > 0]
    return max(usable, key=lambda sf: sf[1])[0] if usable else None


def cantrip_for(plan: Plan, sheet: Msg | None, target: Msg) -> str | None:
    """A cantrip to cast instead of the default this turn (module docstring), or None."""
    casting = (sheet or {}).get("spellcasting") or {}
    known = [c["index"] for c in casting.get("cantrips", [])]
    rated = [(s, spell_factor(s, target)) for s in known]
    damaging = [(s, f) for s, f in rated if f is not None and f > 0]
    if plan.role == "caster" and plan.cantrip is not None:
        base = spell_factor(plan.cantrip, target)
        floor = 1.0 if base is None else base
    elif weapons_resisted(sheet, target):
        floor = max(factor(target, a["damage_type"]) for a in _weapon_lines(sheet).values())
    else:
        return None
    better = [(s, f) for s, f in damaging if f > floor]
    return max(better, key=lambda sf: sf[1])[0] if better else None


@cache
def _damage_use(use_id: str) -> DamageUse | None:
    use = next((u for u in item_use_data().uses if u.id == use_id), None)
    return use.effect if use is not None and isinstance(use.effect, DamageUse) else None


def _gear_damage(use_id: str, target: Msg) -> float:
    effect = _damage_use(use_id)
    index = target.get("monster_index")
    foe = _foe(index) if index else None
    if effect is None:
        return 0.0
    if effect.creature_types and (
        foe is None or creature_type_of(foe) not in effect.creature_types
    ):
        return 0.0
    return _average(effect.dice) * factor(target, effect.damage_type)


def resist_gear(
    plan: Plan, combat: Msg, gear: list[Msg], sheet: Msg | None, target: Msg
) -> Msg | None:
    """Carried damage gear thrown at a target that resists every weapon (docstring), or None."""
    me = token_of(combat, plan.hero_id)
    if me is None or not (combat.get("economy") or {}).get("action"):
        return None
    if not weapons_resisted(sheet, target):
        return None
    if target["zone_id"] not in {me["zone_id"], *touching(combat, me["zone_id"])}:
        return None
    weapon = _best_weapon(sheet, target)
    aimed = [g for g in gear if g.get("target") == "creature"]
    rated = [(g, _gear_damage(g["use_id"], target)) for g in aimed]
    better = [(g, d) for g, d in rated if d > weapon]
    if not better:
        return None
    use = max(better, key=lambda gd: gd[1])[0]
    return {
        "type": "use_item",
        "actor_id": plan.hero_id,
        "item": use["item"],
        "use_id": use["use_id"],
        "target_id": target["creature_id"],
    }
