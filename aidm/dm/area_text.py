"""The narrator's line for the creatures an area spell left untouched (M40.5, round 7 Z10).

`area_miss_facts(state, events)`: for every area cast in these events, the creatures in its area
it did not affect, with the engine's reason (`aidm.rules.area_misses`: excluded by the spell's
targeting data, saved, no harm, an HP pool spent before them), so the model never tells the
spell working on them. Reason words come from `REASON_TEXT` by reason, never by spell.

Public API: `REASON_TEXT`, `AREA_MISSES`, `area_miss_facts(state, events) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.data.combat_data import combat_registries
from aidm.dm.entities import display_name
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.area_misses import AreaMiss, MissReason, area_misses

REASON_TEXT: dict[MissReason, str] = {
    MissReason.EXCLUDED: "{detail}: the spell cannot affect them",
    MissReason.SAVED: "they resisted it with a save",
    MissReason.NO_HARM: "it did them no harm",
    MissReason.POOL: "too many hit points: its power ran out before them",
    MissReason.UNTOUCHED: "it did not take hold of them",
}
AREA_MISSES = (
    "{spell} did not affect these creatures in its area: {who}. Tell no effect of {spell} on"
    " them: they are exactly as before."
)


def _named(state: GameState, misses: Sequence[AreaMiss]) -> str:
    groups: dict[str, list[str]] = {}
    for miss in misses:
        creature = state.creatures.get(miss.creature_id)
        name = creature.name if creature is not None else display_name(miss.creature_id)
        why = REASON_TEXT[miss.reason].format(detail=miss.detail)
        groups.setdefault(why, []).append(name)
    return "; ".join(f"{' and '.join(names)} ({why})" for why, names in groups.items())


def area_miss_facts(state: GameState, events: Sequence[AnyEvent]) -> list[str]:
    out: list[str] = []
    for event in events:
        if not isinstance(event, SpellCast):
            continue
        spell = combat_registries().spells.find(event.spell_id)
        misses = area_misses(state, spell, event, events) if spell is not None else ()
        if misses:
            who = _named(state, misses)
            out.append(AREA_MISSES.format(spell=display_name(event.spell_id), who=who))
    return out
