"""Rebuild a `TableCore` from a loaded save (M6.3) or switch it to another campaign (M6.5).

`restore(core, loaded)` replaces everything the table owns about ONE campaign: state, the replay
base (`initial`), the log and its public feed (so seq catch-up and the story history work after a
restart), the seats (tokens kept, nobody connected), the id counter, the TTS flag and the save
folder (`save_id` = the folder the save was loaded from, so progress is written back there even when
the folder was renamed: QA-09), the screen's audio settings and the turn timer when the save has
them (M11.2, M15.1) and
clears who is typing. Open connections (`outboxes`, `conn_player`) are not touched;
`rebind_connections` seats them in the new table. A save that was in a fight resumes it when the
first seated hero connects (`resume_combat`). The retry markers come with the save
(`loaded.checkpoints`, M11.1) and a defeated save comes back DEFEATED (`phase_of`).

Public API: `restore`, `connected_seats`, `rebind_connections`.
"""

import random

from aidm.models.encounter import EncounterStatus
from aidm.session import combat_flow
from aidm.session.persistence import LoadedCampaign
from aidm.session.public_feed import PublicFeed
from aidm.session.table_core import Player, TableCore, phase_of


def restore(core: TableCore, loaded: LoadedCampaign) -> None:
    combat_flow.end_player_turn(core)
    if core.vote is not None and core.vote.timer is not None:
        core.vote.timer.cancel()
    core.state = loaded.state
    core.save_id = loaded.campaign_id
    core.initial = loaded.initial.model_copy(deep=True)
    core.log = list(loaded.log)
    core.public = PublicFeed.rebuild(core.initial, core.log)
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
    if loaded.meta.audio is not None:  # M11.2: the screen's audio comes back with the save
        core.audio = loaded.meta.audio
    if loaded.meta.turn_timer is not None:  # M15.1: the host's turn timer (0 = off)
        core.turn_seconds = float(loaded.meta.turn_timer) or None
    core.typing.clear()
    core.phase = phase_of(loaded.state)
    core.checkpoints = loaded.checkpoints.model_copy(deep=True)
    core.mark_due = False
    core.paused = False
    core.queue.clear()
    core.resolving = None
    core.vote = None
    core.pending = None
    core.segment = []
    core.issued_rolls = {}
    core.rolled_for = {}
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
