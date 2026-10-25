"""A typed demand to surrender on a hero's turn (M29.9a T12): ONE engine check, then the fight
goes on or ends (a fight whose remaining foes all surrendered is a victory).

`surrender_turn(core, player, entry, demand)`: on the hero's own open turn with the action left,
`rules.surrender.demand_surrender` (the action, the check, the "surrendered" condition on the
foes that yield), told with the round; a spent action is refused with the plain reason
(`ACTION_SPENT`). M31.1a V5: against foes that never yield (undead, constructs, oozes,
plants) there is no roll, only the rules' plain line, and the action is kept; when only some
never yield, the roll covers the others and the player is told who will not. Called by
`aidm.session.fight_text` for a `dm.surrender_intent.SurrenderIntent`.

Public API: `ACTION_SPENT`, `surrender_turn`.
"""

from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.rules.acts_fight import SurrenderIntent
from aidm.rules.surrender import NoneYield, demand_surrender, never_yield_line
from aidm.rules.turns import EconomyRefused
from aidm.session import combat_flow
from aidm.session.declared import declare
from aidm.session.table_core import Player, TableCore

ACTION_SPENT = (
    "You have already used your action this turn. Move, use a bonus action or end your turn."
)


async def surrender_turn(
    core: TableCore, player: Player, entry: QueueEntry, demand: SurrenderIntent, *, say: bool = True
) -> None:
    enc = core.state.encounter
    if enc is None or enc.active_id() != demand.actor_id or core.turn_key is None:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
        return
    stubborn = never_yield_line(core.state, demand.actor_id)
    try:
        events = demand_surrender(
            core.rng, core.state, demand.actor_id, demand.skill, core.regs.tiers
        )
    except EconomyRefused:
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    except NoneYield as none:  # M31.1a V5: no roll, the action is kept
        core.notice(player.id, NoticeKind.REFUSED, none.line)
        return
    await combat_flow.tell_segment(core)
    if say:  # M32.1a: a later act of a compound line was declared with the whole line
        declare(core, entry)
    core.apply_all(events)
    if stubborn is not None:  # the roll covered only the foes that can yield
        core.notice(player.id, NoticeKind.INFO, stubborn)
    await combat_flow.after_player_step(core, demand.actor_id)
