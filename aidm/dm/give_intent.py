"""Typed handing-over (M23.3, GOAL "Items": "give the bell-tongue to Yeva" is deterministic).

`give_intent(state, actor_id, clean)` reads the precheck's normalised sentence ("give the
tide-orders to gorran", "hand over the hymnal to the cantor", "give yeva the bell-tongue") and
returns a `GiveIntent` when it names a thing the actor carries (a keepsake first, then an
inventory item; words compared through `rules.quest_items.item_words`; M29.7a R18: showing is
not giving, "show" is no hand-over verb; R23: a keepsake is also named by its description, or,
when its quest's deliver step names this NPC, by any word it shares with the name: "the bent
silver coin" is "Mord's Coin" for Mord)
and a known, living NPC (a present one first, by name or role; when two records fit, the one an
active quest's deliver step names). The NPC need not be here: the
rules then refuse in plain words ("Yeva Mossbell is not here."), as they refuse a hostile one.
M29.5c G31: the hero's own name with a third-person verb ("Rook hands the scroll over to Ranna,
giving it into her hands") reads the same, a trailing clause cut. A sentence naming nobody known
is None and goes on to the adjudicator; so is an abstract gift or coin ("give my thanks to
Yeva", "give him a coin": `hand_intent.ABSTRACT_GIFTS`, `_MONEY`). M29.7a R23: a concrete thing
the actor does not carry is still an intent (`thing` ""), so the rules say so plainly instead
of a storyteller gift. The rules decide (`aidm.rules.handing.give_events`).

Public API: `GiveIntent(actor_id, npc_id, thing)` (`thing` a keepsake id, an inventory key,
or "" for nothing carried),
`give_intent(state, actor_id, clean) -> GiveIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.dm.entities import display_name
from aidm.dm.hand_intent import ABSTRACT_GIFTS
from aidm.models.quests import StepKind
from aidm.models.state import Creature, GameState
from aidm.models.world import QuestState, WorldNpc
from aidm.rules.quest_items import item_words
from aidm.rules.quest_plan import main_quests
from aidm.rules.scene import current_scene

_THING = r"(?:my |the |a |an |this |that |our )?(?P<{}>[a-z0-9 ,'-]+?)"
_GIVE = re.compile(
    r"(?:give|hand|pass|offer|present|deliver|return)(?: over| back)? "
    + _THING.format("item")
    + r"(?: over| back)? to (?:the )?(?P<who>[a-z0-9' -]+?)|"
    r"(?:give|hand|pass|offer|return) (?P<who2>[a-z0-9' -]+?) "
    r"(?:my |the |our |this |that )(?P<item2>[a-z0-9 ,'-]+?)"
)


_PRONOUNS = frozenset({"it", "them", "this", "that", "these", "those", "one", "him", "her"})
_THIRD = {
    "gives": "give",
    "hands": "hand",
    "passes": "pass",
    "offers": "offer",
    "presents": "present",
    "delivers": "deliver",
    "returns": "return",
}


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


_MONEY = re.compile(
    r"(?:\d+|some|a few|a|an|one|two|three|a handful of|a bit of|a little)? ?"
    r"(?:gold|silver|copper|coin|coins|gold coins?|silver coins?|copper coins?|gp|sp|cp|money)"
    r"(?: pieces?| coins?)?"
)


def _delivers_to(state: GameState, quest_id: str | None, npc_id: str) -> bool:
    """A quest (side, favour or main route) whose deliver step names this NPC."""
    if quest_id is None:
        return False
    quest = state.world.quests.get(quest_id)
    steps = list(quest.steps) if quest is not None else []
    if state.campaign is not None:
        mains = main_quests(state.campaign.plan)
        steps += [s for m in mains if m.id == quest_id for r in m.routes for s in r.steps]
    return any(s.kind is StepKind.DELIVER and s.npc == npc_id for s in steps)


def _keepsake(state: GameState, actor: Creature, wanted: frozenset[str], npc_id: str) -> str | None:
    assert actor.pc is not None
    held = actor.pc.keepsakes
    named = next((k.id for k in held if _fits(wanted, k.name)), None)
    described = next((k.id for k in held if k.description and _fits(wanted, k.description)), None)
    owed = [
        k.id
        for k in held
        if _delivers_to(state, k.quest_id, npc_id)
        and wanted & (_words(k.name) | _words(k.description))
    ]
    return named or described or (owed[0] if owed else None)


def _thing(state: GameState, actor: Creature, name: str, npc_id: str) -> str | None:
    """The keepsake or item named; "" for a concrete thing not carried; None for an abstract
    gift or coin (the adjudicator)."""
    if actor.pc is None:
        return None
    wanted = _words(name)
    keepsake = _keepsake(state, actor, wanted, npc_id)
    if keepsake is not None:
        return keepsake
    item = next(
        (
            e.item
            for e in actor.pc.inventory
            if _fits(wanted, e.item) or _fits(wanted, display_name(e.item))
        ),
        None,
    )
    if item is not None:
        return item
    plain = name.strip().removeprefix("some ")
    abstract = not wanted or wanted & ABSTRACT_GIFTS or wanted <= _PRONOUNS
    return None if abstract or _MONEY.fullmatch(plain) else ""


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


def _readings(actor: Creature, clean: str) -> list[str]:
    """M29.5c G31: "rook hands the receipt-scroll over to ranna, giving it into her hands" is a
    hand-over too: the hero's own name and a third-person verb read as "hand ...", and a
    trailing clause (after a comma or "and") is cut."""
    text = clean
    name = actor.name.lower()
    for prefix in (name, name.split()[0]):
        if text.startswith(f"{prefix} "):
            verb, _, rest = text[len(prefix) + 1 :].partition(" ")
            text = f"{_THIRD.get(verb, verb)} {rest}".strip()
            break
    cuts = [text, text.split(",")[0].strip(), text.split(" and ")[0].strip()]
    return list(dict.fromkeys(c for c in cuts if c))


def _intent(state: GameState, actor: Creature, reading: str) -> GiveIntent | None:
    match = _GIVE.fullmatch(reading)
    if match is None:
        return None
    if match["who"] is not None:
        item, npc_id = match["item"], _receiver(state, match["who"], anywhere=True)
    else:
        item, npc_id = match["item2"], _receiver(state, match["who2"], anywhere=False)
    if npc_id is None:
        return None
    thing = _thing(state, actor, item, npc_id)
    if thing is None:
        return None
    return GiveIntent(actor.id, npc_id, thing)


def give_intent(state: GameState, actor_id: str, clean: str) -> GiveIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None:
        return None
    found = [i for r in _readings(actor, clean) if (i := _intent(state, actor, r)) is not None]
    return next((i for i in found if i.thing), found[0] if found else None)
