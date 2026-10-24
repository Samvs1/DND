"""Typed handing-over (M23.3, GOAL "Items": "give the bell-tongue to Yeva" is deterministic).

The `give_carried` and `give_missing` phrase rows (data/bg3/intent_phrases.json: "give the
tide-orders to gorran", "hand over the hymnal to the cantor", "give yeva the bell-tongue"; the
sentence, its part before a comma and its part before "and" are tried in turn) give the `item`
and `who` slots; the resolvers return a `GiveIntent` when they name a thing the actor carries (a
keepsake first, then an inventory item; words compared through `rules.quest_items.item_words`;
M29.7a R18: showing is not giving, "show" is no hand-over verb; R23: a keepsake is also named
by its description, or, when its quest's deliver step names this NPC, by any word it shares
with the name: "the bent silver coin" is "Mord's Coin" for Mord) and a known, living NPC (a
present one first, by name or role; when two records fit, the one an active quest's deliver
step names; the "give <who> the <thing>" form only for an NPC here). The NPC need not be here:
the rules then refuse in plain words ("Yeva Mossbell is not here."), as they refuse a hostile
one. An abstract gift or coin ("give my thanks to Yeva", "give him a coin": the lexicon's
`abstract_gifts`, the `loose_money` pattern) is None. M29.7a R23: a concrete thing the actor
does not carry is still an intent (`thing` ""), so the rules say so plainly instead of a
storyteller gift; that row (`give_missing`) ranks after paying (M29.9a T17). The rules decide
(`aidm.rules.handing.give_events`). M32.1a X6 (round 5: "hands the three salt-lanterns to Bram"
gave one): a counted keepsake ("the three whole salt-lanterns", "all the salt we have
gathered": a number, or a word of the lexicon's `give_all_words`) is every fitting keepsake up
to the count (`more`); `said` keeps the count asked, so the table can say how many there were.
M33.1 (ultrareview 2: "give two arrows to Bram" gave one arrow and said "had only 1"): a counted
give of a stacked inventory item is that many units, up to the stack held (`more` repeats the
item key, one gift per unit through the same gift path).

Public API: `GiveIntent(actor_id, npc_id, thing, more=(), said=1)` (`thing` a keepsake id, an
inventory key, or "" for nothing carried; `more` further keepsakes, or further units of the
inventory item, of a counted hand-over; `said` the count asked, `GIVE_ALL` for "all"),
`RESOLVERS` (`give_carried`, `give_missing`),
`give_intent(state, actor_id, clean) -> GiveIntent | None` (the give rows alone),
`named_npc(state, who, anywhere)`.
"""

import re
from dataclasses import dataclass

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.entities import display_name
from aidm.dm.intent_match import Found, Resolver, route
from aidm.models.quests import StepKind
from aidm.models.state import Creature, GameState
from aidm.models.world import QuestState, WorldNpc
from aidm.rules.handing import delivers_to
from aidm.rules.quest_items import item_words
from aidm.rules.quest_plan import main_quests
from aidm.rules.scene import current_scene

_PRONOUNS = frozenset({"it", "them", "this", "that", "these", "those", "one", "him", "her"})
_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_NUMBERS |= {"nine": 9, "ten": 10}
GIVE_ALL = 99


@dataclass(frozen=True)
class GiveIntent:
    actor_id: str
    npc_id: str
    thing: str
    more: tuple[str, ...] = ()
    said: int = 1


def _words(text: str) -> frozenset[str]:
    return frozenset(w for w in item_words(text) if len(w) > 1)


def _fits(wanted: frozenset[str], name: str) -> bool:
    have = _words(name)
    return bool(wanted) and bool(have) and (wanted <= have or have <= wanted)


def _keepsakes(state: GameState, actor: Creature, wanted: frozenset[str], npc_id: str) -> list[str]:
    """Every carried keepsake the words name: by name, then by description, then one its
    quest's deliver step owes this NPC that shares a word."""
    assert actor.pc is not None
    held = actor.pc.keepsakes
    named = [k.id for k in held if _fits(wanted, k.name)]
    described = [k.id for k in held if k.description and _fits(wanted, k.description)]
    owed = [
        k.id
        for k in held
        if delivers_to(state, k.quest_id, npc_id)
        and wanted & (_words(k.name) | _words(k.description))
    ]
    return list(dict.fromkeys(named or described or owed))


def _count(phrase: str) -> tuple[int, str]:
    """(how many the words ask for, the words without the count): 1 when none is said."""
    table = intent_phrases()
    plain = phrase.strip().removeprefix("the ")
    first, _, rest = plain.partition(" ")
    if first in table.lexicon["give_all_words"]:
        return GIVE_ALL, rest.removeprefix("of ").removeprefix("the ")
    counted = re.fullmatch(table.patterns["counted"], plain)
    if counted is None:
        return 1, phrase
    n = counted["n"]
    return (int(n) if n.isdigit() else _NUMBERS[n]), counted["rest"]


def _thing(state: GameState, actor: Creature, name: str, npc_id: str) -> str | None:
    """The keepsake or item named; "" for a concrete thing not carried; None for an abstract
    gift or coin (the adjudicator)."""
    if actor.pc is None:
        return None
    wanted = _words(name)
    keepsakes = _keepsakes(state, actor, wanted, npc_id)
    if keepsakes:
        return keepsakes[0]
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
    table = intent_phrases()
    abstract = not wanted or wanted & table.lexicon["abstract_gifts"] or wanted <= _PRONOUNS
    return None if abstract or re.fullmatch(table.patterns["loose_money"], plain) else ""


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


def named_npc(state: GameState, who: str, anywhere: bool) -> str | None:
    """The NPC `who` names: a present one first (by name or role), else any living one."""
    wanted = _words(who)
    present = current_scene(state).npc_ids
    here = _pick(state, [i for i in present if _npc_fits(state.world.npcs[i], wanted)])
    if here is not None or not anywhere:
        return here
    living = sorted((n for n in state.world.npcs.values() if not n.dead), key=lambda n: n.id)
    return _pick(state, [n.id for n in living if _fits(wanted, n.name)])


def _resolve(found: Found) -> GiveIntent | None:
    state = found.state
    actor = state.creatures.get(found.actor_id)
    if actor is None:
        return None
    npc_id = named_npc(state, found.group("who") or "", anywhere=found.params["anywhere"] is True)
    if npc_id is None:
        return None
    said, name = _count(found.group("item") or "")
    thing = _thing(state, actor, name, npc_id)
    if thing is None:
        return None
    if said == 1 or actor.pc is None:
        return GiveIntent(actor.id, npc_id, thing)
    held = next((e.qty for e in actor.pc.inventory if e.item == thing), 0)
    if held:  # a stacked item: one unit per gift, up to the stack held
        return GiveIntent(actor.id, npc_id, thing, (thing,) * (min(said, held) - 1), said)
    more = [k for k in _keepsakes(state, actor, _words(name), npc_id) if k != thing]
    return GiveIntent(actor.id, npc_id, thing, tuple(more[: said - 1]), said)


def give_carried(found: Found) -> GiveIntent | None:
    intent = _resolve(found)
    return intent if intent is not None and intent.thing else None


RESOLVERS: dict[str, Resolver] = {"give_carried": give_carried, "give_missing": _resolve}


def give_intent(state: GameState, actor_id: str, clean: str) -> GiveIntent | None:
    found = route(state, actor_id, clean, RESOLVERS, families=("give",))
    return found if isinstance(found, GiveIntent) else None
