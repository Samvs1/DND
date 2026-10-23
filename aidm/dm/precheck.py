"""Deterministic pre-checks: obvious exploration commands handled without the LLM (SPEC 6.2).

`precheck(state, actor_id, text)` maps a CLEAR command to a typed intent and returns None for
everything else (the adjudicator decides then). It is conservative on purpose: the whole
(normalised) sentence must match one command pattern AND name something that exists (a listed
neighbour, a present shop NPC, an item the actor carries). "Look around for traps" or "draw a
map" therefore go to the adjudicator. Nothing here runs during a fight (combat uses structured
commands). Intents carry ids only; the session executes them through the rules.

Public API:
- Intents (frozen): `RestIntent(kind)` (`RestKind` SHORT/LONG), `ShopIntent(npc_id)`,
  `TravelIntent(node_id)`, `ItemIntent` (equip / unequip / drop, `aidm.dm.equip_intent`),
  `InventoryIntent(actor_id)`,
  `LookIntent(text)` (the deterministic description, `look_around_text`),
  `TakeIntent(actor_id, item_id)` (M19.3: "pick up / take / grab <a visible item here>"),
  `HelpUpIntent(actor_id, target_id)` (M20.2: "help her up", "wake <a downed hero>";
  `aidm.dm.help_intent`), `GiveIntent(actor_id, npc_id, thing)` (M23.3: "give the <thing> to
  <name>"; `aidm.dm.give_intent`), `HeroHandIntent` (M29.7a R7/R8: "hand the poultice to Elowen",
  "give Elowen 30 gold": to another hero, before healing; `aidm.dm.hand_intent`),
  `LiftIntent` (M29.7a R18: "lift the link back out of his pouch": a keepsake an NPC here holds;
  `aidm.dm.lift_intent`, before a give), `PayIntent` (M29.9a T17: "pay Rutter 4 silver", "hand
  Rutter a gold piece": coins to an NPC, when no carried thing is named; `aidm.dm.pay_intent`),
  `ParleyIntent` (M29.7a R4: talking to the foes while an
  encounter offer waits answers it as parley, `aidm.dm.parley_intent`), `BarredIntent(text)`
  (M23.8: "go to <a locked exit>"; the world reason, `aidm.rules.gateway_lock`; M29.7c R24:
  "pick the lock on <a locked exit>" too, no check, `aidm.dm.lock_intent`), `UseIntent`
  (M27.5: "light my torch", "use X on Y", "put out my torch"...; `aidm.dm.use_intent`, after
  the item commands), `HealIntent` (M29.5b: "drink my potion", "pour my potion into Rook",
  "cast cure wounds on Tamsin"; `aidm.dm.heal_intent`, after a give to an NPC); a rest named
  inside a longer sentence is a `RestIntent` too (M29.5b, `aidm.dm.rest_words`, after healing).
  M29.7a: the hero's own name with a third-person verb reads as the hero's command
  (`aidm.dm.sentence.own_reading`), and a compound sentence that lights or puts out a light
  first is that `UseIntent` with `rest`, the other act (`use_intent.light_first`, R17).
- `Intent` (the union), `precheck(state, actor_id, text) -> Intent | None`.
- `gear_intent(state, actor_id, text) -> UseIntent | None`: the gear precheck alone, for the
  typed actions of a fight (M27.5: putting a light out is free, lighting one a bonus action).
- `gear_phrase(text) -> (phrase, mine) | None`: the gear a throw or use sentence names (M27.6).
- `asks_what_now(state, actor_id, text) -> bool` (M23.8: "what now", "what should we do", "where
  to", "i'm lost", "help me"...; never "help <a downed hero> up", the help-up pre-check wins).
  It is answered before the queue, also in a fight: What now? is not a turn.
- `look_around_text(state) -> str`: the scene manifest as plain prose.
- `SHOP_ROLES`: role words that make a present NPC a shopkeeper.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from aidm.dm.equip_intent import ItemIntent, item_command
from aidm.dm.give_intent import GiveIntent, give_intent
from aidm.dm.hand_intent import HeroHandIntent, hand_intent
from aidm.dm.heal_intent import HealIntent, heal_intent
from aidm.dm.help_intent import HelpUpIntent, help_up_intent
from aidm.dm.lift_intent import LiftIntent, lift_intent
from aidm.dm.lock_intent import barred_lock_reason
from aidm.dm.parley_intent import ParleyIntent, parley_intent
from aidm.dm.pay_intent import PayIntent, pay_intent
from aidm.dm.rest_words import wordy_rest
from aidm.dm.sentence import normalise, own_reading
from aidm.dm.use_intent import UseIntent, item_phrase, light_first, use_intent
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.gateway_lock import locked_reason, short_reason
from aidm.rules.scene import SceneView, current_scene, node_display_name
from aidm.rules.world_graph import legal_neighbours


class RestKind(StrEnum):
    SHORT = "short"
    LONG = "long"


@dataclass(frozen=True)
class RestIntent:
    kind: RestKind


@dataclass(frozen=True)
class ShopIntent:
    npc_id: str


@dataclass(frozen=True)
class TravelIntent:
    node_id: str


@dataclass(frozen=True)
class InventoryIntent:
    actor_id: str


@dataclass(frozen=True)
class LookIntent:
    text: str


@dataclass(frozen=True)
class TakeIntent:
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class BarredIntent:
    text: str


type Intent = (
    RestIntent
    | ShopIntent
    | TravelIntent
    | ItemIntent
    | InventoryIntent
    | LookIntent
    | TakeIntent
    | HelpUpIntent
    | GiveIntent
    | PayIntent
    | HeroHandIntent
    | LiftIntent
    | ParleyIntent
    | BarredIntent
    | UseIntent
    | HealIntent
)

SHOP_ROLES = (
    "merchant",
    "shopkeeper",
    "shopkeep",
    "trader",
    "vendor",
    "peddler",
    "smith",
    "blacksmith",
    "armorer",
    "armourer",
    "alchemist",
    "fletcher",
    "quartermaster",
)

_SHORT = re.compile(
    r"(?:take |have )?(?:a )?short rest|rest (?:for )?(?:an|one|a) hour|"
    r"(?:catch (?:our|my) breath|take a breather)"
)
_LONG = re.compile(
    r"(?:take |have )?(?:a )?long rest|(?:make|set up|pitch) camp(?: for the night)?|"
    r"camp for the night|rest for the night|rest until (?:morning|dawn)|"
    r"(?:go to )?sleep for the night|bed down(?: for the night)?"
)
_SHOP = re.compile(
    r"(?:shop|browse(?: (?:the|their|his|her) wares)?|(?:see|look at) (?:the|their|his|her) wares|"
    r"open (?:the|their|his|her) shop|trade|barter|buy something|buy supplies|"
    r"(?:buy|purchase|shop|trade|barter) (?:from|with) (?P<who>[a-z' -]+))"
)
_TRAVEL = re.compile(
    r"(?:go|travel|head|walk|move|return|journey|ride|set off|set out|proceed|make (?:our|my) way)"
    r"(?: back)? (?:to|towards?|into|for) (?:the )?(?P<dest>[a-z0-9' -]+)"
)
_TAKE = re.compile(
    r"(?:pick up|take|grab|collect|retrieve|scoop up|pocket|lift|get) (?:up )?"
    r"(?:the |a |an |that |this )?(?P<item>[a-z0-9 ,'-]+?)(?: up)?"
    r"(?: (?:from|off|at|on) (?:the )?[a-z0-9 ,'-]+)?|"
    r"pick (?:the |a |an |that |this )?(?P<item2>[a-z0-9 ,'-]+?) up"
)
_INVENTORY = re.compile(
    r"(?:(?:check|open|show|see|look in|look at) )?(?:my |our )?"
    r"(?:inventory|pack|backpack|bag|belongings)|what (?:am i|are we) carrying|"
    r"what do (?:i|we) have"
)
_LOOK = re.compile(
    r"look|look around|look about|glance around|"
    r"(?:look|glance) around (?:the )?(?:room|area|place)|"
    r"survey (?:the )?(?:area|room|surroundings|scene)|take in (?:the|my|our) surroundings|"
    r"what do (?:i|we) see|where am i|where are we|"
    r"describe (?:the )?(?:room|area|place|scene|surroundings)"
)


_WHAT_NOW = re.compile(
    r"(?:so |ok |okay |hmm |um |well )?(?:"
    r"what now|now what|what next|what(?: is|'s) next|what(?: is|'s) the plan|"
    r"what (?:should|do|can|must) (?:i|we) do(?: now| next| here)?|"
    r"where to(?: now| next)?|where (?:do|should|can) (?:i|we) go(?: now| next| from here)?|"
    r"where now|(?:i'm|i am|we're|we are) lost|help(?: me| us)?|"
    r"(?:give (?:me|us) )?a hint|hint|any (?:ideas|hints)"
    r")"
)


def asks_what_now(state: GameState, actor_id: str, text: str) -> bool:
    clean = " ".join(text.lower().replace("’", "'").split()).strip(" .!?")
    if _WHAT_NOW.fullmatch(clean) is None:
        return False
    return help_up_intent(state, actor_id, normalise(text)) is None


def _words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", name.lower().replace("-", " "))) - {"the"}


def _in_fight(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def _travel(state: GameState, scene: SceneView, dest: str) -> TravelIntent | BarredIntent | None:
    wanted = _words(dest)
    if state.campaign is not None and state.campaign.offer is not None:
        return None
    for node in scene.exits:
        if wanted not in (_words(node), _words(node_display_name(state, node))):
            continue
        if node in legal_neighbours(state.world, state.world.current_node):
            return TravelIntent(node)
        reason = locked_reason(state, node)
        return BarredIntent(reason) if reason is not None else None
    return None


def is_shop(state: GameState, npc: WorldNpc) -> bool:
    role = _words(npc.role)
    return npc.id == state.world.shop_npc_id or any(r in role for r in SHOP_ROLES)


def _shop(state: GameState, scene: SceneView, who: str | None) -> ShopIntent | None:
    present = [state.world.npcs[i] for i in scene.npc_ids]
    shops = [n for n in present if is_shop(state, n) and not n.hostile]
    if who is not None:
        wanted = _words(who)
        shops = [n for n in shops if wanted in (_words(n.name), _words(n.role))]
    if not shops:
        return None
    current = next((n for n in shops if n.id == state.world.shop_npc_id), shops[0])
    return ShopIntent(current.id)


def _take(state: GameState, scene: SceneView, actor_id: str, name: str) -> TakeIntent | None:
    wanted = _words(name)
    for item_id in scene.item_ids:
        have = _words(state.world.items[item_id].name)
        if wanted and (have <= wanted or wanted <= have):
            return TakeIntent(actor_id, item_id)
    return None


def precheck(state: GameState, actor_id: str, text: str) -> Intent | None:
    if _in_fight(state):
        return None
    actor = state.creatures.get(actor_id)
    clean = normalise(text)
    clean = own_reading(actor.name, clean) if actor is not None else clean
    if not clean:
        return None
    helped = help_up_intent(state, actor_id, clean) or parley_intent(state, actor_id, clean)
    if helped is not None:
        return helped
    if _SHORT.fullmatch(clean):
        return RestIntent(RestKind.SHORT)
    if _LONG.fullmatch(clean):
        return RestIntent(RestKind.LONG)
    if _LOOK.fullmatch(clean):
        return LookIntent(look_around_text(state))
    if _INVENTORY.fullmatch(clean):
        return InventoryIntent(actor_id)
    given = lift_intent(state, actor_id, clean) or give_intent(state, actor_id, clean)
    if given is None or (isinstance(given, GiveIntent) and not given.thing):
        given = pay_intent(state, actor_id, clean) or given  # M29.9a T17: coins to an NPC
    if given is not None:
        return given
    handed = hand_intent(state, actor_id, clean)
    if handed is not None:
        return handed
    healed = heal_intent(state, actor_id, clean)
    if healed is not None:
        return healed
    rest = wordy_rest(clean)
    if rest is not None:
        return RestIntent(RestKind(rest))
    scene = current_scene(state)
    shop = _SHOP.fullmatch(clean)
    if shop:
        return _shop(state, scene, shop["who"])
    travel = _TRAVEL.fullmatch(clean)
    if travel:
        return _travel(state, scene, travel["dest"])
    barred = barred_lock_reason(state, scene.locked_exits, clean)  # M29.7c R24: no check
    if barred is not None:
        return BarredIntent(barred)
    found = item_command(state, actor_id, clean) or light_first(state, actor_id, clean)
    found = found or use_intent(state, actor_id, clean)
    take = _TAKE.fullmatch(clean)
    if found is None and take:
        return _take(state, scene, actor_id, take["item"] or take["item2"])
    return found


def gear_intent(state: GameState, actor_id: str, text: str) -> UseIntent | None:
    clean = normalise(text)
    return use_intent(state, actor_id, clean) if clean else None


def gear_phrase(text: str) -> tuple[str, bool] | None:
    """The gear a throw or use sentence names, and whether it is said as the hero's own."""
    clean = normalise(text)
    return item_phrase(clean) if clean else None


def _listing(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def look_around_text(state: GameState) -> str:
    scene = current_scene(state)
    world = state.world
    parts = [f"You are at {scene.node_name}."]
    if scene.description:
        parts.append(scene.description.strip())
    npcs = [world.npcs[i] for i in scene.npc_ids]
    people = [f"{n.name} ({n.role})" if n.role else n.name for n in npcs]
    parts.append(f"Here with you: {_listing(people)}." if people else "Nobody else is here.")
    foes = [state.creatures[c].name for c in scene.monster_ids]
    if foes:
        parts.append(f"Hostile: {_listing(foes)}.")
    features = [world.features[f].name for f in scene.feature_ids]
    if features:
        parts.append(f"You notice: {_listing(features)}.")
    items = [world.items[i].name for i in scene.item_ids]
    if items:
        parts.append(f"Lying here: {_listing(items)}.")
    exits = [
        node_display_name(state, e)
        + (f" ({short_reason(state, e)})" if e in scene.locked_exits else "")
        for e in scene.exits
    ]
    parts.append(f"Ways on: {_listing(exits)}." if exits else "There is no obvious way on.")
    return " ".join(parts)
