"""A typed question to a person who has something the engine must tell (M31.1b V13).

The `ask_lore` phrase row (data/bg3/intent_phrases.json: an asking word or a question mark)
reads the line; the resolver finds the person it names (a word of the name of an NPC standing
here, filler such as "the" left out; the first one named who has something to tell) and returns
an `AskIntent` only when `rules.lore_talk.ask_events` has something for them: a lesson for an
open learn step or a secret they may reveal now. Otherwise the row gives nothing and the line
goes on to the storyteller as before. The session applies the engine's events first and then
lets the storyteller answer in the person's voice with those events (`session.lore_turn`).

Its act type lives in `aidm.rules.acts` (M36.1); this module only reads text.
Public API: `AskIntent(actor_id, npc_id)`, `RESOLVERS` (`ask_lore`).
"""

from aidm.dm.intent_conditions import name_words
from aidm.dm.intent_match import Found, Resolver
from aidm.rules.acts import AskIntent
from aidm.rules.lore_talk import ask_events
from aidm.rules.secrets import fact_words


def ask_lore(found: Found) -> AskIntent | None:
    state = found.state
    words = fact_words(found.text)
    here = state.world.current_node
    for npc in state.world.npcs.values():
        if npc.node_id != here or npc.dead or not words & name_words(npc.name):
            continue
        if ask_events(state, found.actor_id, npc.id, words):
            return AskIntent(found.actor_id, npc.id)
    return None


RESOLVERS: dict[str, Resolver] = {"ask_lore": ask_lore}
