"""Legendary actions (M3.8, SRD 5.1 "Legendary Creatures"): at the end of another creature's
turn a legendary monster may spend points (`LEGENDARY_PER_ROUND`, regained at the start of its
own turn by `turns.begin_turn` through the `turn_recharge` of its "legendary-actions" pool) on
one of its catalog's `legendary` options (`rules.monster_catalog`). The option runs exactly like
a turn action (`rules.monster_actions`) but spends no action economy.

Public API:
- `legendary_ready(state) -> list[str]`: the hook the session/AI calls after a `TurnEnded`:
  monsters of the active fight that could take one now (alive, standing, not incapacitated or
  withdrawn, points left, and not the creature whose turn it is or just was). The AI (M3.10)
  decides whether and which.
- `legendary_action(state, monster_id, action, target_ids, target_zone, regs, rng) ->
  list[AnyEvent]`: validated before any event (`CommandRefused`: NOT_IN_COMBAT, NOT_YOUR_TURN
  during or right after its own turn, CANNOT_ACT, UNKNOWN_OPTION, NO_LEGENDARY when the points
  are short, target and range refusals); events: the points `ResourceSet`, `MonsterActionUsed`
  (legendary), then the attack or effect events.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import MonsterActionCommand, RefusalCode
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.command_checks import Actor, CommandRefused, refusal_from
from aidm.rules.conditions import can_take_actions
from aidm.rules.dice import Rng
from aidm.rules.encounter import EncounterRefused
from aidm.rules.monster_actions import monster_catalog_of, plan_monster_option, run_monster_option
from aidm.rules.monster_keys import LEGENDARY_KEY
from aidm.rules.resources import resource_left, spend_resource
from aidm.rules.turns import EconomyRefused
from aidm.rules.zones import ZoneError


def _turn_owner(enc: Encounter) -> str | None:
    if 0 <= enc.active_index < len(enc.initiative):
        return enc.initiative[enc.active_index].creature_id
    return None


def _may_act(state: GameState, enc: Encounter, cid: str) -> bool:
    combatant, creature = enc.combatants.get(cid), state.creatures.get(cid)
    if combatant is None or creature is None or combatant.withdrawn is not None:
        return False
    return not creature.dead and creature.hp > 0 and can_take_actions(creature)


def legendary_ready(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    owner = _turn_owner(enc)
    return [
        cid
        for cid in enc.combatants
        if cid != owner
        and _may_act(state, enc, cid)
        and resource_left(state.creatures[cid], LEGENDARY_KEY) > 0
    ]


def _legendary_actor(state: GameState, monster_id: str) -> Actor:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        raise CommandRefused(RefusalCode.NOT_IN_COMBAT, "There is no fight going on.")
    combatant, creature = enc.combatants.get(monster_id), state.creatures.get(monster_id)
    if combatant is None or creature is None:
        raise CommandRefused(RefusalCode.NOT_IN_COMBAT, "You are not in this fight.")
    if _turn_owner(enc) == monster_id:
        raise CommandRefused(
            RefusalCode.NOT_YOUR_TURN, "Legendary actions come at the end of another's turn."
        )
    if not _may_act(state, enc, monster_id):
        raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot act right now.")
    return Actor(enc=enc, combatant=combatant, creature=creature)


def _legendary(
    state: GameState, cmd: MonsterActionCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = _legendary_actor(state, cmd.actor_id)
    catalog = monster_catalog_of(actor.creature, regs)
    option = catalog.legendary_option(cmd.action)
    if option is None:
        raise CommandRefused(RefusalCode.UNKNOWN_OPTION, "You have no such legendary action.")
    if resource_left(actor.creature, LEGENDARY_KEY) < option.cost:
        raise CommandRefused(RefusalCode.NO_LEGENDARY, "Not enough legendary actions left.")
    plan = plan_monster_option(state, actor, catalog, option, cmd, regs)
    paid = spend_resource(actor.creature, LEGENDARY_KEY, option.cost)
    return run_monster_option(rng, state, cmd.actor_id, option, plan, regs, paid, legendary=True)


def legendary_action(
    state: GameState,
    monster_id: str,
    action: str,
    target_ids: Sequence[str],
    target_zone: str | None,
    regs: CombatRegistries,
    rng: Rng,
) -> list[AnyEvent]:
    cmd = MonsterActionCommand(
        actor_id=monster_id, action=action, target_ids=tuple(target_ids), target_zone=target_zone
    )
    try:
        return _legendary(state, cmd, regs, rng)
    except (EconomyRefused, EncounterRefused, ZoneError) as error:
        raise refusal_from(error) from None
