"""Typed lifting of a keepsake an NPC holds (M29.7a R18: "I slip my fingers into his pouch and lift
the Bailiff's Broken Link back out (Sleight of Hand)" was a storyteller check with no item moving).

`lift_intent(state, actor_id, clean)` reads the precheck's normalised sentence: a stealing word
(lift, steal, pickpocket, pick his pocket, snatch, filch, swipe, pilfer, palm, nick, take back,
grab back, slip ... out) and a keepsake that an NPC here holds (`WorldNpc.keepsakes`), named by
its name words (every word of the name in the sentence, or at least two of them). The rules roll
and decide (`aidm.rules.lifting.lift_events`). Anything else is None (the adjudicator).

Public API: `LiftIntent(actor_id, npc_id, keepsake_id)`,
`lift_intent(state, actor_id, clean) -> LiftIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.models.state import GameState
from aidm.rules.quest_items import item_words
from aidm.rules.scene import current_scene

_STEAL = re.compile(
    r"\b(?:lift|lifts|steal|steals|pickpocket|pickpockets|pick (?:his|her|their) pocket|snatch|"
    r"snatches|filch|filches|swipe|swipes|pilfer|pilfers|palm|palms|nick|nicks|"
    r"(?:take|takes|grab|grabs|get|gets|slip|slips|sneak|sneaks) (?:it |the [a-z' -]+ )?back|"
    r"(?:slip|slips|fish|fishes|ease|eases) [a-z' -]+ out)\b"
)


@dataclass(frozen=True)
class LiftIntent:
    actor_id: str
    npc_id: str
    keepsake_id: str


def _named(name: str, said: frozenset[str]) -> bool:
    words = frozenset(w for w in item_words(name) if len(w) > 1)
    return bool(words) and (words <= said or len(words & said) >= 2)


def lift_intent(state: GameState, actor_id: str, clean: str) -> LiftIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None or _STEAL.search(clean) is None:
        return None
    said = item_words(clean)
    for npc_id in current_scene(state).npc_ids:
        npc = state.world.npcs[npc_id]
        held = next((k for k in npc.keepsakes if _named(k.name, said)), None)
        if held is not None and not npc.dead:
            return LiftIntent(actor_id, npc_id, held.id)
    return None
