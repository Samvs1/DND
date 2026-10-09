"""The combat turn clock (M15.1, owner playtest: turns must never be taken away unexpectedly).

- `limit_for(core, owner)`: the host's turn timer (`core.turn_seconds`: off, 90 s, 3 min or
  5 min; default 3 min) runs only when another connected player with a hero waits: a solo
  table, or the timer Off, never times a turn out.
- `start(core, key, seconds)`: the end timer (`turn` -> `combat_flow.turn_timeout`, the careful
  auto-turn), a warning `WARN_SECONDS` before the end (`turn_warn` -> `warn`: a notice to the
  acting player) and the deadline the phone and the screen count down from
  (`TableCore.turn_left`, sent as `floor.seconds_left`).
- Reconnect grace: an owner whose last connection drops (their turn, or their turn comes up
  while they are away) keeps the turn for `GRACE_SECONDS` before the careful auto-turn
  (`grace`, `grace_left`); coming back (`resume`) restarts their clock. A kicked hero plays at
  once (`lobby.release_turn(grace=False)`).
- `set_timer`: the host setting (`host_turn_timer`), persisted in table.json (`turn_timer`).

Public API: `TURN_CHOICES`, `WARN_SECONDS`, `GRACE_SECONDS`, `WARN_TEXT`, `limit_for`, `start`,
`stop`, `grace`, `grace_left`, `resume`, `warn`, `set_timer`.
"""

from aidm.models.protocol_server import NoticeKind
from aidm.session.table_core import Player, TableCore

TURN_CHOICES = (0, 90, 180, 300)
WARN_SECONDS = 30.0
GRACE_SECONDS = 30.0
WARN_TEXT = "30 seconds left: act or end your turn."
_LABELS = {0: "off", 90: "90 seconds", 180: "3 minutes", 300: "5 minutes"}


def limit_for(core: TableCore, owner: Player) -> float | None:
    if core.turn_seconds is None:
        return None
    waiting = [
        p for p in core.players.values() if p.id != owner.id and p.connected and p.creature_id
    ]
    return core.turn_seconds if waiting else None


def start(core: TableCore, key: str, seconds: float | None, *, shown: bool = True) -> None:
    core.turn_clock.stop()
    if seconds is None:
        return
    clock = core.turn_clock
    clock.end = core.start_timer("turn", key, seconds)
    if not shown:
        return
    clock.deadline = core.config.clock.time() + seconds
    if seconds > WARN_SECONDS:
        clock.warn = core.start_timer("turn_warn", key, seconds - WARN_SECONDS)


def stop(core: TableCore) -> None:
    core.turn_clock.stop()


def grace_left(core: TableCore, owner: Player) -> float:
    """Seconds an away owner still has to come back (0 when connected or long gone)."""
    if owner.connected or owner.left_at is None:
        return 0.0
    return max(0.0, GRACE_SECONDS - (core.config.clock.time() - owner.left_at))


def grace(core: TableCore, key: str, owner: Player) -> None:
    """The owner of the open turn went away: the auto-turn waits for the rest of the grace."""
    seconds = grace_left(core, owner) or GRACE_SECONDS
    core.diag("grace_started", player_id=owner.id, creature_id=owner.creature_id, seconds=seconds)
    start(core, key, seconds, shown=False)


def resume(core: TableCore, player: Player) -> None:
    """A returning owner whose turn is open gets their clock back (fresh)."""
    key = core.turn_key
    enc = core.state.encounter
    if key is not None and enc is not None and enc.active_id() == player.creature_id:
        core.diag(
            "grace_ended", player_id=player.id, creature_id=player.creature_id, reason="returned"
        )
        start(core, key, limit_for(core, player))


def _owner_of_turn(core: TableCore, key: str) -> Player | None:
    enc = core.state.encounter
    if core.turn_key != key or enc is None:
        return None
    return core.owner_of(enc.active_id())


def warn(core: TableCore, key: str) -> None:
    owner = _owner_of_turn(core, key)
    if owner is not None and not core.paused:
        core.diag("turn_warning", player_id=owner.id, creature_id=owner.creature_id)
        core.notice(owner.id, NoticeKind.INFO, WARN_TEXT)


def set_timer(core: TableCore, seconds: int) -> None:
    """The host's turn timer; the open turn's clock follows at once (Off stops it)."""
    core.turn_seconds = float(seconds) or None
    key = core.turn_key
    owner = _owner_of_turn(core, key) if key is not None else None
    if key is not None and owner is not None and owner.connected:
        start(core, key, limit_for(core, owner))
    core.notice(None, NoticeKind.HOST, f"Turn timer: {_LABELS.get(seconds, f'{seconds} s')}.")
    core.broadcast_snapshot()
    core.autosave()
