"""The exploration action queue and the free-text turn pipeline (SPEC 6.1, 6.2, 10).

Queue: FIFO, any seated player with a living hero may submit; at most ONE waiting entry per
player (the one being resolved does not count); everyone gets `queue_state` on every change;
one entry resolves at a time, never while paused, fighting or voting is irrelevant (a vote does
not block the queue). Combat free text from the active hero is a `creative_action`.

Resolution of one entry (`resolve_action`): the deterministic pre-checks first (look around ->
the manifest text; travel / short rest / long rest / shop -> a ready vote; inventory -> a
private listing; equip / unequip / drop -> `party_actions.item_intent`), else the adjudicator
with `apply` wired to THE reducer (dice and mechanical events are broadcast as they apply),
then `telling.conclude` (arrival, rewards, narration, NPC voice, memory, epilogue) and the
fight check. A point-of-no-return result stores `PendingHostile` and asks only the acting
player (`pending_confirmation`); `confirm_hostile` re-runs the stored call with
`confirm_hostile=True` (no second model call), `cancel_hostile` drops it. Every entry ends in
narration or a typed notice: never silent.

Public API: `submit_action`, `kick_resolver`, `resolve_next`, `resolve_action`,
`adjudicated`, `confirm_hostile`, `cancel_hostile`, `inventory_text`.
"""

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.precheck import (
    InventoryIntent,
    ItemIntent,
    LookIntent,
    RestIntent,
    RestKind,
    ShopIntent,
    TravelIntent,
    precheck,
)
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import (
    ErrorCode,
    NoticeKind,
    PendingConfirmationMsg,
    Resolving,
)
from aidm.models.protocol_views import QueueEntry, TablePhase, VoteKind
from aidm.models.state import Creature
from aidm.rules.scene import node_display_name
from aidm.rules.turns import EconomyRefused, spend_action
from aidm.session import combat_flow, party_actions, votes
from aidm.session.table_core import Job, PendingHostile, Player, TableCore
from aidm.session.telling import conclude, remember, tell_text

STAY_HAND = "You stay your hand, and the moment passes without bloodshed."
ACTION_SPENT = (
    "You have already used your action this turn. Move, use a bonus action or end your turn."
)


def submit_action(core: TableCore, player: Player, msg: SubmitAction) -> None:
    if core.phase is not TablePhase.PLAY:
        ended = core.phase is TablePhase.ENDED
        text = "This tale has ended." if ended else "The adventure has not started yet."
        core.error(player.id, ErrorCode.WRONG_PHASE, text)
        return
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero to act.")
        return
    if pc.hp <= 0:  # M11.1: a downed hero cannot act (v1: the unconscious hero kept typing)
        core.error(player.id, ErrorCode.NO_CHARACTER, "You are unconscious and cannot act.")
        return
    if core.combat_active():
        _combat_text(core, player, pc, msg.text)
        return
    if any(e.player_id == player.id for e in core.queue):
        core.error(player.id, ErrorCode.ALREADY_QUEUED, "Your next action is already waiting.")
        return
    core.queue.append(QueueEntry(player_id=player.id, creature_id=pc.id, text=msg.text))
    core.broadcast_queue()
    kick_resolver(core)


def _combat_text(core: TableCore, player: Player, pc: Creature, text: str) -> None:
    enc = core.state.encounter
    if enc is None or enc.active_id() != pc.id or core.turn_key is None:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
        return
    if not _action_left(core, pc.id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    entry = QueueEntry(player_id=player.id, creature_id=pc.id, text=text)

    async def job() -> None:
        now = core.state.encounter
        if now is None or now.active_id() != pc.id or core.turn_key is None:
            core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
            return
        if not _action_left(core, pc.id):
            core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
            return
        await combat_flow.tell_segment(core)
        result = await adjudicated(core, entry, creative=True)
        if result.executed:
            _spend_action(core, pc.id)
        core.segment = []
        await combat_flow.after_player_step(core, pc.id)

    core.schedule(job)


def _action_left(core: TableCore, creature_id: str) -> bool:
    """A creative action costs the hero's action (SPEC 6.1; DECISIONS M9.5 QA-01)."""
    enc = core.state.encounter
    combatant = enc.combatants.get(creature_id) if enc is not None else None
    return combatant is not None and combatant.economy.action


def _spend_action(core: TableCore, creature_id: str) -> None:
    try:
        core.apply_all(spend_action(core.state, creature_id, reason="creative action"))
    except EconomyRefused:
        return  # the effect ended the fight or the hero's turn: nothing left to spend


def kick_resolver(core: TableCore) -> None:
    idle = core.resolving is None and not core.resolver_scheduled
    ready = core.phase is TablePhase.PLAY and not core.paused and not core.in_combat
    if idle and ready and core.queue:
        core.resolver_scheduled = True
        core.schedule(lambda: resolve_next(core))


async def resolve_next(core: TableCore) -> None:
    core.resolver_scheduled = False
    if not core.queue or core.paused or core.in_combat:
        return
    entry = core.queue.popleft()
    core.resolving = entry
    core.broadcast(Resolving(entry=entry))
    core.broadcast_queue()
    try:
        await resolve_action(core, entry)
    finally:
        core.resolving = None
        core.broadcast_queue()


async def resolve_action(core: TableCore, entry: QueueEntry) -> None:
    player = core.players.get(entry.player_id)
    actor = core.state.creatures.get(entry.creature_id)
    if player is None or actor is None or actor.dead:
        core.notice(entry.player_id, NoticeKind.REFUSED, "Your hero can no longer act.")
        return
    intent = precheck(core.state, entry.creature_id, entry.text)
    if intent is None:
        await adjudicated(core, entry)
    elif isinstance(intent, LookIntent):
        await remember(core, await tell_text(core, intent.text))
    elif isinstance(intent, InventoryIntent):
        core.notice(player.id, NoticeKind.INFO, inventory_text(actor))
    elif isinstance(intent, ItemIntent):
        await party_actions.item_intent(core, player, intent)
    elif isinstance(intent, TravelIntent):
        detail = f"travel to {node_display_name(core.state, intent.node_id)}"
        job = party_actions.travel_job(core, entry.creature_id, intent.node_id)
        _propose(core, player, VoteKind.TRAVEL, detail, job)
    elif isinstance(intent, RestIntent):
        short = intent.kind is RestKind.SHORT
        kind = VoteKind.SHORT_REST if short else VoteKind.LONG_REST
        detail = "take a short rest" if short else "make camp for a long rest"
        _propose(core, player, kind, detail, party_actions.rest_job(core, intent.kind))
    else:
        _shop_intent(core, player, entry, intent)


def _shop_intent(core: TableCore, player: Player, entry: QueueEntry, intent: ShopIntent) -> None:
    npc = core.state.world.npcs[intent.npc_id]
    job = party_actions.shop_job(core, entry.creature_id, intent.npc_id)
    _propose(core, player, VoteKind.SHOP, f"trade with {npc.name}", job)


def _propose(core: TableCore, player: Player, kind: VoteKind, detail: str, job: Job) -> None:
    if votes.open_vote(core, kind, detail, player, job):
        core.notice(None, NoticeKind.INFO, f"{player.name} proposes to {detail}.")


async def adjudicated(
    core: TableCore, entry: QueueEntry, *, creative: bool = False
) -> AdjudicationResult:
    result = await adjudicate(
        core.state,
        entry.creature_id,
        entry.text,
        core.llm,
        AdjudicationOptions(creative_action=creative),
        core.rng,
        core.regs,
        core.apply,
    )
    if result.pending is not None and result.pending_call is not None:
        core.pending = PendingHostile(
            entry.player_id, entry.creature_id, result.pending_call, result.pending.prompt
        )
        msg = PendingConfirmationMsg(player_id=entry.player_id, prompt=result.pending.prompt)
        core.send(entry.player_id, msg)
    events = await conclude(
        core,
        result,
        list(result.events),
        actor_id=entry.creature_id,
        player_text=entry.text,
    )
    if not creative:
        await combat_flow.after_resolution(core, events)
    return result


async def confirm_hostile(core: TableCore, player: Player) -> None:
    pending = core.pending
    if pending is None or pending.player_id != player.id:
        core.error(player.id, ErrorCode.REFUSED, "Nothing is waiting for your confirmation.")
        return
    core.pending = None
    ctx = ToolContext(actor_id=pending.actor_id, confirm_hostile=True)
    result = execute_tool(core.state, pending.call, ctx, core.rng, core.regs)
    if not result.ok:
        core.notice(player.id, NoticeKind.REFUSED, "The moment has passed.")
        return
    events = core.apply_all(list(result.events))
    events = await conclude(core, None, events, actor_id=pending.actor_id)
    await combat_flow.after_resolution(core, events)


async def cancel_hostile(core: TableCore, player: Player) -> None:
    pending = core.pending
    if pending is None or pending.player_id != player.id:
        core.error(player.id, ErrorCode.REFUSED, "Nothing is waiting for your confirmation.")
        return
    core.pending = None
    await remember(core, await tell_text(core, STAY_HAND))


def inventory_text(creature: Creature) -> str:
    pc = creature.pc
    if pc is None or not pc.inventory:
        return f"{creature.name} carries nothing of note."
    items = ", ".join(
        f"{row.item.replace('-', ' ')} x{row.qty}" if row.qty > 1 else row.item.replace("-", " ")
        for row in pc.inventory
    )
    return f"{creature.name} carries: {items}. Gold: {pc.gold}."
