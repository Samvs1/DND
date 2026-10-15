"""Typed handing-over (M23.3, GOAL "Items": "give the bell-tongue to Yeva" is deterministic).

`give_intent(state, actor_id, clean)` reads the precheck's normalised sentence ("give the
tide-orders to gorran", "hand over the hymnal to the cantor", "show the letter to venk", "give
yeva the bell-tongue") and returns a `GiveIntent` when it names a thing the actor carries (a
keepsake first, then an inventory item; words compared through `rules.quest_items.item_words`)
and a known, living NPC (a present one first, by name or role). The NPC need not be here: the
rules then refuse in plain words ("Yeva Mossbell is not here."), as they refuse a hostile one.
A sentence naming nothing carried or nobody known is None and goes on to the adjudicator ("give
my thanks to Yeva" is roleplay). The rules decide (`aidm.rules.handing.give_events`).

Public API: `GiveIntent(actor_id, npc_id, thing)` (`thing` a keepsake id or an inventory key),
`give_intent(state, actor_id, clean) -> GiveIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.dm.entities import display_name
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldNpc
from aidm.rules.quest_items import item_words
from aidm.rules.scene import current_scene

_THING = r"(?:my |the |a |an |this |that |our )?(?P<{}>[a-z0-9 ,'-]+?)"
_GIVE = re.compile(
    r"(?:give|hand|pass|offer|present|show|deliver)(?: over| back)? "
    + _THING.format("item")
    + r"(?: over| back)? to (?:the )?(?P<who>[a-z0-9' -]+?)|"
    r"(?:give|hand|pass|offer|show) (?P<who2>[a-z0-9' -]+?) "
    r"(?:my |the |our |this |that )(?P<item2>[a-z0-9 ,'-]+?)"
)


@dataclass(frozen=True)
class GiveIntent:
    actor_id: str
    npc_id: str
    thing: str


def _words(text: str) -> frozenset[str]:
    return frozenset(w for w in item_words(text) if len(w) > 1)


def _fits(wanted: frozenset[str], name: str) -> bool:
    have = _words(name)
    return bool(wanted) and bool(have) and (wanted <= have or have <= wanted)


def _thing(actor: Creature, name: str) -> str | None:
    if actor.pc is None:
        return None
    wanted = _words(name)
    keepsake = next((k.id for k in actor.pc.keepsakes if _fits(wanted, k.name)), None)
    if keepsake is not None:
        return keepsake
    return next(
        (
            e.item
            for e in actor.pc.inventory
            if _fits(wanted, e.item) or _fits(wanted, display_name(e.item))
        ),
        None,
    )


def _npc_fits(npc: WorldNpc, wanted: frozenset[str]) -> bool:
    return _fits(wanted, npc.name) or (bool(npc.role) and _words(npc.role) == wanted)


def _receiver(state: GameState, who: str, anywhere: bool) -> str | None:
    wanted = _words(who)
    present = current_scene(state).npc_ids
    here = next((i for i in present if _npc_fits(state.world.npcs[i], wanted)), None)
    if here is not None or not anywhere:
        return here
    living = sorted((n for n in state.world.npcs.values() if not n.dead), key=lambda n: n.id)
    return next((n.id for n in living if _fits(wanted, n.name)), None)


def give_intent(state: GameState, actor_id: str, clean: str) -> GiveIntent | None:
    match = _GIVE.fullmatch(clean)
    actor = state.creatures.get(actor_id)
    if match is None or actor is None:
        return None
    if match["who"] is not None:
        item, npc_id = match["item"], _receiver(state, match["who"], anywhere=True)
    else:
        item, npc_id = match["item2"], _receiver(state, match["who2"], anywhere=False)
    thing = _thing(actor, item)
    if npc_id is None or thing is None:
        return None
    return GiveIntent(actor_id, npc_id, thing)
