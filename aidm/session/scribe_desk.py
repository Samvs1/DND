"""The Scribe's desk in the table actor (M13.1): `scribe_revive` -> `rules.scribe` -> THE reducer.

The message is a job (so the table's pause and the defeat lock refuse it before it runs, with
their existing codes); inside the job `rules.scribe.revive_events` checks again with the live
state. A refusal is an `ErrorMsg` with `ErrorCode.REFUSED` (unknown target: `UNKNOWN_TARGET`)
and `refusal` = the `ScribeRefusal` code, so the UI can pick the Scribe's matching line; nothing
is spent. Success applies the events; the public feed shows "The Scribe rewrites <name> into the
story." and the next snapshot carries the new `scribe` state.

Public API: `revive(core, player, msg)`, `REFUSAL_TEXT`.
"""

from aidm.data.scribe_defs import scribe_table
from aidm.models.protocol_client import ScribeRevive
from aidm.models.protocol_server import ErrorCode
from aidm.rules.scribe import ScribeRefusal, ScribeRefused, revive_events
from aidm.session.table_core import Player, TableCore

REFUSAL_TEXT: dict[ScribeRefusal, str] = {
    ScribeRefusal.DEFEATED: "The story has ended for now; the Scribe's quill rests.",
    ScribeRefusal.PAUSED: "The game is paused.",
    ScribeRefusal.IN_COMBAT: "The Scribe will not write while blades are drawn.",
    ScribeRefusal.NONE_FALLEN: "Nobody has fallen; there is nothing to rewrite.",
    ScribeRefusal.PAYER_DOWN: "Your hero must be standing to pay the Scribe.",
    ScribeRefusal.UNKNOWN_TARGET: "The Scribe finds no such hero in the story.",
    ScribeRefusal.NOT_FALLEN: "That hero is down, but not yet the Scribe's to rewrite.",
    ScribeRefusal.NO_FUNDS: "You cannot afford the Scribe's price.",
}


async def revive(core: TableCore, player: Player, msg: ScribeRevive) -> None:
    payer_id = player.creature_id
    if payer_id is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a hero for that.")
        return
    try:
        events = revive_events(
            core.state, payer_id, msg.target_id, scribe_table(), paused=core.paused
        )
    except ScribeRefused as refused:
        unknown = refused.reason is ScribeRefusal.UNKNOWN_TARGET
        code = ErrorCode.UNKNOWN_TARGET if unknown else ErrorCode.REFUSED
        core.error(player.id, code, REFUSAL_TEXT[refused.reason], refusal=refused.reason.value)
        return
    core.apply_all(events)
