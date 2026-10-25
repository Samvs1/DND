"""THE menu builder: the acting hero's legal actions right now (M36, SPEC 6.2). Pure.

`build_menu(state, actor_id, regs)` dispatches on where the hero stands:
- an active fight the hero is in, on the hero's own open turn: the fight menu
  (`rules.menu_fight`);
- an active fight, not the hero's turn: an `off_turn` menu with no entries (the session answers
  "not your turn" with no model call);
- out of a fight: the `explore` scope (its scene entries arrive in M36.3; empty until then).

Public API: `build_menu(state, actor_id, regs) -> ActionMenu`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import ActionMenu, MenuScope
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.rules.menu_fight import fight_menu


def build_menu(state: GameState, actor_id: str, regs: CombatRegistries) -> ActionMenu:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE and actor_id in enc.combatants:
        if enc.turn_open and enc.active_id() == actor_id:
            return fight_menu(state, actor_id, regs)
        return ActionMenu(scope=MenuScope.OFF_TURN, actor_id=actor_id)
    return ActionMenu(scope=MenuScope.EXPLORE, actor_id=actor_id)
