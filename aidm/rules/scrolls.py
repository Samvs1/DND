"""Wizard scroll copying (SPEC 7.2, BG3): learn a spell from a found scroll into the spellbook.

BG3 rule (docs/RULES_DECISIONS.md M2.5): no Arcana check and no time cost; copying costs gold per
spell level (the `scroll_copy` feature hook: 50 gold per level, SRD's copying cost; Evocation
Savant halves evocation copies) and consumes the scroll. A refusal changes nothing.

Public API:
- `SCROLL_PREFIX` ("scroll-of-"): a spell scroll is the inventory item `scroll-of-<spell index>`;
  `scroll_item_index(spell) -> str`, `scroll_spell_index(item) -> str | None`.
- `ScrollCopyRefusal` (StrEnum) and `ScrollCopyRefused(ValueError)` with `.reason`.
- `copy_scroll_to_spellbook(wizard, item, regs) -> list[AnyEvent]`: `GoldChanged` (when the
  cost is not 0), `InventoryChanged` (one scroll used up) and `SpellbookChanged`. Refused when
  the creature is not a PC, has no scroll-copy feature, does not carry the scroll, the spell is
  unknown, a cantrip, not on its class list (expanded grants included), above its highest slot
  level, already in the book, or the gold is short.
- `scroll_copy_lines(wizard, regs) -> list[ScrollCopyLine]` (M27.7, the Spellbook tab): each
  carried scroll this hero could copy now, with its cost; `affordable` False when only the gold
  is short. Empty for anyone without the scroll-copy feature.
"""

from enum import StrEnum

from aidm.data.character_data import CharacterRegistries
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged, SpellbookChanged
from aidm.models.sheet import ScrollCopyLine
from aidm.models.state import Creature
from aidm.rules.feature_build import scroll_copy_cost
from aidm.rules.level_spells import learnable_spells
from aidm.rules.spellcasting import max_spell_level

SCROLL_PREFIX = "scroll-of-"


class ScrollCopyRefusal(StrEnum):
    NOT_A_PC = "not_a_pc"
    NO_SCROLL_COPY = "no_scroll_copy"
    NO_SCROLL = "no_scroll"
    UNKNOWN_SPELL = "unknown_spell"
    CANTRIP = "cantrip"
    NOT_CLASS_SPELL = "not_class_spell"
    LEVEL_TOO_HIGH = "level_too_high"
    ALREADY_KNOWN = "already_known"
    NOT_ENOUGH_GOLD = "not_enough_gold"


class ScrollCopyRefused(ValueError):
    """Copying is not possible; nothing was spent or consumed."""

    def __init__(self, reason: ScrollCopyRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason


def scroll_item_index(spell: str) -> str:
    return f"{SCROLL_PREFIX}{spell}"


def scroll_spell_index(item: str) -> str | None:
    if not item.startswith(SCROLL_PREFIX) or len(item) == len(SCROLL_PREFIX):
        return None
    return item[len(SCROLL_PREFIX) :]


def copy_scroll_to_spellbook(
    wizard: Creature, item: str, regs: CharacterRegistries
) -> list[AnyEvent]:
    pc = wizard.pc
    if pc is None:
        raise ScrollCopyRefused(ScrollCopyRefusal.NOT_A_PC, wizard.id)
    held = next((row.qty for row in pc.inventory if row.item == item), 0)
    if held < 1:
        raise ScrollCopyRefused(ScrollCopyRefusal.NO_SCROLL, item)
    spell_index = scroll_spell_index(item)
    spell = regs.spells.find(spell_index) if spell_index else None
    if spell is None:
        raise ScrollCopyRefused(ScrollCopyRefusal.UNKNOWN_SPELL, item)
    ids = [*pc.features, *pc.traits]
    cost = scroll_copy_cost(ids, pc.level, regs.features, spell.level, spell.school.index)
    if cost is None:
        raise ScrollCopyRefused(ScrollCopyRefusal.NO_SCROLL_COPY, pc.class_index)
    cls = regs.classes.get(pc.class_index)
    if spell.level == 0:
        raise ScrollCopyRefused(ScrollCopyRefusal.CANTRIP, spell.index)
    if spell.level > max_spell_level(cls, pc.level):
        raise ScrollCopyRefused(ScrollCopyRefusal.LEVEL_TOO_HIGH, spell.index)
    if spell.index not in learnable_spells(cls, pc.level, ids, pc.subclass, regs):
        raise ScrollCopyRefused(ScrollCopyRefusal.NOT_CLASS_SPELL, spell.index)
    if spell.index in pc.spellbook:
        raise ScrollCopyRefused(ScrollCopyRefusal.ALREADY_KNOWN, spell.index)
    if pc.gold < cost:
        raise ScrollCopyRefused(ScrollCopyRefusal.NOT_ENOUGH_GOLD, f"{pc.gold} < {cost}")
    events: list[AnyEvent] = []
    if cost:
        events.append(GoldChanged(creature_id=wizard.id, delta=-cost, gold=pc.gold - cost))
    events.append(InventoryChanged(creature_id=wizard.id, item=item, delta=-1, qty=held - 1))
    book = [*pc.spellbook, spell.index]
    events.append(SpellbookChanged(creature_id=wizard.id, spellbook=book))
    return events


def _copy_line(wizard: Creature, item: str, regs: CharacterRegistries) -> ScrollCopyLine | None:
    pc = wizard.pc
    index = scroll_spell_index(item)
    spell = regs.spells.find(index) if index else None
    if pc is None or spell is None:
        return None
    try:
        copy_scroll_to_spellbook(wizard, item, regs)
    except ScrollCopyRefused as refused:
        if refused.reason is not ScrollCopyRefusal.NOT_ENOUGH_GOLD:
            return None
    ids = [*pc.features, *pc.traits]
    cost = scroll_copy_cost(ids, pc.level, regs.features, spell.level, spell.school.index) or 0
    return ScrollCopyLine(
        item=item,
        spell=spell.index,
        name=spell.name,
        level=spell.level,
        cost=cost,
        affordable=pc.gold >= cost,
    )


def scroll_copy_lines(wizard: Creature, regs: CharacterRegistries) -> list[ScrollCopyLine]:
    pc = wizard.pc
    if pc is None:
        return []
    items = dict.fromkeys(e.item for e in pc.inventory if e.item.startswith(SCROLL_PREFIX))
    lines = (_copy_line(wizard, item, regs) for item in items)
    return [line for line in lines if line is not None]
