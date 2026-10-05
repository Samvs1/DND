"""Host controls routed by the table actor (SPEC 10). Only the host seat may use them.

M6.2 implements start (campaign generation), force vote, pause and resume; pause stops the
exploration queue, combat commands and turn timeouts (a timer that fires while paused restarts).
Kick, difficulty, TTS toggle, save, load, new and end are routed here and answered with a host
notice until M6.5 implements them (`HOST_PENDING`).

Public API: `HOST_PENDING`, `host_message`.
"""

from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_client import HostForceVote, HostPause, HostResume, HostStart
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.session import explore, lobby, votes
from aidm.session.table_core import Player, TableCore

HOST_PENDING = "That host control is not available in this build yet."


def host_message(core: TableCore, player: Player, msg: AnyClientMsg) -> None:
    if not player.is_host:
        core.error(player.id, ErrorCode.NOT_HOST, "Only the host can do that.")
        return
    if isinstance(msg, HostStart):
        theme = msg.theme
        core.schedule(lambda: lobby.start_campaign(core, player, theme))
    elif isinstance(msg, HostForceVote):
        votes.force_vote(core, player)
    elif isinstance(msg, HostPause):
        core.paused = True
        core.notice(None, NoticeKind.HOST, "The host paused the game.")
        core.broadcast_snapshot()
    elif isinstance(msg, HostResume):
        core.paused = False
        core.notice(None, NoticeKind.HOST, "The game resumes.")
        core.broadcast_snapshot()
        explore.kick_resolver(core)
    else:
        core.notice(player.id, NoticeKind.HOST, HOST_PENDING)
