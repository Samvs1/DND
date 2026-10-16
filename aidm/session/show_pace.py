"""The screen paces the table (M26.3): `presented` reports and the waits that use them.

`presented(core, conn_id, seq)` records a screen's report (`TableCore.shows`, `show_board`); a
report from any connection that is not a screen is ignored without an error.
`last_shown_seq(core)` is the highest seq the screens were sent as an event line or a dice roll
(private events are never sent, so waiting for the raw last event seq would always hit the cap).
`wait_presented(core, seq, floor_s, cap_s)` waits on the table's clock (`ShowBoard.wait`) and
writes one `show_wait_capped` diagnostics line when a screen did not keep up.

Public API: `presented`, `last_shown_seq`, `wait_presented`.
"""

from aidm.session.show_board import WaitEnd
from aidm.session.table_core import TableCore


def presented(core: TableCore, conn_id: str, seq: int) -> None:
    if conn_id in core.spectators:
        core.shows.report(conn_id, seq)


def last_shown_seq(core: TableCore) -> int:
    events, rolls = core.public.events, core.public.rolls
    return max(events[-1].seq if events else -1, rolls[-1].seq if rolls else -1)


async def wait_presented(core: TableCore, seq: int, floor_s: float, cap_s: float) -> WaitEnd:
    clock = core.config.clock
    started = clock.time()
    end = await core.shows.wait(clock, seq, floor_s, cap_s)
    if end is WaitEnd.CAP:
        waited = round(clock.time() - started, 2)
        core.diag("show_wait_capped", seq=seq, waited=waited, screens=len(core.shows.seen))
    return end
