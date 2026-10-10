"""The host role follows the table (M17.1, owner request: "the host is the one who connects first").

The first seat at a table is the host (`TableCore.new_player`). The role moves to the connected
seat that joined earliest (seat creation order) when the host is gone:

- LOBBY and GENERATING: at once, whenever the host has no live connection;
- every other phase (PLAY, DEFEATED, ENDED): at once when the host has not connected since this
  server process started (a loaded save: `left_at` is None and no connection), else only after the
  host has been away `HOST_AWAY_S` seconds (a `host_away` timer re-checks, on the table's clock).

Nothing moves while nobody else is connected; the next `hello` re-checks. A returning former host
is an ordinary player. Every move leaves exactly one host, logs `host_moved` to the session log,
broadcasts a HOST notice and the roster, re-sends `welcome` to the new host (so their page shows
the host controls), sends them the host stats and autosaves the seats (table.json).

Public API: `HOST_AWAY_S`, `check(core, reason)`.
"""

from aidm.models.protocol_server import NoticeKind, Welcome
from aidm.models.protocol_views import TablePhase
from aidm.session.stats import send_host_stats
from aidm.session.table_core import Player, TableCore

HOST_AWAY_S = 60.0
_AT_ONCE = (TablePhase.LOBBY, TablePhase.GENERATING)
_EPSILON = 0.01  # a timer firing a hair early on the loop clock still counts as due


def check(core: TableCore, reason: str) -> None:
    """Move the host role if the rules above say so (called on hello, close and the timer)."""
    host = next((p for p in core.players.values() if p.is_host), None)
    if host is not None and host.connected:
        return
    heir = next((p for p in core.players.values() if p.connected), None)
    if heir is None:
        return
    if host is None:
        _move(core, None, heir, "no_host")
        return
    if core.phase in _AT_ONCE:
        _move(core, host, heir, "host_left_lobby")
        return
    if host.left_at is None:
        _move(core, host, heir, "host_not_returned")
        return
    away = core.config.clock.time() - host.left_at
    if away + _EPSILON >= HOST_AWAY_S:
        _move(core, host, heir, "host_away")
    elif reason != "timer":
        core.start_timer("host_away", host.id, HOST_AWAY_S - away)


def _move(core: TableCore, old: Player | None, new: Player, reason: str) -> None:
    for player in core.players.values():
        player.is_host = player is new
    core.diag("host_moved", from_id=old.id if old else None, to_id=new.id, reason=reason)
    core.notice(None, NoticeKind.HOST, f"{new.name} is now the host.")
    core.send(new.id, Welcome(player_id=new.id, token=new.token, is_host=True))
    core.broadcast_roster()
    send_host_stats(core)
    core.autosave()
