"""Generated player-manual tables for hero creation: classes, races, backgrounds (M14.1).

Every function returns one Markdown block built from the typed loaders, never from raw JSON.
"""

from aidm.data.background_defs import background_defs
from aidm.data.class_defs import ClassDef, class_defs
from aidm.data.feature_defs import feature_defs
from aidm.data.manual_md import join, signed, table, words
from aidm.data.race_defs import race_defs


def _is_unsupported(feature_id: str) -> bool:
    if feature_id not in feature_defs():
        return False
    return any(hook.kind == "unsupported" for hook in feature_defs().get(feature_id).hooks)


def _feature_name(cls: ClassDef, feature_id: str) -> str:
    own = {f.id: f.name for f in cls.bg3_features}
    if feature_id in own:
        return own[feature_id]
    name = feature_defs().get(feature_id).name if feature_id in feature_defs() else words(feature_id)
    return f"{name}*" if _is_unsupported(feature_id) else name


def classes_table() -> str:
    rows = []
    for c in class_defs().all():
        magic = c.spellcasting
        casting = f"{magic.ability.upper()} ({magic.kind}, from level {magic.first_level})" if magic else "none"
        rows.append(
            [
                c.name,
                f"d{c.hit_die}",
                "/".join(a.upper() for a in c.primary_abilities),
                "/".join(a.upper() for a in c.saving_throws),
                join(c.armor),
                join(c.weapons),
                casting,
            ]
        )
    head = ["Class", "Hit die", "Main abilities", "Saving throws", "Armour", "Weapons", "Spellcasting"]
    return table(head, rows)


def class_features_table() -> str:
    rows = []
    for c in class_defs().all():
        cells = []
        for row in c.levels:
            names = [_feature_name(c, f) for f in row.features]
            for extra in c.subclass_features:
                if extra.level == row.level:
                    names += [_feature_name(c, f) for f in extra.features]
            cells.append(", ".join(names) if names else "-")
        rows.append([c.name, *cells])
    head = ["Class", "Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]
    note = "An asterisk marks a feature that is on the sheet but that the table cannot use yet."
    return table(head, rows) + "\n\n" + note


def spell_slots_table() -> str:
    rows = []
    for c in class_defs().all():
        if c.spellcasting is None:
            continue
        for row in c.levels:
            if c.spellcasting.kind == "pact":
                level = next((i + 1 for i, n in enumerate(row.slots) if n), 0)
                slots = f"{max(row.slots)} pact slots of level {level}"
            else:
                slots = ", ".join(f"L{i + 1}: {n}" for i, n in enumerate(row.slots) if n) or "none"
            known = "prepared" if row.spells_known is None else str(row.spells_known)
            rows.append([c.name, row.level, row.cantrips_known, known, slots])
    return table(["Class", "Level", "Cantrips", "Spells known", "Spell slots"], rows)


def races_table() -> str:
    rows = []
    for r in race_defs().all():
        bonuses = [f"{b.ability.upper()} {signed(b.bonus)}" for b in r.ability_bonuses]
        if r.ability_choice is not None:
            bonuses.append(f"any {r.ability_choice.choose} others {signed(r.ability_choice_bonus)}")
        subs = [s.name for s in r.subraces]
        rows.append(
            [
                r.name,
                r.size,
                f"{r.speed} ft",
                f"{r.darkvision} ft" if r.darkvision else "none",
                ", ".join(bonuses) or "none",
                ", ".join(subs) or "none",
                join(r.traits),
            ]
        )
    head = ["Race", "Size", "Speed", "Darkvision", "Ability bonuses", "Subraces", "Traits"]
    return table(head, rows)


def backgrounds_table() -> str:
    rows = [
        [b.name, join(b.skills), join(b.tools), f"{b.gold} gp", b.flavour] for b in background_defs().all()
    ]
    return table(["Background", "Skills", "Tools", "Starting gold", "In a few words"], rows)
