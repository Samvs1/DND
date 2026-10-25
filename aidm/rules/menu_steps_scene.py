"""A chosen out-of-fight menu step as the acts the session runners take (M36.4, SPEC 6.2). Pure.

`scene_step_acts(state, actor_id, entry, step, text)` turns one step of the explore or offer menu
into the acts `session.intent_turn.run_intent` (and the client handlers) already play. Engine
meaning, never wording:
- `travel` to the place the party stands in is a plain "You are already at X." (round 6 Y15:
  never a vote, never an invented blocked road); a place further on is walked hop by hop
  (`TravelIntent(first hop, goal)` over the roads open now, `rules.world_graph.travel_route`); a
  locked way is the world's reason (`BarredIntent`); a known place no open road reaches says
  so; while an encounter offer waits here every other place says it is answered first;
- counts: `give` hands that many units (a keepsake group by name gives that many of its
  keepsakes, `menu_items.same_keepsakes`), `hand`/`loot` move `qty` units, gold or keepsakes,
  `pay` that many gold, `take` that many units of a group lying here (`menu_items.same_lying`,
  `TakeIntent.qty` for part of a stack), `drop` one unit per drop, `buy`/`sell` the count;
- `talk` is the lore/social path carrying the player's words (`AskIntent.said`); `look` the
  look-around (`LookAroundIntent`, the session writes the text);
- `offer:<choice>` is the offer card's answer (`AnswerOffer`), a parley answer the held parley
  (`ParleyIntent`), the surrender demand a parley with its skill or, when every foe is a kind
  that never yields, the rules' plain line;
- a feature is used out of a fight (`FeatureUseIntent`), a draught on a hero is `HealIntent`, a
  spell on heroes `CastIntent` (no creature target: cast at the scene); M36.8c: a `feed:` draught
  comes from the target hero's own pack (`HealIntent.owner_id` the target), and a keepsake taken
  back from a shown person comes from whichever of their twin records holds it.
`free_acts` serves the free answers on any menu (pack, "what now", putting out the light).

Public API: `SceneAct`, `scene_step_acts(state, actor_id, entry, step, text)`,
`free_acts(actor_id, entry)`.
"""

from aidm.models.abilities import Skill
from aidm.models.action_menu import ActionKind, MenuEntry, MenuStep
from aidm.models.campaign_state import OfferChoice
from aidm.models.protocol_client import AnswerOffer, CopyScroll, ShopBuy, ShopSell
from aidm.models.state import GameState
from aidm.rules.acts import (
    AskIntent,
    BarredIntent,
    CastIntent,
    FeatureUseIntent,
    GiveIntent,
    HealIntent,
    HelpUpIntent,
    HeroHandIntent,
    Intent,
    InventoryIntent,
    ItemAction,
    ItemIntent,
    ItemIntents,
    LiftIntent,
    LookAroundIntent,
    LootIntent,
    OtherIntent,
    ParleyIntent,
    PayIntent,
    QuestAnswerIntent,
    RefusedIntent,
    RestIntent,
    RestKind,
    SearchIntent,
    ShopIntent,
    TakeIntent,
    TravelIntent,
    UseIntent,
    WhatNowIntent,
)
from aidm.rules.gateway_lock import locked_reason
from aidm.rules.item_grants import carried_qty
from aidm.rules.menu_items import FEED_OPTION, same_keepsakes, same_lying
from aidm.rules.menu_scene import OFFER_FIRST_NOTE
from aidm.rules.menu_scene_view import twin_boss
from aidm.rules.scene import node_display_name
from aidm.rules.world_graph import travel_route

type SceneAct = Intent | WhatNowIntent | AnswerOffer | ShopBuy | ShopSell | CopyScroll
MAX_TRADE = 99
GONE = "That is no longer lying here."


def free_acts(actor_id: str, entry: MenuEntry) -> list[SceneAct] | None:
    """The free answers open on any menu, or None for any other entry."""
    if entry.kind is ActionKind.INVENTORY:
        return [InventoryIntent(actor_id)]
    if entry.kind is ActionKind.WHAT_NOW:
        return [WhatNowIntent(actor_id)]
    if entry.kind is ActionKind.PUT_OUT:
        return [UseIntent(actor_id, entry.item or "light", put_out=True)]
    return None


def _offer_here(state: GameState) -> bool:
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    return offer is not None and offer.node_id == state.world.current_node


def _travel(state: GameState, actor_id: str, node: str) -> SceneAct:
    world = state.world
    name = node_display_name(state, node)
    if node == world.current_node:
        return RefusedIntent(actor_id, f"You are already at {name}.")
    if _offer_here(state):
        return RefusedIntent(actor_id, f"{OFFER_FIRST_NOTE[0].upper()}{OFFER_FIRST_NOTE[1:]}.")
    route = travel_route(world, world.current_node, node)
    if route:
        return TravelIntent(route[0], goal=node if len(route) > 1 else None)
    reason = locked_reason(state, node)
    if reason is not None:
        return BarredIntent(reason)
    return RefusedIntent(actor_id, f"No open road leads from here to {name}.")


def _unlock(state: GameState, actor_id: str, entry: MenuEntry, node: str) -> SceneAct:
    reason = locked_reason(state, node) or entry.target_notes.get(node)
    if reason:
        return BarredIntent(reason)
    return RefusedIntent(actor_id, f"The way to {node_display_name(state, node)} is open.")


def _give(state: GameState, actor_id: str, entry: MenuEntry, npc: str, qty: int) -> SceneAct:
    hero = state.creatures[actor_id]
    thing = entry.item or ""
    keeps = same_keepsakes(hero.pc.keepsakes, thing) if hero.pc is not None else []
    if keeps:
        ids = keeps[:qty]
        return GiveIntent(actor_id, npc, ids[0], tuple(ids[1:]), qty)
    units = max(1, min(qty, carried_qty(hero, thing)))
    return GiveIntent(actor_id, npc, thing, (thing,) * (units - 1), qty)


def _hand(state: GameState, actor_id: str, entry: MenuEntry, to: str, qty: int) -> list[SceneAct]:
    if entry.item is None:
        return [HeroHandIntent(actor_id, to, None, gold=qty)]
    hero = state.creatures[actor_id]
    keeps = same_keepsakes(hero.pc.keepsakes, entry.item) if hero.pc is not None else []
    if keeps:
        return [HeroHandIntent(actor_id, to, k) for k in keeps[:qty]]
    return [HeroHandIntent(actor_id, to, entry.item, qty=qty)]


def _loot(
    state: GameState, actor_id: str, entry: MenuEntry, fallen: str, qty: int
) -> list[SceneAct]:
    if entry.item is None:
        return [LootIntent(actor_id, fallen, None, gold=qty)]
    hero = state.creatures.get(fallen)
    pc = hero.pc if hero is not None else None
    keeps = same_keepsakes(pc.keepsakes, entry.item) if pc is not None else []
    if keeps:
        return [LootIntent(actor_id, fallen, k) for k in keeps[:qty]]
    return [LootIntent(actor_id, fallen, entry.item, qty=qty)]


def _take(state: GameState, actor_id: str, entry: MenuEntry, qty: int) -> list[SceneAct]:
    acts: list[SceneAct] = []
    left = qty
    for item in same_lying(state, entry.item or ""):
        if left < 1:
            break
        units = min(left, item.qty)
        acts.append(TakeIntent(actor_id, item.id, None if units >= item.qty else units))
        left -= units
    return acts or [RefusedIntent(actor_id, GONE)]


def _drop(actor_id: str, item: str, qty: int) -> SceneAct:
    drops = tuple(ItemIntent(actor_id, ItemAction.DROP, item) for _ in range(qty))
    return drops[0] if len(drops) == 1 else ItemIntents(drops)


def _offer(actor_id: str, entry: MenuEntry) -> SceneAct:
    if entry.kind is ActionKind.SURRENDER and entry.note:
        return RefusedIntent(actor_id, entry.note)  # every foe a kind that never yields
    if entry.skill is not None:
        return ParleyIntent(actor_id, Skill(entry.skill))
    return AnswerOffer(choice=OfferChoice(entry.option or OfferChoice.FIGHT.value))


def _trade(state: GameState, entry: MenuEntry, qty: int) -> SceneAct:
    keeper = state.world.shop_npc_id or ""
    count = min(qty, MAX_TRADE)
    if entry.kind is ActionKind.BUY:
        return ShopBuy(npc_id=keeper, item_id=entry.item or "", qty=count)
    return ShopSell(npc_id=keeper, item_id=entry.item or "", qty=count)


def _plain(actor_id: str, entry: MenuEntry, target: str | None, text: str) -> SceneAct:
    """The entries that need no state: one act from the entry's data keys."""
    match entry.kind:
        case ActionKind.TALK:
            return AskIntent(actor_id, target or "", said=text)
        case ActionKind.LOOK:
            return LookAroundIntent(actor_id)
        case ActionKind.SEARCH:
            return SearchIntent(actor_id, Skill(entry.skill or Skill.PERCEPTION.value))
        case ActionKind.REST:
            return RestIntent(RestKind(entry.option or RestKind.SHORT.value))
        case ActionKind.SHOP:
            return ShopIntent(target or "")

        case ActionKind.EQUIP:
            return ItemIntent(actor_id, ItemAction.EQUIP, entry.item or "")
        case ActionKind.UNEQUIP:
            return ItemIntent(actor_id, ItemAction.UNEQUIP, entry.item or "")
        case ActionKind.ITEM:
            target_id = target or actor_id
            owner = target_id if entry.option == FEED_OPTION else actor_id
            return HealIntent(actor_id, (target_id,), item=entry.item, owner_id=owner)
        case ActionKind.GEAR:
            return UseIntent(actor_id, entry.item or "", target, use_id=entry.use_id)
        case ActionKind.COPY_SCROLL:
            return CopyScroll(item_id=entry.item or "")
        case ActionKind.QUEST:
            return QuestAnswerIntent(actor_id, entry.quest_id or "", entry.option == "accept")
        case ActionKind.HELP_UP:
            return HelpUpIntent(actor_id, target or "")
        case ActionKind.FEATURE:
            return FeatureUseIntent(actor_id, entry.feature_id or "")
        case ActionKind.OFFER | ActionKind.SURRENDER:
            return _offer(actor_id, entry)
        case _:
            return OtherIntent(actor_id, text)


def _counted(
    state: GameState, actor_id: str, entry: MenuEntry, target: str, qty: int
) -> list[SceneAct] | None:
    """The entries whose count matters, or None for the others."""
    match entry.kind:
        case ActionKind.GIVE:
            return [_give(state, actor_id, entry, target, qty)]
        case ActionKind.HAND:
            return _hand(state, actor_id, entry, target, qty)
        case ActionKind.PAY:
            return [PayIntent(actor_id, target, qty)]
        case ActionKind.TAKE if entry.id.startswith("loot:"):
            return _loot(state, actor_id, entry, target, qty)
        case ActionKind.TAKE:
            return _take(state, actor_id, entry, qty)
        case ActionKind.DROP:
            return [_drop(actor_id, entry.item or "", qty)]
        case ActionKind.BUY | ActionKind.SELL:
            return [_trade(state, entry, qty)]
        case _:
            return None


def _holder(state: GameState, person: str, keepsake: str) -> str:
    """The record of a shown person that holds the keepsake (a hidden boss twin may, M36.8c)."""
    npc = state.world.npcs.get(person)
    if npc is not None and any(k.id == keepsake for k in npc.keepsakes):
        return person
    return twin_boss(state, person)


def _cast(actor_id: str, entry: MenuEntry, step: MenuStep) -> SceneAct:
    spell = entry.spell_id or ""
    if not entry.target_ids:
        return CastIntent(actor_id, spell, (), at_scene=True)
    targets = step.targets or (actor_id,)
    return CastIntent(actor_id, spell, targets[: max(1, entry.max_targets)])


def scene_step_acts(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep, text: str
) -> list[SceneAct]:
    free = free_acts(actor_id, entry)
    if free is not None:
        return free
    target = step.targets[0] if step.targets else None
    if target is None and len(entry.target_ids) == 1:
        target = entry.target_ids[0]
    needs = entry.max_targets > 0 and entry.kind not in (ActionKind.ITEM, ActionKind.CAST)
    if target is None and needs:
        return [RefusedIntent(actor_id, f"Say who or where for: {entry.label}.")]
    qty = max(1, min(step.qty, entry.qty_max))
    if entry.kind is ActionKind.TRAVEL:
        return [_travel(state, actor_id, target or "")]
    if entry.kind is ActionKind.UNLOCK:
        return [_unlock(state, actor_id, entry, target or "")]
    if entry.kind is ActionKind.CAST:
        return [_cast(actor_id, entry, step)]
    if entry.kind is ActionKind.LIFT:
        return [
            LiftIntent(actor_id, _holder(state, target or "", entry.item or ""), entry.item or "")
        ]
    counted = _counted(state, actor_id, entry, target or "", qty)
    return counted if counted is not None else [_plain(actor_id, entry, target, text)]
