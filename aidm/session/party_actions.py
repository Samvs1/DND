"""Deterministic party and hero actions of the table actor (no adjudicator call).

Vote jobs (run once a ready vote passes): `travel_job` (the `move_party` DM tool, then the
M5.4 arrival order through `telling.conclude`; a crossing that leaves open tasks behind asks the
proposer first, `quest_people.hold`, M23.4), `rest_job` (`rules.rests`), `shop_job` (the
`open_shop` tool, then `shop_stock` to everyone). Hero jobs: `answer` (the pending encounter
offer, first answer wins), `buy`/`sell` (`rules.shop`), `level` (`rules.leveling.level_up`; not
in a fight, M20.4), `equip`/`unequip`/`drop` and the equip/drop pre-check intents
(`rules.equipment`), `use_item` (M7.5b: a potion outside a fight on the hero or another living hero,
`rules.items.use_item_events`; at full HP it is drunk for nothing, M27.7),
`copy_scroll` (M27.7: the Spellbook tab, a wizard copies a carried scroll into the spellbook out
of a fight, `rules.scrolls`; refusal codes `scroll_<reason>`),
`help_up` / `help_up_intent` (M20.2: outside a fight a standing hero helps a downed ally up to
1 HP, `rules.downed`; the button and the typed sentence). Picking up and giving live in
`aidm.session.hand_over` (M23.3).
Refusals are typed and player-safe; nothing is spent on a refusal.

Public API: `travel_job`, `rest_job`, `shop_job`, `item_intent`, `answer`, `buy`, `sell`,
`level`, `equip`, `unequip`, `drop`, `use_item`, `copy_scroll`, `help_up`, `help_up_intent`,
`send_stock`.
"""

from aidm.dm.arrival import offer_data
from aidm.dm.equip_intent import ItemAction, ItemIntent
from aidm.dm.help_intent import HelpUpIntent
from aidm.dm.llm_types import ToolCall
from aidm.dm.precheck import RestKind
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import dm_tool
from aidm.models.commands import RefusalCode
from aidm.models.events import AnyEvent, GoldChanged
from aidm.models.item_events import ItemUsed
from aidm.models.protocol_client import (
    AnswerOffer,
    CopyScroll,
    Drop,
    Equip,
    HelpUp,
    LevelUp,
    ShopBuy,
    ShopSell,
    Unequip,
    UseItem,
)
from aidm.models.protocol_server import ErrorCode, NoticeKind, ShopStock
from aidm.models.state import Creature, CreatureKind
from aidm.rules.command_checks import CommandRefused
from aidm.rules.downed import HelpUpRefused, help_up_events
from aidm.rules.equipment import (
    EquipRefused,
    drop_events,
    equip_events,
    unequip_events,
)
from aidm.rules.items import use_item_events
from aidm.rules.leveling import LevelUpInvalid, can_level_up, level_up
from aidm.rules.offer_answer import OfferRefused, answer_offer
from aidm.rules.rests import RestRefused, long_rest, rest_refused_text, short_rest
from aidm.rules.scrolls import ScrollCopyRefused, copy_scroll_to_spellbook, scroll_spell_index
from aidm.rules.shop import ShopRefused, buy_events, npc_shop_stock, sell_events
from aidm.session import combat_flow
from aidm.session.quest_people import hold
from aidm.session.table_core import Job, Player, TableCore
from aidm.session.telling import conclude, remember, tell_text
from aidm.session.views import stock_lines


def _tool(name: str, **args: str) -> ToolCall:
    return ToolCall(f"session-{name}", name, dm_tool(name).args_model.model_validate(args))


def travel_job(core: TableCore, actor_id: str, node_id: str) -> Job:
    async def job() -> None:
        call = _tool("move_party", node_id=node_id)
        result = execute_tool(core.state, call, ToolContext(actor_id), core.rng, core.regs)
        owner = core.owner_of(actor_id)
        if result.pending is not None and owner is not None:  # M23.4: leaving tasks behind
            hold(core, owner.id, actor_id, call, result.pending.prompt)
            return
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
            events = (
                short_rest(core.state, core.regs.combat.chars.features)
                if kind is RestKind.SHORT
                else long_rest(core.state)
            )
        except RestRefused as refused:
            core.notice(None, NoticeKind.REFUSED, rest_refused_text(refused))
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
        core.error(
            player.id,
            ErrorCode.REFUSED,
            f"No sale: {refused.detail or refused.reason}.",
            refusal=f"shop_{refused.reason.value}",
        )
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
        core.error(
            player.id,
            ErrorCode.REFUSED,
            f"No sale: {refused.detail or refused.reason}.",
            refusal=f"shop_{refused.reason.value}",
        )
        return
    _trade(core, player, events, f"Sold {msg.qty} x {msg.item_id.replace('-', ' ')}.")


async def level(core: TableCore, player: Player, msg: LevelUp) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    if core.combat_active():  # M20.4: as in the video game, levels are taken between fights
        core.error(player.id, ErrorCode.WRONG_PHASE, "Level up when the fight is over.")
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


async def use_item(core: TableCore, player: Player, msg: UseItem) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    if core.combat_active():
        core.error(player.id, ErrorCode.WRONG_PHASE, "In a fight, use items from the hotbar.")
        return
    target = core.state.creatures.get(msg.target_id or pc.id)
    if target is None or target.kind is not CreatureKind.PC:
        code = RefusalCode.UNKNOWN_TARGET.value
        core.error(player.id, ErrorCode.REFUSED, "No hero like that is here.", code)
        return
    regs, rng = core.regs.combat, core.rng
    try:
        events = use_item_events(rng, core.state, pc.id, msg.item_id, target.id, regs)
    except CommandRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.reason, refused.code.value)
        return
    name = msg.item_id.replace("-", " ")
    who = "" if target.id == pc.id else f" to {target.name}"
    wasted = any(isinstance(e, ItemUsed) and e.no_effect for e in events)  # M27.7: full health
    end = ": no special effect, it is gone." if wasted else "."
    _gear(core, player, events, f"{pc.name} uses the {name}{who}{end}")


async def copy_scroll(core: TableCore, player: Player, msg: CopyScroll) -> None:
    pc = _hero(core, player)
    if pc is None:
        return
    if core.combat_active():
        core.error(player.id, ErrorCode.WRONG_PHASE, "Copy scrolls when the fight is over.")
        return
    chars = core.regs.combat.chars
    try:
        events = copy_scroll_to_spellbook(pc, msg.item_id, chars)
    except ScrollCopyRefused as refused:
        code = f"scroll_{refused.reason.value}"
        core.error(player.id, ErrorCode.REFUSED, "That scroll cannot be copied.", code)
        return
    spell = chars.spells.find(scroll_spell_index(msg.item_id) or "")
    name = spell.name if spell is not None else msg.item_id
    gold = sum(-e.delta for e in events if isinstance(e, GoldChanged))
    _gear(core, player, events, f"{pc.name} copies {name} into the spellbook for {gold} gold.")


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


async def help_up(core: TableCore, player: Player, msg: HelpUp) -> None:
    pc = _hero(core, player)
    if pc is not None:
        await _help_up(core, player, pc, msg.target_id)


async def help_up_intent(core: TableCore, player: Player, intent: HelpUpIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    if pc is not None:
        await _help_up(core, player, pc, intent.target_id)


async def _help_up(core: TableCore, player: Player, pc: Creature, target_id: str) -> None:
    try:
        events = help_up_events(core.state, pc.id, target_id)
    except HelpUpRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, refused.reason.value)
        return
    core.apply_all(events)
    target = core.state.creatures[target_id]
    await remember(core, await tell_text(core, f"{pc.name} helps {target.name} up."))
