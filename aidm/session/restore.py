"""Rebuild a `TableCore` from a loaded save (M6.3) or switch it to another campaign (M6.5).

`restore(core, loaded)` replaces everything the table owns about ONE campaign: state, the replay
base (`initial`), the log (so seq catch-up works after a restart), the seats (tokens kept, nobody
connected), the id counter and the TTS flag. Open connections (`outboxes`, `conn_player`) are not
touched; `rebind_connections` seats them in the new table. A save that was in a fight resumes it
when the first seated hero connects (`resume_combat`).

Public API: `restore`, `connected_seats`, `rebind_connections`.
"""

import random

from aidm.models.encounter import EncounterStatus
from aidm.models.protocol_views import TablePhase
from aidm.session import combat_flow
from aidm.session.persistence import LoadedCampaign
from aidm.session.table_core import Player, TableCore


def restore(core: TableCore, loaded: LoadedCampaign) -> None:
    combat_flow.end_player_turn(core)
    if core.vote is not None and core.vote.timer is not None:
        core.vote.timer.cancel()
    core.state = loaded.state
    core.initial = loaded.initial.model_copy(deep=True)
    core.log = list(loaded.log)
    core.unsaved = []
    core.rng = random.Random(f"{loaded.state.seed}:{loaded.state.event_count}")
    core.creation_rng = random.Random(f"{loaded.state.seed}:creation:{loaded.state.event_count}")
    core.players = {
        s.id: Player(
            id=s.id, name=s.name, token=s.token, is_host=s.is_host, creature_id=s.creature_id
        )
        for s in loaded.meta.seats
    }
    core.next_counter = max(loaded.meta.next_id, core.next_counter)
    core.tts_enabled = loaded.meta.tts_enabled
    core.phase = TablePhase.PLAY if loaded.state.world.current_node else TablePhase.LOBBY
    core.paused = False
    core.queue.clear()
    core.resolving = None
    core.vote = None
    core.pending = None
    core.segment = []
    core.issued_rolls = {}
    enc = loaded.state.encounter
    core.in_combat = enc is not None and enc.status is EncounterStatus.ACTIVE
    core.resume_combat = core.in_combat


type Seats = dict[str, tuple[str, str]]


def connected_seats(core: TableCore) -> Seats:
    """Open connections as `{conn_id: (name, token)}`, to re-seat them after a switch."""
    seats: Seats = {}
    for conn_id in core.conn_player:
        player = core.player_for(conn_id)
        if player is not None:
            seats[conn_id] = (player.name, player.token)
    return seats


def rebind_connections(core: TableCore, seats: Seats, host_token: str | None) -> None:
    """Seat every open connection in the restored table: by token when the save knows the
    person, otherwise as a new seat that keeps their token. `host_token` marks the host seat."""
    by_token = {p.token: p for p in core.players.values()}
    core.conn_player = {}
    for conn_id, (name, token) in seats.items():
        player = by_token.get(token)
        if player is None:
            player = core.new_player(name)
            player.token = token
            by_token[token] = player
        player.conns.add(conn_id)
        core.conn_player[conn_id] = player.id
    for player in core.players.values():
        player.is_host = host_token is not None and player.token == host_token
