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
fight check. M22.1: the player's words are declared to the table first (`declared.declare`;
not for the private inventory listing), also for a creative action or a typed move in a fight.
A point-of-no-return result stores `PendingHostile` and asks only the acting player
(`pending_confirmation`); `confirm_hostile` re-runs the stored call with
`confirm_hostile=True` (no second model call), `cancel_hostile` drops it. A crossing that
leaves open tasks behind (M23.4, `move_party`) asks the same way, without the hold line. A
fight started by a weapon attack on an NPC rolls that attack before the narration
(`opening.strike_if_opening`, M19.2). Every entry ends in narration or a typed notice: never silent.
M23.8: a typed "what now" is answered before the queue (`what_now.answer`, not a turn), and a typed
move to a locked exit is told why it is shut (`BarredIntent`, `rules.gateway_lock`).
M27.5: typed gear use (`UseIntent`) runs through `gear_actions` (a refused use goes on to the
adjudicator); in a fight a typed put-out or light is `gear_actions.fight_gear`. M29.5b: a typed
feature or heal in a fight is the hotbar's command (`dm.fight_intent`). M30.0b: typed lines in
and out of a fight go through the one router (`dm.intent_router`).

Public API: `submit_action`, `kick_resolver`, `resolve_next`, `resolve_action`,
`adjudicated`, `confirm_hostile`, `cancel_hostile`, `inventory_text`.
"""

from collections.abc import Sequence

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.equip_intent import ItemIntent
from aidm.dm.fight_intent import FightCommand
from aidm.dm.give_intent import GiveIntent
from aidm.dm.hand_intent import HeroHandIntent
from aidm.dm.heal_intent import HealIntent
from aidm.dm.help_intent import HelpUpIntent
from aidm.dm.intent_router import fight_intent
from aidm.dm.lift_intent import LiftIntent
from aidm.dm.llm_types import ToolCall
from aidm.dm.parley_intent import ParleyIntent
from aidm.dm.pay_intent import PayIntent
from aidm.dm.precheck import (
    BarredIntent,
    InventoryIntent,
    LookIntent,
    RestIntent,
    RestKind,
    ShopIntent,
    TakeIntent,
    TravelIntent,
    asks_what_now,
    precheck,
)
from aidm.dm.surrender_intent import SurrenderIntent
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.dm.use_intent import UseIntent
from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import AnswerOffer, SubmitAction
from aidm.models.protocol_server import (
    ErrorCode,
    NoticeKind,
    Resolving,
)
from aidm.models.protocol_views import QueueEntry, TablePhase, VoteKind
from aidm.models.state import Creature
from aidm.rules.scene import node_display_name
from aidm.rules.turns import EconomyRefused, spend_action
from aidm.session import (
    combat_flow,
    gear_actions,
    hand_over,
    heal_actions,
    party_actions,
    votes,
    what_now,
)
from aidm.session.declared import declare
from aidm.session.opening import strike_if_opening
from aidm.session.quest_people import CROSS_STAY, hold
from aidm.session.surrender_turn import ACTION_SPENT, surrender_turn
from aidm.session.table_core import Job, Player, TableCore
from aidm.session.telling import conclude, remember, tell_text

HOLD = "{name} stands on the brink of violence. {why}"  # M29.5c G11: the reason, too
STAY_HAND = "You stay your hand, and the moment passes without bloodshed."


def submit_action(core: TableCore, player: Player, msg: SubmitAction) -> None:
    if core.phase is not TablePhase.PLAY:
        ended = core.phase is TablePhase.ENDED
        text = "This tale has ended." if ended else "The adventure has not started yet."
        core.error(player.id, ErrorCode.WRONG_PHASE, text)
        return
    pc = core.living_pc(player)
    if asks_what_now(core.state, pc.id if pc is not None else "", msg.text):
        what_now.answer(core, player)  # M23.8: not a turn, also in a fight
        return
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero to act.")
        return
    if pc.hp <= 0:  # M11.1: a downed hero cannot act (v1: the unconscious hero kept typing)
        core.error(player.id, ErrorCode.NO_CHARACTER, "You are unconscious and cannot act.")
        return
    if core.pending is not None and core.pending.player_id == player.id:
        core.pending = None  # a new action answers the open "Are you sure?" with no (M15.1)
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
    entry = QueueEntry(player_id=player.id, creature_id=pc.id, text=text)
    if gear_actions.fight_gear(core, player, entry):  # M27.5: put out (free) or light (bonus)
        return
    enc = core.state.encounter
    if enc is None or enc.active_id() != pc.id or core.turn_key is None:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
        return
    found = fight_intent(core.state, pc.id, text)  # M30.0b: the one router's fight rows
    if isinstance(found, list):  # M19.4: "I move to the ravine" moves (no action spent)
        moves = found
        core.schedule(lambda: _typed_move(core, player, entry, moves))
        return
    if isinstance(found, SurrenderIntent):  # M29.9a T12: one engine check, not a story roll
        demand = found
        core.schedule(lambda: surrender_turn(core, player, entry, demand))
        return
    if found is not None:  # M29.5b: "I use Second Wind", "I drink my potion": the hotbar's way
        command = found
        core.schedule(lambda: _typed_command(core, player, entry, command))
        return
    if not _action_left(core, pc.id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return

    async def job() -> None:
        now = core.state.encounter
        if now is None or now.active_id() != pc.id or core.turn_key is None:
            core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
            return
        if not _action_left(core, pc.id):
            core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
            return
        await combat_flow.tell_segment(core)
        declare(core, entry)
        result = await adjudicated(core, entry, creative=True)
        if result.executed:
            _spend_action(core, pc.id)
        core.segment = []
        await combat_flow.after_player_step(core, pc.id)

    core.schedule(job)


async def _typed_command(
    core: TableCore, player: Player, entry: QueueEntry, command: FightCommand
) -> None:
    """A typed feature or heal runs as the hotbar command (a refusal says the rules' reason)."""
    declare(core, entry)
    await combat_flow.player_command(core, player, command)


async def _typed_move(
    core: TableCore, player: Player, entry: QueueEntry, moves: list[MoveCommand | DashCommand]
) -> None:
    """The commands the phone's Move list sends; a refusal is answered the same way."""
    creature_id = entry.creature_id
    declare(core, entry)
    for command in moves:
        await combat_flow.player_command(core, player, command)
    goal = next((m.zone_id for m in moves if isinstance(m, MoveCommand)), None)
    enc = core.state.encounter
    here = enc.combatants.get(creature_id) if enc is not None else None
    if enc is not None and here is not None and here.zone_id == goal:
        zone = next(z.name for z in enc.zone_map.zones if z.id == goal)
        core.notice(player.id, NoticeKind.INFO, f"You move to {zone}.")


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
    if not isinstance(intent, InventoryIntent):  # the listing is private: nothing to tell
        declare(core, entry)
    if intent is None:
        await adjudicated(core, entry)
    elif isinstance(intent, LookIntent | BarredIntent):
        await remember(core, await tell_text(core, intent.text))
    elif isinstance(intent, InventoryIntent):
        core.notice(player.id, NoticeKind.INFO, inventory_text(actor))
    elif isinstance(intent, ItemIntent):
        await party_actions.item_intent(core, player, intent)
    elif isinstance(intent, TakeIntent):
        await hand_over.take_intent(core, player, intent)
    elif isinstance(intent, HelpUpIntent):
        await party_actions.help_up_intent(core, player, intent)
    elif isinstance(intent, GiveIntent):
        await hand_over.give_intent(core, player, intent)
    elif isinstance(intent, HeroHandIntent):
        await hand_over.hand_intent(core, player, intent)
    elif isinstance(intent, PayIntent):
        await _pay(core, player, entry, intent)
    elif isinstance(intent, LiftIntent):
        await hand_over.lift_intent(core, player, intent)
    elif isinstance(intent, ParleyIntent):  # M29.7a R4: one roll answers the waiting offer
        await party_actions.answer(
            core, player, AnswerOffer(choice=OfferChoice.PARLEY, skill=intent.skill)
        )
    elif isinstance(intent, UseIntent):
        await _gear_use(core, player, entry, intent)
    elif isinstance(intent, HealIntent):
        await heal_actions.heal_intent(core, player, intent)
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


async def _pay(core: TableCore, player: Player, entry: QueueEntry, intent: PayIntent) -> None:
    """M29.9a T17: the coins move first; "pay Rutter and ask him about the girl" then asks."""
    paid = hand_over.pay_first(core, player, intent)
    if paid is None:
        return
    if intent.rest is None:
        await conclude(core, None, paid, actor_id=intent.actor_id)
        return
    await adjudicated(core, entry.model_copy(update={"text": intent.rest}), prior=paid)


async def _gear_use(core: TableCore, player: Player, entry: QueueEntry, intent: UseIntent) -> None:
    """A typed gear use; M29.7a R17: "light a candle, then look around" lights it (or says why
    not in an engine line) AND the other act goes to the adjudicator, told together."""
    if intent.rest is None:
        if not await gear_actions.use_intent(core, player, intent):
            await adjudicated(core, entry)
        return
    prior = await gear_actions.first_act(core, player, intent)
    await adjudicated(core, entry.model_copy(update={"text": intent.rest}), prior=prior)


def _shop_intent(core: TableCore, player: Player, entry: QueueEntry, intent: ShopIntent) -> None:
    npc = core.state.world.npcs[intent.npc_id]
    job = party_actions.shop_job(core, entry.creature_id, intent.npc_id)
    _propose(core, player, VoteKind.SHOP, f"trade with {npc.name}", job)


def _propose(core: TableCore, player: Player, kind: VoteKind, detail: str, job: Job) -> None:
    if votes.open_vote(core, kind, detail, player, job):
        core.notice(None, NoticeKind.INFO, f"{player.name} proposes to {detail}.")


async def adjudicated(
    core: TableCore,
    entry: QueueEntry,
    *,
    creative: bool = False,
    prior: Sequence[AnyEvent] = (),
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
        await _hold(core, entry, result.pending_call, result.pending.prompt)
        return result
    events = [*prior, *result.events]
    for done in result.executed:  # M19.2: a fight opened with a weapon attack rolls it now
        events += strike_if_opening(core, done.call, entry.creature_id, done.result.events)
    events = await conclude(
        core,
        result,
        events,
        actor_id=entry.creature_id,
        player_text=entry.text,
    )
    if not creative:
        await combat_flow.after_resolution(core, events)
    return result


async def _hold(core: TableCore, entry: QueueEntry, call: ToolCall, prompt: str) -> None:
    """A point-of-no-return act waits for its player (M15.1 playtest): the narrator never tells
    it as done (one engine hold line instead), and the question goes out AFTER that line."""
    if call.name != "move_party":  # M23.4: a crossing only asks, nothing violent is held
        actor = core.state.creatures.get(entry.creature_id)
        name = actor.name if actor is not None else "The hero"
        await tell_text(core, HOLD.format(name=name, why=prompt).strip())
    hold(core, entry.player_id, entry.creature_id, call, prompt)


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
    events += strike_if_opening(core, pending.call, pending.actor_id, events)
    events = await conclude(core, None, events, actor_id=pending.actor_id)
    await combat_flow.after_resolution(core, events)


async def cancel_hostile(core: TableCore, player: Player) -> None:
    pending = core.pending
    if pending is None or pending.player_id != player.id:
        core.error(player.id, ErrorCode.REFUSED, "Nothing is waiting for your confirmation.")
        return
    core.pending = None
    line = CROSS_STAY if pending.call.name == "move_party" else STAY_HAND
    await remember(core, await tell_text(core, line))


def inventory_text(creature: Creature) -> str:
    pc = creature.pc
    if pc is None or not pc.inventory:
        return f"{creature.name} carries nothing of note."
    items = ", ".join(
        f"{row.item.replace('-', ' ')} x{row.qty}" if row.qty > 1 else row.item.replace("-", " ")
        for row in pc.inventory
    )
    return f"{creature.name} carries: {items}. Gold: {pc.gold}."
