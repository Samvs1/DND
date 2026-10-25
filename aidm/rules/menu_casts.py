"""Out-of-fight casts on the menu (M36.3, SPEC 6.2). Pure.

Every spell the hero can cast now (a ready cantrip, or a ready leveled spell with a slot of its
level or higher, `menu_magic.lowest_slot`; a spell paid from a race or feature pool is listed and
the rules answer an empty pool), labelled from its own data (`menu_labels.spell_label`):
- a spell that strikes no one and takes creatures (healing, a ward, a buff) aims at the heroes,
  the hero first (`rules.spells.cast_spell`, the typed-healing path);
- any other spell (self, a point or an area, or a hostile spell with no one to strike) is cast at
  the scene (`rules.spells.scene_cast`: the slot is spent, nothing moves);
- while a foe's offer waits here a hostile spell (`spell_targets.strikes_creatures`: an attack,
  a save, damage, an HP pool such as Sleep) is a strike at the offer's foes (`starts_fight`): the
  offer is answered as Fight and the cast plays on the hero's turn (M35.2 Y9,
  `rules.waiting_foe.cast_starts_fight`), never a scene cast.

Public API: `explore_casts(view)`, `strike_casts(view, foe_ids)`, `SCENE_NOTE`.
"""

from collections.abc import Iterator

from aidm.data.spell_defs import SpellDef
from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.sheet import SpellLine
from aidm.rules.menu_labels import spell_label
from aidm.rules.menu_magic import lowest_slot, needs_of
from aidm.rules.menu_scene_view import SceneMenuView
from aidm.rules.spell_targets import strikes_creatures

SCENE_NOTE = "cast at the scene"


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
        if slot is not None:
            yield spell, line, slot[0], slot[1]


def explore_casts(view: SceneMenuView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    party = (view.actor_id, *view.heroes)
    for spell, line, level, left in _castable(view):
        hostile = strikes_creatures(spell)
        if hostile and view.threat:
            continue  # a strike at the waiting foes (`strike_casts`)
        aimed = needs_of(spell) == "creature" and not hostile
        out.append(
            MenuEntry(
                id=f"cast:{spell.index}",
                kind=ActionKind.CAST,
                label=spell_label(spell, line, left),
                target_ids=party if aimed else (),
                max_targets=max(1, line.target_count) if aimed else 0,
                note="" if aimed else SCENE_NOTE,
                spell_id=spell.index,
                slot_level=level,
            )
        )
    return out


def strike_casts(view: SceneMenuView, foe_ids: tuple[str, ...]) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for spell, line, level, left in _castable(view):
        if not strikes_creatures(spell):
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
