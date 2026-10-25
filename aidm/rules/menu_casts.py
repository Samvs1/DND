"""Out-of-fight casts on the menu (M36.3, SPEC 6.2). Pure.

Every spell the hero can cast now (a ready cantrip, or a ready leveled spell with a slot of its
level or higher, `menu_magic.lowest_slot`; a spell paid from a race or feature pool is listed and
the rules answer an empty pool), labelled from its own data (`menu_labels.spell_label`). M36.10a:
a ready leveled spell with no slot left stays listed, `spent` and noted NO_SLOT (never a strike at
a waiting foe), so a typed cast of it is refused by the rules in plain words (M30.2b: never a free
spell through the storyteller):
- a spell that strikes no one and takes creatures (healing, a ward, a buff) aims at the heroes,
  the hero first (`rules.spells.cast_spell`, the typed-healing path);
- any other spell (self, a point or an area, or a hostile spell with no one to strike) is cast at
  the scene (`rules.spells.scene_cast`: the slot is spent, nothing moves);
- while a foe's offer waits here a hostile spell (`spell_targets.strikes_creatures`: an attack,
  a save, damage, an HP pool such as Sleep) is a strike at the offer's foes (`starts_fight`): the
  offer is answered as Fight and the cast plays on the hero's turn (M35.2 Y9,
  `rules.waiting_foe.cast_starts_fight`), never a scene cast.

M36.4: `feature:<name>`: a class feature usable out of a fight (`feature_commands.
usable_out_of_fight`: a healing bonus action such as Second Wind) with uses left, the same id as
in a fight; Action Surge, Turn Undead and Breath Weapon need a fight and are not listed.

Public API: `explore_casts(view)`, `strike_casts(view, foe_ids)`, `explore_features(view)`,
`SCENE_NOTE`, `NO_SLOT`.
"""

from collections.abc import Iterator

from aidm.data.spell_defs import SpellDef
from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.sheet import SpellLine
from aidm.rules.feature_commands import usable_out_of_fight
from aidm.rules.features import command_hook
from aidm.rules.menu_labels import spell_label
from aidm.rules.menu_magic import lowest_slot, needs_of
from aidm.rules.menu_scene_view import SceneMenuView
from aidm.rules.menu_view import slug
from aidm.rules.spell_targets import strikes_creatures

SCENE_NOTE = "cast at the scene"
NO_SLOT = "no spell slot left"


def _castable(view: SceneMenuView) -> Iterator[tuple[SpellDef, SpellLine, int | None, int | None]]:
    """(spell, line, lowest slot level, slots left there) for every spell castable now."""
    block = view.sheet.spellcasting
    if block is None:
        return
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    for line in lines:
        spell = view.regs.spells.find(line.index)
        if spell is None or not line.prepared:
            continue
        if line.level == 0 or line.resource is not None:
            yield spell, line, None, None
            continue
        slot = lowest_slot(block, line.level)
        yield (spell, line, slot[0], slot[1]) if slot is not None else (spell, line, line.level, 0)


def explore_casts(view: SceneMenuView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    party = (view.actor_id, *view.heroes)
    for spell, line, level, left in _castable(view):
        hostile = strikes_creatures(spell)
        if hostile and view.threat:
            continue  # a strike at the waiting foes (`strike_casts`)
        aimed = needs_of(spell) == "creature" and not hostile
        note = NO_SLOT if left == 0 else "" if aimed else SCENE_NOTE
        out.append(
            MenuEntry(
                id=f"cast:{spell.index}",
                kind=ActionKind.CAST,
                label=spell_label(spell, line, left),
                target_ids=party if aimed else (),
                max_targets=max(1, line.target_count) if aimed else 0,
                spent=left == 0,
                note=note,
                spell_id=spell.index,
                slot_level=level,
            )
        )
    return out


def strike_casts(view: SceneMenuView, foe_ids: tuple[str, ...]) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for spell, line, level, left in _castable(view):
        if not strikes_creatures(spell) or left == 0:
            continue
        count = line.target_count if needs_of(spell) == "creature" else len(foe_ids)
        out.append(
            MenuEntry(
                id=f"cast:{spell.index}",
                kind=ActionKind.CAST,
                label=spell_label(spell, line, left),
                target_ids=foe_ids,
                max_targets=max(1, min(count, len(foe_ids))),
                note="starts the fight",
                spell_id=spell.index,
                slot_level=level,
                starts_fight=True,
            )
        )
    return out


def explore_features(view: SceneMenuView) -> list[MenuEntry]:
    hero = view.state.creatures[view.actor_id]
    feats = view.regs.chars.features
    out: list[MenuEntry] = []
    for line in view.sheet.feature_actions:
        hook = command_hook(hero, feats, line.feature)
        if not line.available or hook is None or not usable_out_of_fight(hook):
            continue
        entry_id = f"feature:{slug(line.name)}"
        if any(e.id == entry_id for e in out):
            continue
        parts = [f"heals {line.heal}"] if line.heal else []
        parts += [f"{line.uses_left} left"] if line.uses_left is not None else []
        out.append(
            MenuEntry(
                id=entry_id,
                kind=ActionKind.FEATURE,
                label=f"{line.name} ({', '.join(parts)})" if parts else line.name,
                cost="bonus",
                feature_id=line.feature,
            )
        )
    return out
