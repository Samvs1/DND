"""A typed search where something is hidden (M31.1a V9): ONE discovery check, then the telling.

`search_turn(core, entry, intent, prior=())`: `rules.searching.search_events` (the check
at the hidden things' own DC and what it finds) applied through THE reducer; with nothing more
in the line it is told at once (`telling.conclude`, the player's words with it); the rest of the
line ("..., pick it up, and read it") goes to the storyteller with the search's events before it
(`held.adjudicated(prior=...)`), so the telling agrees with the roll. `prior` carries a light lit
first ("I light a candle and search the shelves": the light never replaces the search). When
nothing is hidden any more, the line is the storyteller's as before.

Public API: `search_turn`.
"""

from collections.abc import Sequence

from aidm.dm.search_intent import SearchIntent
from aidm.models.events import AnyEvent
from aidm.models.protocol_views import QueueEntry
from aidm.rules.lore import place_lore_events
from aidm.rules.searching import search_events
from aidm.session.held import adjudicated
from aidm.session.table_core import TableCore
from aidm.session.telling import conclude


async def search_turn(
    core: TableCore, entry: QueueEntry, intent: SearchIntent, prior: Sequence[AnyEvent] = ()
) -> None:
    lore = place_lore_events(core.state, intent.actor_id)  # M31.1b V13c: the place teaches
    prior = [*prior, *core.apply_all(lore)] if lore else prior
    try:
        events = search_events(core.rng, core.state, intent.actor_id, intent.skill)
    except ValueError:  # nothing is hidden here any more: the storyteller's search
        await adjudicated(core, entry, prior=prior)
        return
    told = [*prior, *core.apply_all(events)]
    if intent.rest is None:
        await conclude(core, None, told, actor_id=intent.actor_id, player_text=entry.text)
        return
    await adjudicated(core, entry.model_copy(update={"text": intent.rest}), prior=told)
