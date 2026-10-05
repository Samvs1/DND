"""What the next level asks of a hero (SPEC 7.5): the data behind the level-up dialog.

`level_up_options(creature, regs)` mirrors `aidm.rules.leveling.validate_level_up`: it lists
the subclass, the ability score improvement, class and feature picks (fighting style, expertise),
new cantrips and spells, the swap and the prepared list, with the pools they come from, so a
client can build valid `LevelUpChoices`. It returns None when the hero cannot level up now.

Public API: `level_up_options(creature, regs) -> LevelUpOptions | None`.
"""

from collections.abc import Collection

from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.models.character import PcData
from aidm.models.leveling import LevelUpOptions, PickGroup, PickOption
from aidm.models.state import Creature
from aidm.rules.creation_checks import class_spell_indexes, pick_count
from aidm.rules.feature_build import expertise_counts
from aidm.rules.level_spells import learnable_spells
from aidm.rules.leveling import can_level_up
from aidm.rules.spellcasting import (
    cantrips_known_count,
    prepared_spell_limit,
    spells_known_count,
)


def _words(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


def _spell_group(
    group_id: str, name: str, choose: int, indexes: Collection[str], regs: CharacterRegistries
) -> PickGroup:
    options = [
        PickOption(id=i, name=regs.spells.get(i).name, level=regs.spells.get(i).level)
        for i in sorted(indexes, key=lambda s: (regs.spells.get(s).level, regs.spells.get(s).name))
    ]
    return PickGroup(id=group_id, name=name, choose=choose, options=options)


def _picks(
    cls: ClassDef, level: int, features: list[str], creature: Creature, regs: CharacterRegistries
) -> tuple[list[PickGroup], list[PickGroup]]:
    chosen = [
        PickGroup(
            id=c.id,
            name=_words(c.id),
            choose=c.pick.choose,
            options=[PickOption(id=o, name=_words(o)) for o in c.pick.options],
        )
        for c in cls.choices
        if c.level == level
    ]
    chosen_features: list[PickGroup] = []
    for feature_id in dict.fromkeys(features):
        entry = regs.features.find(feature_id)
        if entry is not None and entry.pick is not None:
            options = [PickOption(id=o, name=regs.features.get(o).name) for o in entry.pick.options]
            chosen_features.append(
                PickGroup(id=feature_id, name=entry.name, choose=entry.pick.choose, options=options)
            )
    for feature_id, count in expertise_counts(features, regs.features).items():
        taken = {s.value for s in creature.skill_expertise}
        skills = [s.value for s in creature.skill_proficiencies if s.value not in taken]
        chosen_features.append(
            PickGroup(
                id=feature_id,
                name=regs.features.get(feature_id).name,
                choose=count,
                options=[PickOption(id=s, name=_words(s)) for s in skills],
            )
        )
    return chosen, chosen_features


def _spells(
    pc: PcData,
    cls: ClassDef,
    level: int,
    features: list[str],
    subclass: str | None,
    creature: Creature,
    regs: CharacterRegistries,
) -> dict[str, object]:
    casting = cls.spellcasting
    if casting is None or level < casting.first_level:
        return {}
    out: dict[str, object] = {}
    cantrip_pool = class_spell_indexes(regs.spells, cls.index, 0, 0)
    taken = set(pc.cantrips + pc.race_cantrips)
    new = cantrips_known_count(cls, level) - cantrips_known_count(cls, level - 1)
    count = pick_count(new, cantrip_pool, taken)
    if count:
        out["cantrips"] = _spell_group("cantrips", "Cantrips", count, cantrip_pool - taken, regs)
    pool = learnable_spells(cls, level, features, subclass, regs)
    if casting.kind == "prepared":
        book = casting.spellbook_start > 0
        have = set(pc.spellbook)
        count = pick_count(casting.spellbook_per_level if book else 0, pool, have)
        if count:
            out["spells"] = _spell_group("spells", "Spellbook", count, pool - have, regs)
        limit = prepared_spell_limit(cls, level, creature.abilities)
        allowed = pool if not book else (have | pool)
        out["prepared"] = _spell_group("prepared", "Prepared", limit, allowed, regs)
        return out
    known = set(pc.spells_known)
    count = pick_count(
        spells_known_count(cls, level) - spells_known_count(cls, level - 1), pool, known
    )
    if count:
        out["spells"] = _spell_group("spells", "Spells", count, pool - known, regs)
    out["replace_from"] = [
        PickOption(id=s, name=regs.spells.get(s).name, level=regs.spells.get(s).level)
        for s in pc.spells_known
    ]
    return out


def level_up_options(creature: Creature, regs: CharacterRegistries) -> LevelUpOptions | None:
    pc = creature.pc
    if pc is None or not can_level_up(creature):
        return None
    cls, level = regs.classes.get(pc.class_index), pc.level + 1
    due_sub = level == cls.subclass_level
    subclass = cls.subclass_index if due_sub else pc.subclass
    features = list(cls.level(level).features)
    if subclass is not None:
        features += [f for row in cls.subclass_features if row.level == level for f in row.features]
    known = [f for f in features if f in regs.features]
    class_picks, feature_picks = _picks(cls, level, known, creature, regs)
    extra = _spells(pc, cls, level, [*pc.features, *known, *pc.traits], subclass, creature, regs)
    return LevelUpOptions.model_validate(
        {
            "level": level,
            "subclass": PickOption(id=cls.subclass_index, name=_words(cls.subclass_index))
            if due_sub
            else None,
            "asi": cls.level(level).asi,
            "class_choices": class_picks,
            "feature_choices": feature_picks,
            **extra,
        }
    )
