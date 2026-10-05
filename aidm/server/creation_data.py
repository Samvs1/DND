"""Read-only creation data for the character wizard (`GET /api/creation-data`, M7.2).

Everything here is public rules data built from the registries (SRD + the data/bg3 overlays):
races with their merged subrace variants, classes (level-1 picks, equipment packages, spell
counts and the SHIPPED spell pools), backgrounds, skill and language names, item names and the
portrait presets. The client mirrors the limits for instant feedback; the server's
`validate_creation` stays authoritative.

Public API: `build_creation_data(regs=None) -> dict[str, object]`, `add_creation_routes(app)`.
"""

from __future__ import annotations

import functools
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from aidm.data.character_data import CharacterRegistries, character_registries
from aidm.data.class_defs import ClassDef
from aidm.data.race_defs import RaceDef, SubraceDef
from aidm.data.spell_defs import shipped_spell_ids
from aidm.data.srd import srd
from aidm.models.abilities import ABILITIES, SKILL_ABILITY, Skill
from aidm.rules.creation_checks import class_spell_indexes, pick_count
from aidm.rules.feature_build import expanded_spell_indexes, feature_effects
from aidm.rules.spellcasting import (
    cantrips_known_count,
    max_spell_level,
    spells_known_count,
)

LEVEL = 1
SPELL_TEXT_CHARS = 220
Json = dict[str, Any]


def _humanise(slug: str) -> str:
    return slug.replace("-", " ").strip().title()


def _item_name(regs: CharacterRegistries, index: str) -> str:
    entry = regs.equipment.find(index) or regs.proficiencies.find(index)
    return entry.name if entry is not None else _humanise(index)


def _feature(regs: CharacterRegistries, feature_id: str) -> Json:
    entry = regs.features.find(feature_id)
    if entry is None:
        return {"id": feature_id, "name": _humanise(feature_id), "summary": ""}
    return {"id": feature_id, "name": entry.name, "summary": entry.summary}


def _picks_for(regs: CharacterRegistries, ids: list[str]) -> tuple[list[Json], list[Json]]:
    """(option picks like draconic ancestry, expertise picks) among the given feature ids."""
    picks: list[Json] = []
    expertise: list[Json] = []
    for feature_id in dict.fromkeys(ids):
        entry = regs.features.find(feature_id)
        if entry is None:
            continue
        if entry.pick is not None:
            options = [_feature(regs, o) for o in entry.pick.options]
            picks.append(
                {**_feature(regs, feature_id), "choose": entry.pick.choose, "options": options}
            )
        for hook in entry.hooks:
            if hook.kind == "expertise":
                expertise.append({**_feature(regs, feature_id), "choose": hook.choose})
    return picks, expertise


def _pick_json(pick: Any) -> Json | None:
    if pick is None:
        return None
    return {"choose": pick.choose, "options": list(pick.options)}


def _grants(regs: CharacterRegistries, part: RaceDef | SubraceDef) -> Json:
    picks, _ = _picks_for(regs, list(part.traits))
    return {
        "ability_bonuses": {b.ability: b.bonus for b in part.ability_bonuses},
        "skills": list(part.skills),
        "tools": list(part.tool_proficiencies),
        "tool_choice": _pick_json(part.tool_choice),
        "languages": list(part.languages),
        "language_choices": part.language_choices,
        "cantrip_choices": part.cantrip_choices,
        "cantrip_class": part.cantrip_class,
        "traits": [_feature(regs, t) for t in part.traits],
        "trait_picks": picks,
    }


def _merge(base: Json, extra: Json) -> Json:
    merged = dict(base)
    bonuses = dict(base["ability_bonuses"])
    for ability, bonus in extra["ability_bonuses"].items():
        bonuses[ability] = bonuses.get(ability, 0) + bonus
    merged["ability_bonuses"] = bonuses
    for key in ("skills", "tools", "languages", "traits", "trait_picks"):
        merged[key] = base[key] + extra[key]
    merged["tool_choice"] = extra["tool_choice"] or base["tool_choice"]
    merged["language_choices"] = base["language_choices"] + extra["language_choices"]
    merged["cantrip_choices"] = base["cantrip_choices"] + extra["cantrip_choices"]
    merged["cantrip_class"] = extra["cantrip_class"] or base["cantrip_class"]
    return merged


def _race(regs: CharacterRegistries, race: RaceDef) -> Json:
    base = _grants(regs, race)
    choice = race.ability_choice
    base["ability_choice"] = (
        {
            "choose": choice.choose,
            "options": list(choice.options),
            "bonus": race.ability_choice_bonus,
        }
        if choice
        else None
    )
    base["skill_choice"] = _pick_json(race.skill_choice)
    return {
        "index": race.index,
        "name": race.name,
        "size": race.size,
        "speed": race.speed,
        "darkvision": race.darkvision,
        "effective": base,
        "subraces": [
            {"index": s.index, "name": s.name, "effective": _merge(base, _grants(regs, s))}
            for s in race.subraces
        ],
    }


def _clip(text: str) -> str:
    """Shorten to whole words (at most SPELL_TEXT_CHARS) and end with an ellipsis when cut."""
    if len(text) <= SPELL_TEXT_CHARS:
        return text
    return text[:SPELL_TEXT_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def _spell_entry(regs: CharacterRegistries, index: str) -> Json:
    spell = regs.spells.get(index)
    text = _clip(spell.desc[0] if spell.desc else "")
    return {
        "index": index,
        "name": spell.name,
        "level": spell.level,
        "school": spell.school.name,
        "casting_time": spell.casting_time,
        "range": spell.range,
        "concentration": spell.concentration,
        "text": text,
    }


def _level_one_feature_ids(cls: ClassDef) -> tuple[list[str], str | None]:
    ids = list(cls.level(LEVEL).features)
    subclass = cls.subclass_index if cls.subclass_level <= LEVEL else None
    if subclass is not None:
        for row in cls.subclass_features:
            if row.level <= LEVEL:
                ids.extend(row.features)
    return list(dict.fromkeys(ids)), subclass


def _casting(
    regs: CharacterRegistries, cls: ClassDef, ids: list[str], sub: str | None
) -> Json | None:
    spec = cls.spellcasting
    if spec is None or spec.first_level > LEVEL:
        return None
    cantrips = class_spell_indexes(regs.spells, cls.index, 0, 0)
    top = max_spell_level(cls, LEVEL)
    levelled = class_spell_indexes(regs.spells, cls.index, 1, top)
    expanded = expanded_spell_indexes(ids, LEVEL, sub, regs.features)
    levelled |= {s for s in expanded if (e := regs.spells.find(s)) and 1 <= e.level <= top}
    picks = spec.spellbook_start if spec.kind == "prepared" else spells_known_count(cls, LEVEL)
    return {
        "ability": spec.ability,
        "kind": spec.kind,
        "cantrip_count": pick_count(cantrips_known_count(cls, LEVEL), cantrips),
        "spell_count": pick_count(picks, levelled),
        "spellbook": spec.spellbook_start > 0,
        "prepares": spec.kind == "prepared",
        "cantrips": sorted(cantrips),
        "spells": sorted(levelled),
    }


def _equipment(regs: CharacterRegistries, cls: ClassDef) -> Json:
    def lines(rows: Any) -> list[Json]:
        return [{"item": r.item, "name": _item_name(regs, r.item), "qty": r.qty} for r in rows]

    return {
        "fixed": lines(cls.equipment.fixed),
        "choices": [
            {"id": c.id, "label": c.label, "options": [lines(option) for option in c.options]}
            for c in cls.equipment.choices
        ],
    }


def _class(regs: CharacterRegistries, cls: ClassDef) -> Json:
    ids, subclass = _level_one_feature_ids(cls)
    picks, expertise = _picks_for(regs, ids)
    effects = feature_effects(ids, LEVEL, regs.features)
    choices = [
        {
            "id": c.id,
            "kind": c.kind,
            "choose": c.pick.choose,
            "options": [_feature(regs, o) for o in c.pick.options],
        }
        for c in cls.choices
        if c.level <= LEVEL
    ]
    return {
        "index": cls.index,
        "name": cls.name,
        "hit_die": cls.hit_die,
        "primary": list(cls.primary_abilities),
        "saves": list(cls.saving_throws),
        "armor": [_item_name(regs, a) for a in cls.armor],
        "weapons": [_item_name(regs, w) for w in cls.weapons],
        "tools": list(cls.tools),
        "skill_choice": _pick_json(cls.skill_choice),
        "equipment": _equipment(regs, cls),
        "features": [_feature(regs, f) for f in ids],
        "class_choices": choices,
        "feature_picks": picks,
        "expertise": expertise,
        "feature_skills": list(effects.skills),
        "casting": _casting(regs, cls, ids, subclass),
    }


def _portraits(regs: CharacterRegistries) -> list[Json]:
    out: list[Json] = [
        {"id": f"class.{c.index}", "key": f"portrait.class.{c.index}", "label": c.name}
        for c in regs.classes.all()
    ]
    for race in regs.races.all():
        for sex in ("f", "m"):
            out.append(
                {
                    "id": f"race.{race.index}.{sex}",
                    "key": f"portrait.race.{race.index}.{sex}",
                    "label": f"{race.name} {1 if sex == 'f' else 2}",
                    "race": race.index,
                }
            )
    return out


def _background(regs: CharacterRegistries, index: str) -> Json:
    entry = regs.backgrounds.get(index)
    return {
        "index": entry.index,
        "name": entry.name,
        "skills": list(entry.skills),
        "tools": list(entry.tools),
        "flavour": entry.flavour,
        "gear": [
            {"item": g.item, "name": _item_name(regs, g.item), "qty": g.qty} for g in entry.gear
        ],
    }


def _race_cantrip_pools(regs: CharacterRegistries) -> dict[str, list[str]]:
    """Class spell lists that racial cantrips draw from (high elf: wizard), shipped only."""
    parts = [*regs.races.all(), *(s for r in regs.races.all() for s in r.subraces)]
    names = {p.cantrip_class for p in parts if p.cantrip_class}
    return {n: sorted(class_spell_indexes(regs.spells, n, 0, 0)) for n in sorted(names)}


def build_creation_data(regs: CharacterRegistries | None = None) -> Json:
    regs = regs or character_registries()
    classes = [_class(regs, c) for c in regs.classes.all()]
    wanted = {
        s
        for c in classes
        if c["casting"]
        for s in c["casting"]["cantrips"] + c["casting"]["spells"]
    }
    race_pools = _race_cantrip_pools(regs)
    wanted |= {s for pool in race_pools.values() for s in pool}
    shipped = shipped_spell_ids()
    skills = {
        s.value: {"name": srd().skills.get(s.value).name, "ability": SKILL_ABILITY[s].value}
        for s in Skill
    }
    tool_ids = {
        t for r in regs.races.all() for t in (r.tool_choice.options if r.tool_choice else ())
    }
    return {
        "abilities": [a.value for a in ABILITIES],
        "races": [_race(regs, r) for r in regs.races.all()],
        "classes": classes,
        "backgrounds": [_background(regs, b.index) for b in regs.backgrounds.all()],
        "skills": skills,
        "languages": [{"index": x.index, "name": x.name} for x in regs.languages.all()],
        "tools": {
            t: _item_name(regs, t)
            for t in sorted(tool_ids | {t for c in classes for t in c["tools"]})
        },
        "race_cantrips": race_pools,
        "spells": {s: _spell_entry(regs, s) for s in sorted(wanted & shipped)},
        "portraits": _portraits(regs),
    }


@functools.cache
def _cached() -> Json:
    return build_creation_data()


def add_creation_routes(app: FastAPI) -> None:
    @app.get("/api/creation-data")
    def creation_data() -> JSONResponse:
        return JSONResponse(_cached(), headers={"Cache-Control": "no-cache"})
