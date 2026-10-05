"""Injectable timers for the table actor (ready votes, turn timers).

The actor never sleeps: it asks a `Clock` to call back later, and the callback only enqueues a
message into the actor's inbox. `LoopClock` uses the running asyncio loop; `ManualClock` is a
deterministic clock for tests (`advance(seconds)` fires every due callback in time order).

Public API: `TimerHandle` (protocol with `cancel()`), `Clock` (protocol with
`call_later(delay, callback) -> TimerHandle`), `LoopClock`, `ManualClock`.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class TimerHandle(Protocol):
    def cancel(self) -> None: ...


class Clock(Protocol):
    def call_later(self, delay: float, callback: Callable[[], None]) -> TimerHandle: ...


class LoopClock:
    def call_later(self, delay: float, callback: Callable[[], None]) -> TimerHandle:
        return asyncio.get_running_loop().call_later(delay, callback)


@dataclass
class _ManualTimer:
    due: float
    order: int
    callback: Callable[[], None]
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class ManualClock:
    now: float = 0.0
    timers: list[_ManualTimer] = field(default_factory=list[_ManualTimer])

    def call_later(self, delay: float, callback: Callable[[], None]) -> TimerHandle:
        timer = _ManualTimer(self.now + max(0.0, delay), len(self.timers), callback)
        self.timers.append(timer)
        return timer

    def pending(self) -> int:
        return sum(1 for t in self.timers if not t.cancelled)

    def advance(self, seconds: float) -> None:
        self.now += seconds
        due = sorted(
            (t for t in self.timers if not t.cancelled and t.due <= self.now),
            key=lambda t: (t.due, t.order),
        )
        for timer in due:
            timer.cancelled = True
            timer.callback()
        self.timers = [t for t in self.timers if not t.cancelled]
