"""Deterministic party and hero actions of the table actor (no adjudicator call).

Vote jobs (run once a ready vote passes): `travel_job` (the `move_party` DM tool, then the
M5.4 arrival order through `telling.conclude`), `rest_job` (`rules.rests`), `shop_job` (the
`open_shop` tool, then `shop_stock` to everyone). Hero jobs: `answer` (the pending encounter
offer, first answer wins), `buy`/`sell` (`rules.shop`), `give` (`rules.social_deeds.gift_events`
+ region rewards), `level` (`rules.leveling.level_up`), `equip`/`unequip`/`drop` and the equip/drop
pre-check intents (`rules.equipment`). Refusals are typed and player-safe; nothing is spent on a
refusal.

Public API: `travel_job`, `rest_job`, `shop_job`, `item_intent`, `answer`, `buy`, `sell`, `give`,
`level`, `equip`, `unequip`, `drop`, `send_stock`.
"""

from aidm.dm.arrival import offer_data
from aidm.dm.llm_types import ToolCall
from aidm.dm.precheck import ItemAction, ItemIntent, RestKind
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import dm_tool
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import (
    AnswerOffer,
    Drop,
    Equip,
    Give,
    LevelUp,
    ShopBuy,
    ShopSell,
    Unequip,
)
from aidm.models.protocol_server import ErrorCode, NoticeKind, ShopStock
from aidm.models.state import Creature
from aidm.rules.equipment import EquipRefused, drop_events, equip_events, unequip_events
from aidm.rules.leveling import LevelUpInvalid, can_level_up, level_up
from aidm.rules.offer_answer import OfferRefused, answer_offer
from aidm.rules.quest_rewards import resolution_reward_events
from aidm.rules.rests import RestRefused, long_rest, short_rest
from aidm.rules.shop import ShopRefused, buy_events, npc_shop_stock, sell_events
from aidm.rules.social_deeds import GiftRefused, gift_events
from aidm.session import combat_flow
from aidm.session.table_core import Job, Player, TableCore
from aidm.session.telling import conclude
from aidm.session.views import stock_lines

REST_REFUSED = "The party cannot rest right now: the supplies or the hour do not allow it."


def _tool(name: str, **args: str) -> ToolCall:
    return ToolCall(f"session-{name}", name, dm_tool(name).args_model.model_validate(args))


def travel_job(core: TableCore, actor_id: str, node_id: str) -> Job:
    async def job() -> None:
        call = _tool("move_party", node_id=node_id)
        result = execute_tool(core.state, call, ToolContext(actor_id), core.rng, core.regs)
        if not result.ok:
            core.notice(None, NoticeKind.REFUSED, "The way there is closed for now.")
            return
        core.pending = None
        events = core.apply_all(list(result.events))
        await combat_flow.after_resolution(core, await conclude(core, None, events))

    return job


def rest_job(core: TableCore, kind: RestKind) -> Job:
    async def job() -> None:
        try:
            events = short_rest(core.state) if kind is RestKind.SHORT else long_rest(core.state)
        except RestRefused:
            core.notice(None, NoticeKind.REFUSED, REST_REFUSED)
            return
        await conclude(core, None, core.apply_all(events))

    return job


def send_stock(core: TableCore, npc_id: str, player_id: str | None = None) -> None:
    regs = core.regs
    try:
        stock = npc_shop_stock(core.state, npc_id, regs.catalogue, regs.shops)
    except ShopRefused:
        return
    npc = core.state.world.npcs[npc_id]
    msg = ShopStock(npc_id=npc_id, npc_name=npc.name, stock=stock_lines(stock, regs.catalogue))
    if player_id is None:
        core.broadcast(msg)
    else:
        core.send(player_id, msg)


def shop_job(core: TableCore, actor_id: str, npc_id: str) -> Job:
    async def job() -> None:
        call = _tool("open_shop", npc=npc_id)
        result = execute_tool(core.state, call, ToolContext(actor_id), core.rng, core.regs)
        if not result.ok:
            core.notice(None, NoticeKind.REFUSED, "The shop stays shut to you.")
            return
        await conclude(core, None, core.apply_all(list(result.events)))
        send_stock(core, npc_id)

    return job


def _hero(core: TableCore, player: Player) -> Creature | None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
    return pc


async def answer(core: TableCore, player: Player, msg: AnswerOffer) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    data = offer_data(core.regs)
    try:
        events = answer_offer(
            core.state, msg.choice, data, core.rng, actor_id=pc.id, skill=msg.skill
        )
    except OfferRefused:
        core.error(player.id, ErrorCode.REFUSED, "There is nothing to answer right now.")
        return
    core.apply_all(events)
    every = await conclude(core, None, events, actor_id=pc.id)
    await combat_flow.after_resolution(core, every)


def _trade(core: TableCore, player: Player, events: list[AnyEvent], text: str) -> None:
    core.apply_all(events)
    core.notice(player.id, NoticeKind.INFO, text)


async def buy(core: TableCore, player: Player, msg: ShopBuy) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    regs = core.regs
    try:
        events = buy_events(
            core.state, pc.id, msg.npc_id, msg.item_id, msg.qty, regs.catalogue, regs.shops
        )
    except ShopRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, f"No sale: {refused.detail or refused.reason}.")
        return
    _trade(core, player, events, f"Bought {msg.qty} x {msg.item_id.replace('-', ' ')}.")


async def sell(core: TableCore, player: Player, msg: ShopSell) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    regs = core.regs
    try:
        events = sell_events(
            core.state, pc.id, msg.npc_id, msg.item_id, msg.qty, regs.catalogue, regs.shops
        )
    except ShopRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, f"No sale: {refused.detail or refused.reason}.")
        return
    _trade(core, player, events, f"Sold {msg.qty} x {msg.item_id.replace('-', ' ')}.")


async def give(core: TableCore, player: Player, msg: Give) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    try:
        events = gift_events(core.state, pc.id, msg.npc_id, msg.item_id, core.regs.tiers)
    except GiftRefused:
        core.error(player.id, ErrorCode.REFUSED, "That gift cannot be given here.")
        return
    core.apply_all(events)
    regs = core.regs
    rewards = resolution_reward_events(core.state, regs.tiers, regs.catalogue)
    await conclude(core, None, [*events, *core.apply_all(rewards)], actor_id=pc.id)


async def level(core: TableCore, player: Player, msg: LevelUp) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    if not can_level_up(pc):
        core.error(player.id, ErrorCode.REFUSED, "Your hero is not ready to level up yet.")
        return
    try:
        events = level_up(pc, msg.choices, core.regs.combat.chars)
    except LevelUpInvalid as invalid:
        text = "; ".join(e.detail for e in invalid.errors) or "Those choices do not fit."
        core.error(player.id, ErrorCode.INVALID, text)
        return
    core.apply_all(events)
    core.notice(None, NoticeKind.INFO, f"{pc.name} grows stronger.")


def _gear(core: TableCore, player: Player, events: list[AnyEvent], text: str) -> None:
    core.apply_all(events)
    core.notice(player.id, NoticeKind.INFO, text)


async def equip(core: TableCore, player: Player, msg: Equip) -> None:
    pc = _hero(core, player)
    if pc is not None:
        await _item(core, player, pc, ItemAction.EQUIP, msg.item_id)


async def unequip(core: TableCore, player: Player, msg: Unequip) -> None:
    pc = _hero(core, player)
    if pc is not None:
        await _item(core, player, pc, ItemAction.UNEQUIP, msg.item_id)


async def drop(core: TableCore, player: Player, msg: Drop) -> None:
    pc = _hero(core, player)
    if pc is not None:
        await _item(core, player, pc, ItemAction.DROP, msg.item_id)


async def item_intent(core: TableCore, player: Player, intent: ItemIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    if pc is not None:
        await _item(core, player, pc, intent.action, intent.item)


async def _item(
    core: TableCore, player: Player, pc: Creature, action: ItemAction, item: str
) -> None:
    if core.combat_active():
        core.error(player.id, ErrorCode.WRONG_PHASE, "Gear changes wait until the fight ends.")
        return
    chars = core.regs.combat.chars
    name = item.replace("-", " ")
    try:
        if action is ItemAction.EQUIP:
            _gear(core, player, equip_events(pc, item, chars), f"{pc.name} readies the {name}.")
        elif action is ItemAction.UNEQUIP:
            _gear(core, player, unequip_events(pc, item, chars), f"{pc.name} stows the {name}.")
        else:
            events = drop_events(core.state, pc, item, chars)
            _gear(core, player, events, f"{pc.name} sets down the {name}.")
    except EquipRefused as refused:
        core.error(
            player.id, ErrorCode.REFUSED, refused.detail.capitalize() + ".", refused.reason.value
        )
