"""Acts: what a hero does out of a fight, as frozen data (M36.1, moved from the `aidm.dm.*_intent`
modules; SPEC 6.2). Pure types, no logic: an act carries ids only and the session runs it through
the rules, the same code paths the buttons use. The fight acts are in `aidm.rules.acts_fight`.

Public API:
- `RestKind` (SHORT/LONG), `RestIntent(kind)`, `ShopIntent(npc_id)`, `TravelIntent(node_id, goal)`
  (`goal`: a place further on, walked hop by hop), `InventoryIntent(actor_id)`, `LookIntent(text)`,
  `TakeIntent(actor_id, item_id, qty)` (`qty` units of a stack, None = all, M36.4),
  `BarredIntent(text)` (a locked way's reason), `WhatNowIntent(actor_id)`;
- `ItemAction` (EQUIP/UNEQUIP/DROP), `ItemIntent(actor_id, action, item)` (`item` the inventory
  index), `ItemIntents(acts)` (both halves of a compound gear line, in the order said);
- `HelpUpIntent(actor_id, target_id)`, `GiveIntent(actor_id, npc_id, thing, more, said)`,
  `PayIntent(actor_id, npc_id, gold, rest)`, `HeroHandIntent(actor_id, to_id, thing, qty, gold)`,
  `LiftIntent(actor_id, npc_id, keepsake_id)`, `ParleyIntent(actor_id, skill)`,
  `UseIntent(actor_id, item, ...)`, `HealIntent(actor_id, target_ids, item, owner_id, spell)`,
  `CastIntent(actor_id, spell, target_ids, at_scene)`, `QuestAnswerIntent(actor_id, quest_id,
  accept)`, `SearchIntent(actor_id, skill, rest)`, `AskIntent(actor_id, npc_id, said)` (a word
  with a person; `said` the player's words when the menu chose it, M36.4),
  `OfferStrikeIntent(actor_id, step)` (an attack while an encounter offer waits; M36.4: `step` the
  menu strike to play on the hero's turn, `rules.menu_steps.resume_strike`),
  `RefusedIntent(actor_id, text)` (a plain no-roll answer), `ImpossibleIntent(actor_id, text,
  reason)` (a feat no body could do);
- M36.4 (the menu's acts, `rules.menu_steps`): `LootIntent(actor_id, from_id, thing, qty, gold)`
  (taking from a downed or dead hero's pack out of a fight, `rules.hero_handing.loot_events`),
  `FeatureUseIntent(actor_id, feature_id)` (a class feature used out of a fight,
  `rules.feature_commands.explore_feature_events`), `LookAroundIntent(actor_id)` (the session
  writes the look-around text, then plays it as `LookIntent`), `OtherIntent(actor_id, text)` (a
  line off the menu: the storyteller's creative or social call);
- M36.8c: `PersonStrikeIntent(actor_id, npc_id, attack)` (an attack on a person here out of a
  fight: `start_encounter` against them with the opening strike `attack`, a weapon option key;
  a non-hostile person asks the point-of-no-return question first);
- `Intent`: the union of the acts above.
"""

from dataclasses import dataclass
from enum import StrEnum

from aidm.models.abilities import Skill
from aidm.models.action_menu import MenuStep


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
    qty: int | None = None  # M36.4: units of a stack; None = all of it


@dataclass(frozen=True)
class BarredIntent:
    text: str


@dataclass(frozen=True)
class WhatNowIntent:
    actor_id: str


class ItemAction(StrEnum):
    EQUIP = "equip"
    UNEQUIP = "unequip"
    DROP = "drop"


@dataclass(frozen=True)
class ItemIntent:
    actor_id: str
    action: ItemAction
    item: str


@dataclass(frozen=True)
class ItemIntents:
    """Both halves of a compound gear line, in the order said (M31.1a V7)."""

    acts: tuple[ItemIntent, ...]


@dataclass(frozen=True)
class HelpUpIntent:
    actor_id: str
    target_id: str


GIVE_ALL = 99  # `GiveIntent.said` for "all of them"


@dataclass(frozen=True)
class GiveIntent:
    actor_id: str
    npc_id: str
    thing: str
    more: tuple[str, ...] = ()
    said: int = 1


@dataclass(frozen=True)
class PayIntent:
    actor_id: str
    npc_id: str
    gold: int
    rest: str | None = None


@dataclass(frozen=True)
class HeroHandIntent:
    actor_id: str
    to_id: str
    thing: str | None  # an inventory key or keepsake id; "" when the actor carries no such thing
    qty: int = 1
    gold: int = 0


@dataclass(frozen=True)
class LiftIntent:
    actor_id: str
    npc_id: str
    keepsake_id: str


@dataclass(frozen=True)
class ParleyIntent:
    actor_id: str
    skill: Skill


@dataclass(frozen=True)
class UseIntent:
    actor_id: str
    item: str
    target: str | None = None
    verb: str | None = None
    put_out: bool = False
    at_rest: bool = False
    use_id: str | None = None  # M27.6: the use a verb picks ("throw" the torch, not "light")
    rest: str | None = None  # M29.7a: the other act of a compound sentence


@dataclass(frozen=True)
class HealIntent:
    actor_id: str
    target_ids: tuple[str, ...]
    item: str | None = None
    owner_id: str | None = None  # who carries the item
    spell: str | None = None


@dataclass(frozen=True)
class CastIntent:
    actor_id: str
    spell: str
    target_ids: tuple[str, ...]
    at_scene: bool = False


@dataclass(frozen=True)
class QuestAnswerIntent:
    actor_id: str
    quest_id: str
    accept: bool


@dataclass(frozen=True)
class SearchIntent:
    actor_id: str
    skill: Skill
    rest: str | None = None


@dataclass(frozen=True)
class AskIntent:
    actor_id: str
    npc_id: str
    said: str = ""  # M36.4: the player's words, when the menu chose the talk


@dataclass(frozen=True)
class OfferStrikeIntent:
    actor_id: str
    step: MenuStep | None = None  # M36.4: the menu strike, played on the hero's turn


@dataclass(frozen=True)
class RefusedIntent:
    actor_id: str
    text: str


@dataclass(frozen=True)
class ImpossibleIntent:
    actor_id: str
    text: str
    reason: str


@dataclass(frozen=True)
class LootIntent:
    actor_id: str
    from_id: str
    thing: str | None  # an inventory key or keepsake id; None for gold only
    qty: int = 1
    gold: int = 0


@dataclass(frozen=True)
class FeatureUseIntent:
    actor_id: str
    feature_id: str


@dataclass(frozen=True)
class LookAroundIntent:
    actor_id: str


@dataclass(frozen=True)
class PersonStrikeIntent:
    actor_id: str
    npc_id: str
    attack: str | None = None


@dataclass(frozen=True)
class OtherIntent:
    actor_id: str
    text: str


type Intent = (
    RestIntent
    | ShopIntent
    | TravelIntent
    | ItemIntent
    | ItemIntents
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
    | CastIntent
    | QuestAnswerIntent
    | SearchIntent
    | AskIntent
    | OfferStrikeIntent
    | RefusedIntent
    | ImpossibleIntent
    | LootIntent
    | FeatureUseIntent
    | LookAroundIntent
    | PersonStrikeIntent
    | OtherIntent
)
