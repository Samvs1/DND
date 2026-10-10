"""Downed heroes outside a fight (M20.2, owner playtest 3: a hero at 0 HP after a won fight could
not be raised by anything outside a fight; the party walked her into the next fight, dying).

- A fight that ends without a defeat leaves every dying hero stable (`stabilise_after_fight`;
  SRD 5.1 "Stabilizing a Creature": with the fight over an ally has all the time a Medicine check
  or a healer's kit needs; docs/RULES_DECISIONS.md M20.2).
- Outside a fight a standing hero helps a downed ally up to 1 HP at no cost (`help_up_events`,
  BG3 Help; in a fight the Help action does the same for an action, `combat_actions.help_command`).
  The 1 HP goes through `resolve_healing`, so the 0-HP unconscious condition and the death save
  counters are cleared the same way as by any healing.

Public API: `HelpUpRefusal`, `HelpUpRefused(reason, detail)`, `downed_heroes(state)`,
`stabilise_after_fight(state) -> list[AnyEvent]`,
`help_up_events(state, helper_id, target_id) -> list[AnyEvent]`.
"""

from enum import StrEnum

from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, Stabilized
from aidm.models.state import Creature, GameState
from aidm.rules.damage import resolve_healing
from aidm.rules.death import is_dying

HELP_UP_HP = 1


class HelpUpRefusal(StrEnum):
    IN_FIGHT = "help_up_in_fight"
    HELPER_DOWN = "help_up_helper_down"
    UNKNOWN_TARGET = "help_up_unknown_target"
    NOT_DOWN = "help_up_not_down"
    FALLEN = "help_up_fallen"


class HelpUpRefused(ValueError):
    def __init__(self, reason: HelpUpRefusal, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def downed_heroes(state: GameState) -> list[Creature]:
    """Heroes at 0 HP who are still alive, by id."""
    return sorted(
        (c for c in state.creatures.values() if c.pc is not None and not c.dead and c.hp <= 0),
        key=lambda c: c.id,
    )


def stabilise_after_fight(state: GameState) -> list[AnyEvent]:
    return [Stabilized(creature_id=c.id) for c in downed_heroes(state) if is_dying(c)]


def _in_fight(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def help_up_events(state: GameState, helper_id: str, target_id: str) -> list[AnyEvent]:
    if _in_fight(state):
        raise HelpUpRefused(HelpUpRefusal.IN_FIGHT, "In a fight, use Help on your turn.")
    helper = state.creatures.get(helper_id)
    if helper is None or helper.pc is None or helper.dead or helper.hp <= 0:
        raise HelpUpRefused(HelpUpRefusal.HELPER_DOWN, "You need to be on your feet to help.")
    target = state.creatures.get(target_id)
    if target is None or target.pc is None or target.id == helper.id:
        raise HelpUpRefused(HelpUpRefusal.UNKNOWN_TARGET, "No hero like that is here.")
    if target.dead:
        detail = f"{target.name} has fallen; only the Scribe can write them back."
        raise HelpUpRefused(HelpUpRefusal.FALLEN, detail)
    if target.hp > 0:
        raise HelpUpRefused(HelpUpRefusal.NOT_DOWN, f"{target.name} is already on their feet.")
    return resolve_healing(target, HELP_UP_HP)
