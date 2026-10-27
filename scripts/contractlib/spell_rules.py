"""Contract rule B6 (same act, same rules on every path): a leveled spell spends a slot and
uses its caster's save DC (M43.1)."""

from collections import deque

from aidm.data.class_defs import class_defs
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.spellcasting import spell_save_dc
from scripts.contractlib.save import Finding, Visitor

WINDOW = 12  # events before a cast in which its slot is spent or its scroll used


def _expected_dc(caster: Creature) -> int | None:
    if caster.pc is None:
        return None
    definition = class_defs().find(caster.pc.class_index)
    if definition is None or definition.spellcasting is None:
        return None
    return spell_save_dc(caster, definition)


class SpellPaths(Visitor):
    def __init__(self) -> None:
        self.spent: dict[str, int] = {}  # caster -> seq of the last slot spent
        self.used: dict[str, int] = {}  # caster -> seq of the last item (a scroll) used
        self.casts: deque[tuple[int, str]] = deque(maxlen=WINDOW)  # (seq, caster) of leveled casts

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]:
        if event.type == "resource_set":  # a slot, or a feature use (racial spells)
            old = state.creatures[event.creature_id].resources.get(event.key)
            if old is not None and event.resource.current < old.current:
                self.spent[event.creature_id] = seq
        elif event.type == "item_used" or (event.type == "inventory_changed" and event.delta < 0):
            self.used[event.creature_id] = seq
        elif event.type == "spell_cast":
            return self._cast(seq, event.caster_id, event.cast_level, event.spell_id)
        elif event.type == "check_resolved" and event.source_id and event.result.kind == "save":
            return self._save(seq, state, event.source_id, event.result.dc, event.reason)
        return []

    def _cast(self, seq: int, caster: str, level: int, spell: str) -> list[Finding]:
        self.casts.append((seq, caster))
        if level == 0:
            return []
        near = max(self.spent.get(caster, -99), self.used.get(caster, -99))
        if seq - near <= WINDOW:
            return []
        return [Finding("B6", seq, f"{caster} cast {spell} at level {level} and spent no slot")]

    def _save(self, seq: int, state: GameState, source: str, dc: int, reason: str) -> list[Finding]:
        if not any(who == source and seq - at <= WINDOW for at, who in self.casts):
            return []
        caster = state.creatures.get(source)
        want = _expected_dc(caster) if caster is not None else None
        if want is None or want == dc:
            return []
        return [Finding("B6", seq, f"{source} save DC {dc}, the caster's DC is {want} ({reason})")]
