"""Host: load a saved campaign or start a new one on the SAME table (SPEC 10, M6.5).

Both replace what the table owns about its campaign (`session.restore.restore`) and re-seat
every open connection: by token when the save knows the person (their hero comes back), else as
a new seat that keeps their token. Each connection gets a fresh `welcome` (the player id may
change), the roster and a snapshot. The current game is saved first. A save that was in a
fight resumes it at once when a seated hero is connected.

Public API: `load`, `new_campaign`.
"""

from aidm.models.protocol_server import ErrorCode, NoticeKind, Welcome
from aidm.models.protocol_views import TablePhase
from aidm.session import combat_flow
from aidm.session.persistence import (
    CampaignLoadError,
    LoadedCampaign,
    SeatRecord,
    TableMeta,
)
from aidm.session.restore import connected_seats, rebind_connections, restore
from aidm.session.table_core import Player, TableCore


def _busy(core: TableCore, host: Player) -> bool:
    if core.phase is TablePhase.GENERATING:
        core.error(host.id, ErrorCode.WRONG_PHASE, "Wait until the campaign is written.")
        return True
    return False


def _switch(core: TableCore, host: Player, loaded: LoadedCampaign) -> None:
    seats = connected_seats(core)
    restore(core, loaded)
    core.kicked = set()
    rebind_connections(core, seats, host.token)
    for conn_id in sorted(core.conn_player):
        player = core.player_for(conn_id)
        if player is not None:
            core.send_conn(
                conn_id, Welcome(player_id=player.id, token=player.token, is_host=player.is_host)
            )
    core.broadcast_roster()
    core.broadcast_snapshot()
    if core.resume_combat and any(p.connected and p.creature_id for p in core.players.values()):
        core.resume_combat = False
        core.schedule(lambda: combat_flow.advance(core))
    core.autosave(force=True)


async def load(core: TableCore, host: Player, campaign_id: str) -> None:
    store = core.config.store
    if store is None or _busy(core, host):
        core.error(host.id, ErrorCode.REFUSED, "Loading is not available right now.")
        return
    try:
        loaded = store.load(campaign_id)
    except CampaignLoadError as exc:
        core.error(host.id, ErrorCode.REFUSED, str(exc))
        return
    core.autosave()
    _switch(core, host, loaded)
    note = " (repaired from its log)" if loaded.recovered else ""
    core.notice(None, NoticeKind.HOST, f"The host loaded a saved campaign{note}.")
    if loaded.warning is not None:
        core.notice(host.id, NoticeKind.HOST, loaded.warning)


async def new_campaign(core: TableCore, host: Player) -> None:
    if _busy(core, host):
        return
    core.autosave()
    state = core.config.new_state()
    seats = [
        SeatRecord(id=p.id, name=p.name, token=p.token, is_host=p.is_host)
        for p in core.players.values()
    ]
    meta = TableMeta(seats=seats, next_id=core.next_counter, tts_enabled=core.tts_enabled)
    _switch(core, host, LoadedCampaign(state.campaign_id, state, state, [], meta))
    core.notice(None, NoticeKind.HOST, "The host started a new campaign.")
