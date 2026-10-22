"""The one-line summary of a spell that has no roll (M27.11, review fix 3): "Elowen reads Sleep:
Goblin A, Goblin B asleep". The strip under the board and THIS ROUND show it, so a Sleep from a
scroll or a slot is not silent. Built from the existing events (the spell cast, then the conditions
it applied), never stored: `PublicFeed` feeds it and `rebuild` replays it.

A spell has no roll when no effect is an attack roll or a save (`rollless`). The line is held until
the first event that is not part of the cast, then sent with the seq of the cast.

Public API: `SpellLine`, `rollless(spell_id)`, `SCROLL_READ`.
"""

from dataclasses import dataclass, field

from aidm.data.spell_defs import Effect, MultiTargetEffect, spell_defs
from aidm.dm.condition_text import condition_label
from aidm.dm.entities import display_name
from aidm.models.combat_events import SpellCast
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import (
    AnyEvent,
    ConcentrationStarted,
    ConditionApplied,
    DiceRolled,
    InventoryChanged,
    ResourceSet,
)
from aidm.models.item_events import ItemUsed
from aidm.models.protocol_server import EventMsg
from aidm.models.state import GameState

SCROLL_READ = "scroll-read"
_PART_OF_A_CAST = (EconomyChanged, ResourceSet, DiceRolled, InventoryChanged, ConcentrationStarted)


def _has_roll(effects: tuple[Effect, ...]) -> bool:
    for effect in effects:
        if effect.type in ("attack_roll", "save"):
            return True
        if isinstance(effect, MultiTargetEffect) and _has_roll(effect.effects):
            return True
    return False


def rollless(spell_id: str) -> bool:
    spell = spell_defs().find(spell_id)
    return spell is not None and not _has_roll(spell.effects)


@dataclass
class _Pending:
    seq: int
    caster_id: str
    verb: str
    spell: str
    hit: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def _who(state: GameState, creature_id: str) -> str:
    creature = state.creatures.get(creature_id)
    return creature.name if creature is not None else "someone"


class SpellLine:
    def __init__(self) -> None:
        self._pending: _Pending | None = None
        self._reader: str | None = None

    def before(self, state: GameState, event: AnyEvent) -> EventMsg | None:
        """Called before an event is projected: returns the summary when `event` ends the cast."""
        pending = self._pending
        if pending is None:
            return None
        if isinstance(event, ConditionApplied) and event.condition.source_id == pending.caster_id:
            hit = (_who(state, event.creature_id), condition_label(event.condition.name).lower())
            pending.hit.append(hit)
            return None
        if isinstance(event, _PART_OF_A_CAST + (ItemUsed,)):
            return None
        return self.finish(state)

    def after(self, state: GameState, seq: int, event: AnyEvent) -> None:
        """Called after the event was projected: a roll-less cast opens a pending line."""
        if isinstance(event, ItemUsed):
            self._reader = event.creature_id if event.use_id == SCROLL_READ else None
        elif isinstance(event, SpellCast) and rollless(event.spell_id):
            verb = "reads" if self._reader == event.caster_id else "casts"
            self._pending = _Pending(seq, event.caster_id, verb, display_name(event.spell_id))
            self._reader = None

    def finish(self, state: GameState) -> EventMsg | None:
        pending, self._pending = self._pending, None
        if pending is None:
            return None
        text = f"{_who(state, pending.caster_id)} {pending.verb} {pending.spell}"
        groups: dict[str, list[str]] = {}
        for name, label in pending.hit:
            groups.setdefault(label, []).append(name)
        tail = "; ".join(f"{', '.join(names)} {label}" for label, names in groups.items())
        line = f"{text}: {tail}" if tail else f"{text}."
        return EventMsg(seq=pending.seq, kind="spell_cast", line=line, subject_id=pending.caster_id)
