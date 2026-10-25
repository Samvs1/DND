"""Typed lifting of a keepsake an NPC holds (M29.7a R18: "I slip my fingers into his pouch and lift
the Bailiff's Broken Link back out (Sleight of Hand)" was a storyteller check with no item moving).

The `lift` phrase row (data/bg3/intent_phrases.json: lift, steal, pickpocket, pick his pocket,
snatch, filch, swipe, pilfer, palm, nick, take back, grab back, slip ... out) finds a stealing
word; the resolver finds a keepsake that an NPC here holds (`WorldNpc.keepsakes`), named by its
name words (every word of the name in the sentence, or at least two of them). The rules roll and
decide (`aidm.rules.lifting.lift_events`). Anything else is None (the adjudicator).

Its act type lives in `aidm.rules.acts` (M36.1); this module only reads text.
Public API: `LiftIntent(actor_id, npc_id, keepsake_id)`, `RESOLVERS` (`lift`).
"""

from aidm.dm.intent_match import Found, Resolver
from aidm.rules.acts import LiftIntent
from aidm.rules.quest_items import item_words
from aidm.rules.scene import current_scene


def _named(name: str, said: frozenset[str]) -> bool:
    words = frozenset(w for w in item_words(name) if len(w) > 1)
    return bool(words) and (words <= said or len(words & said) >= 2)


def lift(found: Found) -> LiftIntent | None:
    state = found.state
    actor = state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    said = item_words(found.text)
    for npc_id in current_scene(state).npc_ids:
        npc = state.world.npcs[npc_id]
        held = next((k for k in npc.keepsakes if _named(k.name, said)), None)
        if held is not None and not npc.dead:
            return LiftIntent(found.actor_id, npc_id, held.id)
    return None


RESOLVERS: dict[str, Resolver] = {"lift": lift}
