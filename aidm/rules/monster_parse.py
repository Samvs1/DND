"""SRD monster action blocks -> attack profiles and spell-DSL pseudo spells (M3.8).

The stat block's structured fields carry the numbers (attack bonus, DC, damage dice and types);
the description is read only for geometry (melee/ranged, reach, range, area). Everything the
catalog executes is an existing engine shape: `AttackProfile` for THE attack path, and a
`SpellDef` (a "pseudo spell", level 0, school "monster") for save effects and on-hit riders, run
by THE spell effect interpreter. Rules decisions (docs/RULES_DECISIONS.md M3.8):
- A damage choice (`choose`, e.g. a spear one- or two-handed) keeps its first option.
- Reach never leaves the zone: every melee attack needs the same zone (zone model, SPEC 7.3);
  "range N/M ft." becomes the zone range band.
- Areas: a cone, line, radius, sphere or cube of 30 ft or less, or "each creature within N ft"
  (N <= 30), hits the monster's own zone; a longer cone or line targets one zone within its
  length (the own zone or one hop at 60 ft); "within N ft" beyond 30 ft hits the own zone and
  its neighbours. Anything else is a single creature within the first "N ft" in the text
  (touch, the same zone, when the text names no distance).
- A save's success_type comes from the data, except that a text saying "half as much damage"
  halves (the 5e-bits data lists some breath weapons, e.g. the adult red dragon's, as "none").

Public API:
- `flat_parts(damage) -> list[ActionDamage]`: plain damage blocks, choices resolved.
- `attack_profiles(key, name, desc, bonus, parts) -> tuple[AttackProfile | None, AttackProfile |
  None]`: the melee and ranged profiles (key and "<key>-ranged" when both exist).
- `on_hit_spell(key, parts, overlay) -> tuple[SpellDef | None, int]`: the riders run after a hit
  (damage parts with their own save DC, plus overlay effects) and their DC.
- `save_spell(key, desc, dc, parts, overlay) -> SpellDef | None`: a save action (breath weapon,
  wing beat); None when it has neither damage nor overlay effects.
"""

import re
from collections.abc import Sequence
from typing import Any

from aidm.data.monster_overlay import ActionOverlay
from aidm.data.spell_defs import SpellDef
from aidm.data.srd_monster_actions import ActionDamage, ActionDc
from aidm.models.combat import AttackEconomy, AttackProfile, ExtraDamage
from aidm.models.damage import DamageType
from aidm.models.features import AttackContext
from aidm.rules.attack_profiles import weapon_die
from aidm.rules.dice import DiceError, parse_dice

SELF_AREA_MAX_FEET = 30
MELEE_REACH = 5
PSEUDO_SCHOOL = "monster"
_REACH = re.compile(r"reach (\d+) ?ft")
_RANGE = re.compile(r"range (\d+)(?:/(\d+))? ?ft")
_AREA = re.compile(r"(\d+)-foot[- ](?:\w+[- ])?(cone|line|radius|sphere|cube)")
_WITHIN = re.compile(r"each creature within (\d+) ?(?:ft|feet)")
_FEET = re.compile(r"(\d+) ?(?:ft|feet)")
_HALF = "half as much damage"

type Json = dict[str, Any]


def _valid_dice(dice: str | None) -> bool:
    if not dice:
        return False
    try:
        parse_dice(dice)
    except DiceError:
        return False
    return True


def flat_parts(damage: Sequence[ActionDamage]) -> list[ActionDamage]:
    found: list[ActionDamage] = []
    for block in damage:
        if block.options:
            found.extend(flat_parts(block.options[: max(1, block.choose or 1)]))
        elif block.damage_type is not None and _valid_dice(block.damage_dice):
            found.append(block)
    return found


def _profile(
    key: str, name: str, bonus: int, parts: Sequence[ActionDamage], ranged: bool, desc: str
) -> AttackProfile:
    main, extra = parts[0], parts[1:]
    dice = main.damage_dice or ""
    if ranged:
        match = _RANGE.search(desc)
        normal = int(match.group(1)) if match else 30
        long = int(match.group(2)) if match and match.group(2) else None
    else:
        match = _REACH.search(desc)
        normal, long = (int(match.group(1)) if match else MELEE_REACH), None
    return AttackProfile(
        key=key,
        name=name,
        attack_bonus=bonus,
        damage=dice,
        damage_type=DamageType(main.damage_type.index if main.damage_type else "bludgeoning"),
        ranged=ranged,
        range_normal=normal,
        range_long=long,
        context=AttackContext(ranged=ranged, weapon_die=weapon_die(dice)),
        economy=AttackEconomy.ACTION,
        extra_damage=tuple(
            ExtraDamage(dice=p.damage_dice or "", damage_type=DamageType(p.damage_type.index))
            for p in extra
            if p.damage_type is not None
        ),
    )


def attack_profiles(
    key: str, name: str, desc: str, bonus: int, parts: Sequence[ActionDamage]
) -> tuple[AttackProfile | None, AttackProfile | None]:
    plain = [p for p in parts if p.dc is None]
    if not plain:
        return None, None
    header, text = desc.split(":", 1)[0].lower(), desc.lower()
    ranged_ok = "ranged" in header
    melee_ok = "melee" in header or not ranged_ok
    melee = _profile(key, name, bonus, plain, False, text) if melee_ok else None
    ranged_key = f"{key}-ranged" if melee_ok else key
    ranged = _profile(ranged_key, name, bonus, plain, True, text) if ranged_ok else None
    return melee, ranged


def _damage_json(parts: Sequence[ActionDamage]) -> list[Json]:
    return [
        {"type": "damage", "dice": p.damage_dice, "damage_type": p.damage_type.index}
        for p in parts
        if p.damage_type is not None
    ]


def _pseudo(key: str, effects: Sequence[Json], rng: Json, targeting: Json) -> SpellDef:
    return SpellDef.model_validate(
        {
            "index": key,
            "level": 0,
            "school": PSEUDO_SCHOOL,
            "classes": [PSEUDO_SCHOOL],
            "range": rng,
            "targeting": targeting,
            "effects": list(effects),
        }
    )


def _dump(effects: Sequence[Any]) -> list[Json]:
    return [e.model_dump(exclude_none=True) for e in effects]


def on_hit_spell(
    key: str, parts: Sequence[ActionDamage], overlay: ActionOverlay | None
) -> tuple[SpellDef | None, int]:
    effects: list[Json] = []
    dc = overlay.dc if overlay is not None and overlay.dc is not None else 0
    for part in parts:
        if part.dc is None:
            continue
        dc = dc or part.dc.dc_value
        half = "half" if part.dc.success_type == "half" else "none"
        effects.append(
            {
                "type": "save",
                "ability": part.dc.dc_type.index,
                "on_fail": _damage_json([part]),
                "on_success": half,
            }
        )
    if overlay is not None:
        effects.extend(_dump(overlay.on_hit))
    if not effects:
        return None, 0
    return _pseudo(key, effects, {"kind": "touch"}, {"kind": "creature"}), dc


def _area(feet: int) -> tuple[Json, Json]:
    if feet <= SELF_AREA_MAX_FEET:
        return {"kind": "self"}, {"kind": "area", "area": "zone"}
    return {"kind": "feet", "feet": feet}, {"kind": "area", "area": "zone"}


def _save_geometry(desc: str) -> tuple[Json, Json]:
    text = desc.lower()
    area = _AREA.search(text)
    if area:
        return _area(int(area.group(1)))
    within = _WITHIN.search(text)
    if within:
        near = int(within.group(1)) <= SELF_AREA_MAX_FEET
        return {"kind": "self"}, {"kind": "area", "area": "zone" if near else "zone_and_adjacent"}
    feet = _FEET.search(text)
    if feet:
        return {"kind": "feet", "feet": max(MELEE_REACH, int(feet.group(1)))}, {"kind": "creature"}
    return {"kind": "touch"}, {"kind": "creature"}


def save_spell(
    key: str,
    desc: str,
    dc: ActionDc,
    parts: Sequence[ActionDamage],
    overlay: ActionOverlay | None,
) -> SpellDef | None:
    on_fail = _damage_json(parts)
    damaging = bool(on_fail)
    if overlay is not None:
        on_fail.extend(_dump(overlay.on_fail))
    if not on_fail:
        return None
    half = damaging and (dc.success_type == "half" or _HALF in desc.lower())
    save: Json = {
        "type": "save",
        "ability": dc.dc_type.index,
        "on_fail": on_fail,
        "on_success": "half" if half else "none",
    }
    rng, targeting = _save_geometry(desc)
    if overlay is not None and overlay.range is not None:
        rng = overlay.range.model_dump(exclude_none=True)
    if overlay is not None and overlay.targeting is not None:
        targeting = overlay.targeting.model_dump(exclude_none=True)
    return _pseudo(key, [save], rng, targeting)
