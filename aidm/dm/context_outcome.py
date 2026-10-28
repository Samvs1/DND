"""The turn's outcome in plain words for the context pack (M43.3, contract rule D1).

Built only through THE context builder (`aidm.dm.context`, the EVENTS section, never trimmed),
from the events' own fields, no phrase rows, one line per fact:
- what did not happen and why: every refusal logged since the last narration (`Memory.untold`)
  that the telling was not handed as an event;
- each event's line (`event_text.event_line`), or, where the event names who caused it, the
  line that says so instead: damage (`DamageTaken.source_id`) and a condition another creature
  caused (`ActiveCondition.source_id`). Casts and killing blows in a fight are the fight
  ledger's lines (`fight_ledger.fight_lines`, in the turn facts);
- M44.4 (round 9 BB8): in a fight, why each foe with no blow here did nothing
  (`aidm.dm.context_turns`: surprised, its turn passed, or its turn has not come yet);
- M44.4 (BB9): every shop trade since the last narration (`Memory.untold`), whichever events the
  telling is handed: a buy at the shop panel is told by no narration of its own.

Public API: `outcome_lines(state, events) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.data.item_catalogue import item_catalogue
from aidm.dm.condition_text import applied_line
from aidm.dm.context_turns import turn_lines
from aidm.dm.entities import display_name
from aidm.dm.event_text import event_line
from aidm.models.events import AnyEvent, ConditionApplied, DamageTaken
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState
from aidm.models.trade_events import ItemsTraded


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
    plain = event_line(state, e)  # resistances and immunities: told in the same line
    return f"{who} dealt {e.total} {kinds} damage to {whom}." + (f" {plain}" if plain else "")


def _deed(state: GameState, e: AnyEvent) -> str | None:
    """The line that names who caused the event, in place of its plain line."""
    if isinstance(e, DamageTaken):
        return _damage(state, e)
    if isinstance(e, ItemsTraded):
        return _trade(state, e)
    if isinstance(e, ConditionApplied) and e.condition.source_id != e.creature_id:
        who, whom = _name(state, e.condition.source_id), _name(state, e.creature_id)
        line = applied_line(whom, e.condition.name) if whom else ""
        return f"{line[:-1]} (caused by {who})." if who and line else None
    return None


def _trade(state: GameState, e: ItemsTraded) -> str:
    who = _name(state, e.creature_id) or display_name(e.creature_id)
    keeper = state.world.npcs.get(e.npc_id)
    ware = item_catalogue().find(e.item)
    what = f"{e.qty} x {ware.name if ware is not None else display_name(e.item)}"
    deal = f"sold {what} to" if e.sold else f"bought {what} from"
    return f"{who} {deal} {keeper.name if keeper else display_name(e.npc_id)} for {e.gold} gold."


def _untold(state: GameState, e: ActionImpossible | ItemsTraded) -> str:
    return _trade(state, e) if isinstance(e, ItemsTraded) else _refused(state, e)


def outcome_lines(state: GameState, events: Sequence[AnyEvent]) -> list[str]:
    carried = [_untold(state, e) for e in state.memory.untold if e not in events]
    told = [line for e in events if (line := _deed(state, e) or event_line(state, e))]
    return [*carried, *told, *turn_lines(state, events)]
