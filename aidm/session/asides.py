"""The scene-setting words of a compound typed line, told with the act they lead into (M33.1,
ultrareview 5: "I step forward and give the ring to Bram" ran the gift and nobody told the step).

`session.intent_turn` plays a compound line part by part. A part no row reads that only sets
the scene (`dm.compound_lines.is_lead_in`: "step forward", "kneel", "bow to the captain") is no
act of its own: it is never ruled on, and its words go to the storyteller with the next telling
of the same turn. `told_with(aside)` holds them while the turn's acts run; the first narration
of that turn (`telling.conclude`) takes them (`take`) before the player's own words, so the
story tells the step and the gift together. The caller tells what no
narration took (an act told by engine lines only) with the turn's other words. Leaving
`told_with` spends the aside, so a job the turn scheduled never tells the words again.

Public API: `Aside`, `told_with(aside)`, `take() -> str | None`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class Aside:
    text: str = ""
    told: bool = False


_CURRENT: ContextVar[Aside | None] = ContextVar("aside", default=None)


@contextmanager
def told_with(aside: Aside) -> Iterator[Aside]:
    token = _CURRENT.set(aside)
    try:
        yield aside
    finally:
        aside.told = True  # nothing later (a job the turn scheduled) takes these words again
        _CURRENT.reset(token)


def take() -> str | None:
    """The waiting scene-setting words, once (None: none wait, or they were told)."""
    aside = _CURRENT.get()
    if aside is None or aside.told or not aside.text:
        return None
    aside.told = True
    return aside.text
