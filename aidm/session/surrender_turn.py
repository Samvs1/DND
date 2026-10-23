"""A typed demand to surrender on a hero's turn (M29.9a T12): ONE engine check, then the fight
goes on or ends (a fight whose remaining foes all surrendered is a victory).

`surrender_turn(core, player, entry, demand)`: on the hero's own open turn with the action left,
`rules.surrender.demand_surrender` (the action, the check, the "surrendered" condition on the
foes that yield), told with the round; a spent action is refused with the plain reason
(`ACTION_SPENT`). Called by `aidm.session.explore` for a `dm.surrender_intent.SurrenderIntent`.

Public API: `ACTION_SPENT`, `surrender_turn`.
"""

from aidm.dm.surrender_intent import SurrenderIntent
from aidm.models.protocol_server import ErrorCode
from aidm.models.protocol_views import QueueEntry
from aidm.rules.surrender import demand_surrender
from aidm.rules.turns import EconomyRefused
from aidm.session import combat_flow
from aidm.session.declared import declare
from aidm.session.table_core import Player, TableCore

ACTION_SPENT = (
    "You have already used your action this turn. Move, use a bonus action or end your turn."
)


async def surrender_turn(
    core: TableCore, player: Player, entry: QueueEntry, demand: SurrenderIntent
) -> None:
    enc = core.state.encounter
    if enc is None or enc.active_id() != demand.actor_id or core.turn_key is None:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
        return
    try:
        events = demand_surrender(
            core.rng, core.state, demand.actor_id, demand.skill, core.regs.tiers
        )
    except EconomyRefused:
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    await combat_flow.tell_segment(core)
    declare(core, entry)
    core.apply_all(events)
    await combat_flow.after_player_step(core, demand.actor_id)
