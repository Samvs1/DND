"""Host-only table controls: kick, difficulty, TTS toggle, save, end (SPEC 10, M6.5).

Decisions (DECISIONS M6.5): a kicked player's seat is removed (their token, their connections and,
for a new seat, their name are refused on hello for the server session: QA-07),
their waiting action and vote are dropped and their hero stays in the tale played by the safe
default turn ("NPC-controlled"); difficulty is the `DifficultySet` event (replayable); the TTS flag
is table-level state saved in `table.json`; save forces a snapshot; end runs the epilogue when the
campaign is complete, otherwise just closes the table (phase `ended`).

Public API: `kick`, `set_difficulty`, `set_tts`, `save`, `end`.
"""

from collections import deque

from aidm.models.campaign_events import DifficultySet
from aidm.models.protocol_client import HostDifficulty
from aidm.models.protocol_server import ErrorCode, Notice, NoticeKind
from aidm.models.protocol_views import TablePhase
from aidm.session import combat_flow, lobby, votes
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import maybe_epilogue

KICKED = "The host removed you from the table."
ENDED_TEXT = "The host ended the session. Thanks for playing."


def kick(core: TableCore, host: Player, target_id: str) -> None:
    target = core.players.get(target_id)
    if target is None:
        core.error(host.id, ErrorCode.UNKNOWN_TARGET, "That player is not at the table.")
        return
    if target.id == host.id:
        core.error(host.id, ErrorCode.REFUSED, "You cannot remove yourself.")
        return
    for conn_id in sorted(target.conns):
        core.send_conn(conn_id, Notice(kind=NoticeKind.HOST, text=KICKED))
        core.conn_player.pop(conn_id, None)
        core.kicked_conns.add(conn_id)
    target.conns.clear()
    core.kicked.add(target.token)
    core.kicked_names.add(target.name.strip().casefold())
    del core.players[target.id]
    core.queue = deque(e for e in core.queue if e.player_id != target.id)
    if core.pending is not None and core.pending.player_id == target.id:
        core.pending = None
    votes.drop_voter(core, target.id)
    lobby.release_turn(core, target.creature_id)
    core.broadcast_queue()
    core.broadcast_roster()
    core.notice(host.id, NoticeKind.HOST, f"{target.name} was removed from the table.")
    core.autosave()


async def set_difficulty(core: TableCore, host: Player, msg: HostDifficulty) -> None:
    core.apply(DifficultySet(monster_hp=msg.monster_hp, monster_damage=msg.monster_damage))
    text = f"Monster difficulty: hit points x{msg.monster_hp:g}, damage x{msg.monster_damage:g}."
    core.notice(None, NoticeKind.HOST, text)


def set_tts(core: TableCore, host: Player, enabled: bool) -> None:
    core.tts_enabled = enabled
    core.notice(None, NoticeKind.HOST, "Narration voice is on." if enabled else "Voice is off.")
    core.broadcast_snapshot()
    core.autosave()


async def save(core: TableCore, host: Player) -> None:
    if core.config.store is None:
        core.notice(host.id, NoticeKind.HOST, "Saving is turned off on this server.")
    elif core.autosave(force=True):
        core.notice(host.id, NoticeKind.HOST, "Game saved.")


async def end(core: TableCore, host: Player) -> None:
    if core.phase in (TablePhase.ENDED, TablePhase.GENERATING):
        core.error(host.id, ErrorCode.WRONG_PHASE, "There is nothing to end right now.")
        return
    core.queue.clear()
    core.broadcast_queue()
    if core.vote is not None:
        votes.close_vote(core, passed=False, reason="the session is ending")
    combat_flow.end_player_turn(core)
    await maybe_epilogue(core)
    core.phase = TablePhase.ENDED
    core.notice(None, NoticeKind.HOST, ENDED_TEXT)
    core.autosave(force=True)
