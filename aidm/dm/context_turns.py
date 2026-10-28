"""Whose turn came in a fight telling, for the context pack (M44.4, round 9 BB8).

A telling runs whenever a hero's line is played or a hero's turn opens, so the foes after that
hero in the order have not had their turn yet; round 9 told them lunging and casting all the same.
Built only through THE context builder (`aidm.dm.context`, the EVENTS section, never trimmed),
from the encounter and the events' own fields, no phrase rows. For each living foe that made no
blow in these events (`fight_ledger.acted`), one plain reason:
- surprised (the `surprised` condition on it, or removed in these events): it lost its turn;
- its turn came in these events (`TurnStarted`) and passed with no attack or spell;
- otherwise its turn has not come since the last telling: it comes after this one.

Public API: `turn_lines(state, events) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.dm.fight_ledger import fight_ledger
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.encounter_events import TurnStarted
from aidm.models.events import AnyEvent, ConditionRemoved
from aidm.models.state import GameState
from aidm.rules.encounter import SURPRISED

_WAITING = (
    "Foes whose turn has not come since the last telling (their turns come after this one and are"
    " told then; now they only stand where they are: no step, swing, shot or spell by them)"
)
_SURPRISED = (
    "Surprised foes (caught off guard, they lose their turn: no step, swing, shot or spell)"
)
_PASSED = "Foes whose turn passed in these events with no attack or spell"


def _foes(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    return [
        c.creature_id
        for c in enc.combatants.values()
        if c.side is Side.HOSTILE
        and c.withdrawn is None
        and (foe := state.creatures.get(c.creature_id)) is not None
        and not foe.dead
        and foe.hp > 0
    ]


def turn_lines(state: GameState, events: Sequence[AnyEvent]) -> list[str]:
    foes = _foes(state)
    if not foes:
        return []
    acted = fight_ledger(state, events).acted
    turned = {e.creature_id for e in events if isinstance(e, TurnStarted)}
    woke = {
        e.creature_id for e in events if isinstance(e, ConditionRemoved) and e.name == SURPRISED
    }
    groups: dict[str, list[str]] = {_SURPRISED: [], _PASSED: [], _WAITING: []}
    for cid in foes:
        if cid in acted:
            continue
        foe = state.creatures[cid]
        if cid in woke or any(c.name == SURPRISED for c in foe.conditions):
            groups[_SURPRISED].append(foe.name)
        else:
            groups[_PASSED if cid in turned else _WAITING].append(foe.name)
    return [f"{title}: {', '.join(names)}." for title, names in groups.items() if names]
