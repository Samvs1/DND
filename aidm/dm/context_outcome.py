"""The turn's outcome in plain words for the context pack (M43.3, contract rule D1).

Built only through THE context builder (`aidm.dm.context`, the EVENTS section, never trimmed),
from the events' own fields, no phrase rows:
- what did not happen and why: every refusal logged since the last narration
  (`Memory.untold`, kept by the reducer) that the telling was not handed as an event:
  `Rook tried "casts magic missile at Bandit B": nothing happened, because <reason>.`;
- who did what, where the event names its actor: damage (`DamageTaken.source_id`), a kill (the
  last damage on the creature that died, in the same events), a condition another creature
  caused (`ActiveCondition.source_id`) and a spell cast in a fight (`SpellCast.caster_id`;
  casts at the scene have their own line, `aidm.dm.cast_text`).
Round 8: four slips followed a refusal the storyteller was not told (AA3, the skiff, the wares,
Vell) and one gave Rook's fire to the rats (r8-typed 466-482).

Public API: `outcome_lines(state, events) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.dm.condition_text import applied_line
from aidm.dm.entities import display_name
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent, ConditionApplied, CreatureDied, DamageTaken
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState


def _name(state: GameState, creature_id: str | None) -> str | None:
    creature = state.creatures.get(creature_id or "")
    return creature.name if creature is not None else None


def _refused(state: GameState, e: ActionImpossible) -> str:
    who = _name(state, e.creature_id) or display_name(e.creature_id)
    tried = f'{who} tried "{e.text.strip()}"' if e.text.strip() else f"{who}'s attempt"
    return f"{tried}: nothing happened, because {e.reason.strip().rstrip('.')}."


def _damage(state: GameState, e: DamageTaken) -> str | None:
    who, whom = _name(state, e.source_id), _name(state, e.creature_id)
    if who is None or whom is None or e.total == 0:
        return None
    kinds = " and ".join(dict.fromkeys(p.damage_type.value for p in e.parts if p.taken))
    whom = "themself" if e.source_id == e.creature_id else whom
    return f"{who} dealt {e.total} {kinds} damage to {whom}."


def _deed(state: GameState, e: AnyEvent, events: Sequence[AnyEvent]) -> str | None:
    if isinstance(e, DamageTaken):
        return _damage(state, e)
    if isinstance(e, CreatureDied):
        hits = [d for d in events if isinstance(d, DamageTaken) and d.creature_id == e.creature_id]
        who, whom = _name(state, hits[-1].source_id) if hits else None, _name(state, e.creature_id)
        return f"{who} killed {whom}." if who and whom and who != whom else None
    if isinstance(e, ConditionApplied) and e.condition.source_id != e.creature_id:
        who, whom = _name(state, e.condition.source_id), _name(state, e.creature_id)
        line = applied_line(whom, e.condition.name) if whom else ""
        return f"{line[:-1]} (caused by {who})." if who and line else None
    if isinstance(e, SpellCast) and not e.at_scene:
        who = _name(state, e.caster_id)
        return f"{who} cast {display_name(e.spell_id)}." if who else None
    return None


def outcome_lines(state: GameState, events: Sequence[AnyEvent]) -> list[str]:
    refused = [_refused(state, e) for e in state.memory.untold if e not in events]
    deeds = [line for e in events if (line := _deed(state, e, events)) is not None]
    return [*refused, *deeds]
