"""Deterministic pre-checks: obvious typed commands handled without the LLM (SPEC 6.2).

`precheck(state, actor_id, text)` maps a CLEAR command to a typed intent and returns None for
everything else (the adjudicator decides then). It is conservative on purpose: a phrase row of
data/bg3/intent_phrases.json must match the sentence (most rows the whole normalised sentence)
AND its resolver must find something that exists (a listed neighbour, a present shop NPC, an
item the actor carries). "Look around for traps" or "draw a map" therefore go to the
adjudicator. Nothing here runs during a fight (combat uses structured commands and
`intent_router.fight_intent`). Intents carry ids only; the session executes them through the
rules. M30.0b: the one router (`aidm.dm.intent_router`, scope `explore`) decides; which
intent wins is the rows' `precedence`, never call order:
help up, parley (while an offer waits), short and long rest, look, inventory, lift, give a
carried thing, pay, give a thing not carried, hand to a hero, heal, a rest in a longer
sentence, shop, travel, a locked way, equip / unequip / drop, light first, gear use, take.

Public API:
- Intents (frozen): `RestIntent(kind)` (`RestKind` SHORT/LONG), `ShopIntent(npc_id)`,
  `TravelIntent(node_id)`, `InventoryIntent(actor_id)`, `LookIntent(text)`, `TakeIntent`,
  `BarredIntent(text)` (`aidm.dm.scene_intent`), `ItemIntent` (`aidm.dm.equip_intent`),
  `HelpUpIntent`, `GiveIntent`, `HeroHandIntent`, `LiftIntent`, `PayIntent`, `ParleyIntent`,
  `UseIntent`, `HealIntent` (their `*_intent` modules);
- `Intent` (the union), `precheck(state, actor_id, text) -> Intent | None`;
- `gear_intent(state, actor_id, text) -> UseIntent | None`: the gear rows alone, for the typed
  actions of a fight (M27.5: putting a light out is free, lighting one a bonus action);
- `gear_phrase(text) -> (phrase, mine) | None`: the gear a throw or use sentence names (M27.6);
- `asks_what_now(state, actor_id, text) -> bool` (M23.8: "what now", "what should we do",
  "where to", "i'm lost", "help me"...; never "help <a downed hero> up", the help-up row ranks
  first). It is answered before the queue, also in a fight: What now? is not a turn;
- `look_around_text(state) -> str`, `SHOP_ROLES`, `is_shop` (`aidm.dm.scene_intent`).
"""

from aidm.dm.equip_intent import ItemIntent
from aidm.dm.give_intent import GiveIntent
from aidm.dm.hand_intent import HeroHandIntent
from aidm.dm.heal_intent import HealIntent
from aidm.dm.help_intent import HelpUpIntent
from aidm.dm.intent_router import ask_intent, explore_intent
from aidm.dm.lift_intent import LiftIntent
from aidm.dm.parley_intent import ParleyIntent
from aidm.dm.pay_intent import PayIntent
from aidm.dm.scene_intent import (
    SHOP_ROLES,
    BarredIntent,
    InventoryIntent,
    LookIntent,
    RestIntent,
    RestKind,
    ShopIntent,
    TakeIntent,
    TravelIntent,
    WhatNowIntent,
    is_shop,
    look_around_text,
)
from aidm.dm.sentence import normalise
from aidm.dm.use_intent import UseIntent, item_phrase, use_intent
from aidm.models.state import GameState

__all__ = [
    "SHOP_ROLES",
    "BarredIntent",
    "Intent",
    "InventoryIntent",
    "ItemIntent",
    "LookIntent",
    "RestIntent",
    "RestKind",
    "ShopIntent",
    "TakeIntent",
    "TravelIntent",
    "asks_what_now",
    "gear_intent",
    "gear_phrase",
    "is_shop",
    "look_around_text",
    "precheck",
]

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
_INTENTS = (
    RestIntent,
    ShopIntent,
    TravelIntent,
    ItemIntent,
    InventoryIntent,
    LookIntent,
    TakeIntent,
    HelpUpIntent,
    GiveIntent,
    PayIntent,
    HeroHandIntent,
    LiftIntent,
    ParleyIntent,
    BarredIntent,
    UseIntent,
    HealIntent,
)


def precheck(state: GameState, actor_id: str, text: str) -> Intent | None:
    found = explore_intent(state, actor_id, text)
    return found if isinstance(found, _INTENTS) else None


def asks_what_now(state: GameState, actor_id: str, text: str) -> bool:
    return isinstance(ask_intent(state, actor_id, text), WhatNowIntent)


def gear_intent(state: GameState, actor_id: str, text: str) -> UseIntent | None:
    clean = normalise(text)
    return use_intent(state, actor_id, clean) if clean else None


def gear_phrase(text: str) -> tuple[str, bool] | None:
    """The gear a throw or use sentence names, and whether it is said as the hero's own."""
    clean = normalise(text)
    return item_phrase(clean) if clean else None
