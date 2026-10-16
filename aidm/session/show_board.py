"""What the shared screens have shown (M26.3, docs/next/GOAL_DICE.md "Timing (the hard rule)").

A screen that animates rolls reports `presented {seq}` when its show queue has shown everything
up to `seq`. `ShowBoard` keeps, per screen connection that has EVER reported ("show-capable"),
the last seq it reported. `wait(clock, seq, floor_s, cap_s)` returns after at least `floor_s`;
while a capable screen has not reported `seq` yet it waits for it too, but never longer than
`cap_s` in total (the cap always ends the wait, so a stuck screen cannot hang the table). A
capable screen that leaves stops counting and wakes the waiter. No capable screen = just the
floor, and a zero floor with nobody behind returns without awaiting at all (today's behaviour).
Timers come from the injected `Clock` (the actor never sleeps); waiters are plain futures woken
by `report`, `drop` and the timers, never polled.

Public API: `ShowBoard` (`seen`, `waiting_for`, `report`, `drop`, `behind`, `wait`),
`WaitEnd` (why a wait ended).
"""

import asyncio
from enum import StrEnum

from aidm.session.table_clock import Clock, TimerHandle


class WaitEnd(StrEnum):
    NONE = "none"  # nothing to wait for
    FLOOR = "floor"  # the floor passed and no capable screen is connected
    PRESENTED = "presented"  # every capable screen still connected reported the seq
    CAP = "cap"  # a capable screen was still behind when the cap ran out


class ShowBoard:
    def __init__(self) -> None:
        self.seen: dict[str, int] = {}  # capable screen connection -> last presented seq
        self.waiting_for: int | None = None  # the seq the running wait is holding for
        self._waiters: set[asyncio.Future[None]] = set()

    def report(self, conn_id: str, seq: int) -> None:
        """The latest report counts (a retry rewinds the log, so a lower seq is honest)."""
        self.seen[conn_id] = seq
        self._wake()

    def drop(self, conn_id: str) -> None:
        if self.seen.pop(conn_id, None) is not None:
            self._wake()

    def behind(self, seq: int) -> bool:
        return any(shown < seq for shown in self.seen.values())

    def _wake(self) -> None:
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)

    async def _sleep(self) -> None:
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.add(waiter)
        try:
            await waiter
        finally:
            self._waiters.discard(waiter)

    async def wait(self, clock: Clock, seq: int, floor_s: float, cap_s: float) -> WaitEnd:
        if floor_s <= 0 and not self.behind(seq):
            return WaitEnd.NONE
        passed = {"floor": floor_s <= 0, "cap": False}

        def fire(key: str) -> None:
            passed[key] = True
            self._wake()

        timers: list[TimerHandle] = []
        if not passed["floor"]:
            timers.append(clock.call_later(floor_s, lambda: fire("floor")))
        timers.append(clock.call_later(max(floor_s, cap_s), lambda: fire("cap")))
        self.waiting_for = seq
        try:
            while not (passed["floor"] and (passed["cap"] or not self.behind(seq))):
                await self._sleep()
        finally:
            self.waiting_for = None
            for timer in timers:
                timer.cancel()
        if self.behind(seq):
            return WaitEnd.CAP
        return WaitEnd.PRESENTED if self.seen else WaitEnd.FLOOR
