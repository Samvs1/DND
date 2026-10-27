"""Which of a hero's ready spells it can pay for now (M41.2, round 7 Z5; SPEC 6.2, 7.2). Pure.

r7b-typed 1277: "Tamsin sends a guiding bolt at the armor", with both of Tamsin's slot levels at
0, cast Sacred Flame: the fight menu lists no leveled spell without a slot, so the model took the
cantrip it did list. A ready spell the hero cannot pay for cannot be cast, so no fight entry
offers it; the menu carries it with the reason (`ActionMenu.unready`), and a line that names one
gets it as a NOT OFFERED target (`rules.menu_unoffered`): M43.2: that step is refused with the
reason, never a stand-in spell and never the storyteller's. Out of a fight such a spell is a
`spent` entry the rules refuse in plain words (M36.10a, `rules.menu_casts`): it names the spell,
so it is no stand-in.
- `ready_lines(block)`: the sheet's prepared spell lines, cantrips first.
- `can_pay(creature, spell, resource)`: the cast's own answer (`spell_targets.cast_slot` with no
  slot level asked, on THE slot model `rules.spellcasting`): a cantrip, an at-will spell, an
  innate spell with a use left in its pool, or a leveled spell with a slot of its level or higher
  (upcasting stays possible). The engine has no ritual casting, and a scroll is an item of the
  pack, so nothing else pays for a spell line.
- `no_slot_reason(creature, level)`: "Tamsin has no 1st-level slot left" (no slot pool above the
  level), else "Tamsin has no slot of 1st level or higher left".
- `unready_spells(creature, block, spells)`: one `MenuTarget` per ready spell the hero cannot pay
  for (id the spell index, label "<name> (<reason>)", kind thing), in sheet order.

Public API: `ready_lines`, `can_pay`, `no_slot_reason`, `unready_spells`.
"""

from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.models.action_menu import MenuTarget
from aidm.models.sheet import SpellcastingBlock, SpellLine
from aidm.models.state import Creature
from aidm.rules.command_checks import CommandRefused
from aidm.rules.spell_targets import cast_slot
from aidm.rules.spellcasting import slot_pools

_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def ready_lines(block: SpellcastingBlock) -> list[SpellLine]:
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    return [line for line in lines if line.prepared]


def can_pay(creature: Creature, spell: SpellDef, resource: str | None) -> bool:
    try:
        cast_slot(creature, spell, None, resource)
    except CommandRefused:
        return False
    return True


def no_slot_reason(creature: Creature, level: int) -> str:
    nth = _ORDINALS.get(level, f"{level}th")
    higher = any(ref.level > level for ref, _ in slot_pools(creature))
    what = f"slot of {nth} level or higher" if higher else f"{nth}-level slot"
    return f"{creature.name} has no {what} left"


def unready_spells(
    creature: Creature, block: SpellcastingBlock | None, spells: Registry[SpellDef]
) -> tuple[MenuTarget, ...]:
    if block is None:
        return ()
    out: list[MenuTarget] = []
    for line in ready_lines(block):
        spell = spells.find(line.index)
        if spell is None or can_pay(creature, spell, line.resource):
            continue
        reason = no_slot_reason(creature, spell.level)
        out.append(MenuTarget(id=spell.index, label=f"{line.name} ({reason})", kind="thing"))
    return tuple(out)
