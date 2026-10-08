"""Table bookkeeping for the screen + controller split (M11.2): who is typing, rate limits.

Neither is game state: nothing here is an event or persisted. `TypingBoard` remembers which
players are composing, with a generation per start so a stale expiry timer never clears a fresher
start; `RateLimit` is a sliding-window counter per key (time comes from the table clock).

Public API: `RateLimit`, `TypingBoard`.
"""

from collections import deque
from dataclasses import dataclass, field

from aidm.session.table_clock import TimerHandle


@dataclass
class RateLimit:
    """At most `limit` hits per `window` seconds per key."""

    limit: int
    window: float
    hits: dict[str, deque[float]] = field(default_factory=dict[str, deque[float]])

    def allow(self, key: str, now: float) -> bool:
        times = self.hits.setdefault(key, deque())
        while times and now - times[0] >= self.window:
            times.popleft()
        if len(times) >= self.limit:
            return False
        times.append(now)
        return True


@dataclass
class TypingBoard:
    gens: dict[str, int] = field(default_factory=dict[str, int])
    timers: dict[str, TimerHandle] = field(default_factory=dict[str, TimerHandle])
    counter: int = 0

    def start(self, player_id: str) -> tuple[int, bool]:
        """Start (or refresh) typing; returns the new generation and whether it is NEW."""
        fresh = player_id not in self.gens
        self.counter += 1
        self.gens[player_id] = self.counter
        old = self.timers.pop(player_id, None)
        if old is not None:
            old.cancel()
        return self.counter, fresh

    def keep_timer(self, player_id: str, timer: TimerHandle) -> None:
        self.timers[player_id] = timer

    def stop(self, player_id: str) -> bool:
        """Stop typing; True when the player was typing."""
        timer = self.timers.pop(player_id, None)
        if timer is not None:
            timer.cancel()
        return self.gens.pop(player_id, None) is not None

    def expire(self, player_id: str, gen: int) -> bool:
        """An expiry timer fired: stop only when it belongs to the current start."""
        if self.gens.get(player_id) != gen:
            return False
        self.timers.pop(player_id, None)
        return self.gens.pop(player_id, None) is not None

    def clear(self) -> None:
        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()
        self.gens.clear()

    def ids(self) -> list[str]:
        return list(self.gens)
