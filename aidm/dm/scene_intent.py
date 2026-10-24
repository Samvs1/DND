"""The scene intents of the typed router (SPEC 6.2 pre-checks; moved out of `aidm.dm.precheck` in
M30.0b): rest, look, inventory, shop, travel, a locked way, take, and "what now?".

Each is a phrase row of data/bg3/intent_phrases.json; the resolvers here are the state lookups:
- `rest` (`rest_short`, `rest_long`, and the `rest_*` rows of a wordy sentence, M29.5b G17:
  "take a short rest" or "a long rest" named decides, both named is unclear, a refusal word
  vetoes; else a long phrase beats a short one): `RestIntent(kind)`;
- `look`: `LookIntent` with the deterministic description (`look_around_text`);
- `inventory`: `InventoryIntent(actor_id)`;
- `shop`: a present, friendly shop NPC (by name or role when named) -> `ShopIntent`;
- `travel`: a listed exit by name words -> `TravelIntent`, or a locked one -> `BarredIntent`
  with the world reason; M32.1a X6: a place further on (or "A, then on to B") is the first
  road of the way there with the `goal` (`dm.far_travel`), a place no open road reaches the
  plain reason; only while no encounter offer waits (`no_offer_waits`);
- `barred_lock` (M29.7c R24: "pick the lock on <a locked exit>"): a locked exit (a progress
  gate, not a lock) whose every name word is said gets no check, only the world reason that says
  what opens the way (`aidm.rules.gateway_lock.locked_reason`);
- `take` (M19.3: "pick up / take / grab <a visible item here>") -> `TakeIntent`;
- `what_now` (M23.8): `WhatNowIntent`, answered before the queue (`precheck.asks_what_now`).

Public API: `RestKind`, `RestIntent`, `ShopIntent`, `TravelIntent`, `InventoryIntent`,
`LookIntent`, `TakeIntent`, `BarredIntent`, `WhatNowIntent`, `SHOP_ROLES`, `is_shop`,
`look_around_text(state)`, `RESOLVERS`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from aidm.dm.far_travel import far_route
from aidm.dm.intent_match import Found, Resolver
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.gateway_lock import locked_reason, short_reason
from aidm.rules.scene import current_scene, node_display_name
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
    goal: str | None = None  # M32.1a X6: a place further on, walked hop by hop


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


@dataclass(frozen=True)
class WhatNowIntent:
    actor_id: str


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
_DROP = frozenset({"the", "of", "a", "an"})


def _words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", name.lower().replace("-", " "))) - {"the"}


def is_shop(state: GameState, npc: WorldNpc) -> bool:
    role = _words(npc.role)
    return npc.id == state.world.shop_npc_id or any(r in role for r in SHOP_ROLES)


def rest(found: Found) -> RestIntent:
    return RestIntent(RestKind(str(found.params["kind"])))


def look(found: Found) -> LookIntent:
    return LookIntent(look_around_text(found.state))


def inventory(found: Found) -> InventoryIntent:
    return InventoryIntent(found.actor_id)


def _what_now(found: Found) -> WhatNowIntent:
    return WhatNowIntent(found.actor_id)


def shop(found: Found) -> ShopIntent | None:
    state, who = found.state, found.group("who")
    present = [state.world.npcs[i] for i in current_scene(state).npc_ids]
    shops = [n for n in present if is_shop(state, n) and not n.hostile]
    if who is not None:
        wanted = _words(who)
        shops = [n for n in shops if wanted in (_words(n.name), _words(n.role))]
    if not shops:
        return None
    current = next((n for n in shops if n.id == state.world.shop_npc_id), shops[0])
    return ShopIntent(current.id)


def travel(found: Found) -> TravelIntent | BarredIntent | None:
    state = found.state
    wanted = _words(found.group("dest") or "")
    for node in current_scene(state).exits:
        if wanted not in (_words(node), _words(node_display_name(state, node))):
            continue
        if node in legal_neighbours(state.world, state.world.current_node):
            return TravelIntent(node)
        reason = locked_reason(state, node)
        return BarredIntent(reason) if reason is not None else None
    far = far_route(state, found.group("dest") or "")  # M32.1a X6: further on, or "A, then B"
    if far is None or isinstance(far, str):
        return BarredIntent(far) if far is not None else None
    return TravelIntent(far[0], goal=far[-1] if len(far) > 1 else None)


def barred_lock(found: Found) -> BarredIntent | None:
    state = found.state
    for node in current_scene(state).locked_exits:
        name = _words(node_display_name(state, node)) - _DROP
        if name and name <= found.words:
            reason = locked_reason(state, node)
            return BarredIntent(reason) if reason is not None else None
    return None


def take(found: Found) -> TakeIntent | None:
    state = found.state
    wanted = _words(found.group("item") or "")
    for item_id in current_scene(state).item_ids:
        have = _words(state.world.items[item_id].name)
        if wanted and (have <= wanted or wanted <= have):
            return TakeIntent(found.actor_id, item_id)
    return None


RESOLVERS: dict[str, Resolver] = {
    "rest": rest,
    "look": look,
    "inventory": inventory,
    "what_now": _what_now,
    "shop": shop,
    "travel": travel,
    "barred_lock": barred_lock,
    "take": take,
}


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
