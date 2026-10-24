"""A question to a person who has something to teach (M31.1b V13).

`lore_turn(core, entry, intent)`: `rules.lore_talk.ask_events` (a secret the person may reveal
now, a lesson for an open learn step) applied through THE reducer, then the whole line goes to
the storyteller with those events before it (`held.adjudicated(prior=...)`), so the person
answers in their own voice and the telling agrees with what the engine recorded. When nothing
is left to tell by the time the turn runs, the line is the storyteller's as before.

Public API: `lore_turn`.
"""

from aidm.dm.lore_intent import AskIntent
from aidm.models.protocol_views import QueueEntry
from aidm.rules.lore_talk import ask_events
from aidm.rules.secrets import fact_words
from aidm.session.held import adjudicated
from aidm.session.table_core import TableCore


async def lore_turn(core: TableCore, entry: QueueEntry, intent: AskIntent) -> None:
    words = fact_words(entry.text)
    events = ask_events(core.state, intent.actor_id, intent.npc_id, words)
    told = core.apply_all(events) if events else []
    await adjudicated(core, entry, prior=told)
