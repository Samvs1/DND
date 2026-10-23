"""Typed handing-over (M23.3, GOAL "Items": "give the bell-tongue to Yeva" is deterministic).

`give_intent(state, actor_id, clean)` reads the precheck's normalised sentence ("give the
tide-orders to gorran", "hand over the hymnal to the cantor", "show the letter to venk", "give
yeva the bell-tongue") and returns a `GiveIntent` when it names a thing the actor carries (a
keepsake first, then an inventory item; words compared through `rules.quest_items.item_words`)
and a known, living NPC (a present one first, by name or role; when two records fit, the one an
active quest's deliver step names). The NPC need not be here: the
rules then refuse in plain words ("Yeva Mossbell is not here."), as they refuse a hostile one.
A sentence naming nothing carried or nobody known is None and goes on to the adjudicator ("give
my thanks to Yeva" is roleplay). The rules decide (`aidm.rules.handing.give_events`).

Public API: `GiveIntent(actor_id, npc_id, thing)` (`thing` a keepsake id or an inventory key),
`give_intent(state, actor_id, clean) -> GiveIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.dm.entities import display_name
from aidm.models.quests import StepKind
from aidm.models.state import Creature, GameState
from aidm.models.world import QuestState, WorldNpc
from aidm.rules.quest_items import item_words
from aidm.rules.quest_plan import main_quests
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


def _quest_receivers(state: GameState) -> frozenset[str]:
    """Who an active quest's deliver step names (side quests, favours, main routes)."""
    steps = [
        s for q in state.world.quests.values() if q.state is QuestState.ACTIVE for s in q.steps
    ]
    if state.campaign is not None:
        mains = main_quests(state.campaign.plan)
        steps += [s for m in mains for r in m.routes for s in r.steps]
    return frozenset(s.npc for s in steps if s.kind is StepKind.DELIVER and s.npc is not None)


def _pick(state: GameState, fitting: list[str]) -> str | None:
    """Two records fit the name (an old plan's boss and cast twin, M29.5b G30): the one a
    quest's deliver step names wins."""
    if len(fitting) < 2:
        return fitting[0] if fitting else None
    named = _quest_receivers(state)
    return next((i for i in fitting if i in named), fitting[0])


def _receiver(state: GameState, who: str, anywhere: bool) -> str | None:
    wanted = _words(who)
    present = current_scene(state).npc_ids
    here = _pick(state, [i for i in present if _npc_fits(state.world.npcs[i], wanted)])
    if here is not None or not anywhere:
        return here
    living = sorted((n for n in state.world.npcs.values() if not n.dead), key=lambda n: n.id)
    return _pick(state, [n.id for n in living if _fits(wanted, n.name)])


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
