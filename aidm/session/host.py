"""Host controls routed by the table actor (SPEC 10). Only the host seat may use them.

Everyone else gets `error not_host`. Pause stops the exploration queue, combat commands and turn
timeouts (a timer that fires while paused restarts); resume continues. Start generates the
campaign, force vote passes the open vote, the turn timer (M15.1, `turn_clock.set_timer`) applies
at once. Kick, TTS toggle (immediate) and difficulty, save,
load, new and end (jobs: they touch the game state or the files) live in `host_controls` and
`host_switch`. Token totals reach the host as `host_stats` after every job (`session.stats`).

Public API: `host_message`.
"""

from functools import partial

from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_client import (
    HostDifficulty,
    HostEnd,
    HostForceVote,
    HostKick,
    HostLoad,
    HostNew,
    HostPause,
    HostResume,
    HostSave,
    HostStart,
    HostTtsToggle,
    HostTurnTimer,
)
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.session import explore, host_controls, host_switch, lobby, turn_clock, votes
from aidm.session.table_core import Player, TableCore


def _pause(core: TableCore, paused: bool) -> None:
    core.paused = paused
    core.notice(
        None, NoticeKind.HOST, "The host paused the game." if paused else "The game resumes."
    )
    core.broadcast_snapshot()
    if not paused:
        explore.kick_resolver(core)


def host_message(core: TableCore, player: Player, msg: AnyClientMsg) -> None:
    if not player.is_host:
        core.error(player.id, ErrorCode.NOT_HOST, "Only the host can do that.")
        return
    match msg:
        case HostStart(theme=theme):
            core.schedule(lambda: lobby.start_campaign(core, player, theme))
        case HostForceVote():
            votes.force_vote(core, player)
        case HostPause():
            _pause(core, True)
        case HostResume():
            _pause(core, False)
        case HostKick(player_id=target):
            host_controls.kick(core, player, target)
        case HostTtsToggle(enabled=enabled):
            host_controls.set_tts(core, player, enabled)
        case HostTurnTimer(seconds=seconds):
            turn_clock.set_timer(core, seconds)
        case HostDifficulty():
            core.schedule(partial(host_controls.set_difficulty, core, player, msg))
        case HostSave():
            core.schedule(partial(host_controls.save, core, player))
        case HostEnd():
            core.schedule(partial(host_controls.end, core, player))
        case HostLoad(campaign_id=campaign_id):
            core.schedule(partial(host_switch.load, core, player, campaign_id))
        case HostNew():
            core.schedule(partial(host_switch.new_campaign, core, player))
        case _:
            core.error(player.id, ErrorCode.INVALID, "That is not a host control.")
