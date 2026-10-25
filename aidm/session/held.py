"""The storyteller's turn and the acts held for their player (split out of `session.explore` in
M31.1a; SPEC 6.1, M15.1, M22.1).

- `adjudicated(core, entry, creative=..., prior=...)`: the adjudicator with `apply` wired to THE
  reducer, then `telling.conclude`; a point-of-no-return result is held (`_hold`): the narrator
  never tells it as done (one engine hold line), and only the acting player is asked
  (`pending_confirmation`). A fight opened with a weapon attack rolls it first
  (`opening.strike_if_opening`, M19.2).
- `hold_parley(core, player, actor_id, skill)` (M31.1a V4): a typed line that would answer the
  waiting encounter offer as a parley asks first, with the same confirm/cancel card
  (`PARLEY_ASK`): one roll, and a failure starts the fight.
- `strike_person(core, entry, intent)` (M36.8c): the menu's attack on a person here out of a
  fight, by the engine's own path: `start_encounter` against them with the opening strike
  (`StartEncounterArgs.opening_strike_on`); a non-hostile person is held at the point of no return
  exactly like the storyteller's call (`_hold`), a hostile one is fought at once.
- `confirm_hostile` re-runs the held call with `confirm_hostile=True` (no second model call) or
  answers the offer as the held parley; `cancel_hostile` drops it with one line. M32.1a X4: a
  confirm or cancel from another seat changes nothing and names whose card it is (`NOT_YOURS`).

Public API: `adjudicated`, `hold_parley`, `strike_person`, `confirm_hostile`, `cancel_hostile`,
`HOLD`, `STAY_HAND`, `PARLEY_ASK`, `PARLEY_STAY`, `NOTHING_WAITS`, `NOT_YOURS`, `NO_FIGHT`.
"""

from collections.abc import Sequence

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import StartEncounterArgs
from aidm.models.abilities import Skill
from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import AnswerOffer
from aidm.models.protocol_server import ErrorCode, NoticeKind, PendingConfirmationMsg
from aidm.models.protocol_views import QueueEntry
from aidm.rules.acts import PersonStrikeIntent
from aidm.rules.progression import node_plan
from aidm.session import combat_flow, party_actions
from aidm.session.opening import strike_if_opening
from aidm.session.quest_people import CROSS_STAY, hold
from aidm.session.table_core import Player, TableCore
from aidm.session.table_records import PendingHostile
from aidm.session.telling import conclude, remember, tell_text

HOLD = "{name} stands on the brink of violence. {why}"  # M29.5c G11: the reason, too
STAY_HAND = "You stay your hand, and the moment passes without bloodshed."
PARLEY_ASK = (
    "This answers the fight offer as a parley: one roll, a failure starts the fight. Confirm?"
)
PARLEY_STAY = "You hold your words for now; the standoff still waits."
NOTHING_WAITS = "Nothing is waiting for your confirmation."
NOT_YOURS = "Nothing is waiting for your confirmation: the card waits for {name}'s player."
NO_FIGHT = "{name} cannot be attacked here now."
MAX_TERRAIN = 3


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
    if call.name != "move_party":  # M23.4: a crossing only asks, nothing violent is held
        actor = core.state.creatures.get(entry.creature_id)
        name = actor.name if actor is not None else "The hero"
        await tell_text(core, HOLD.format(name=name, why=prompt).strip())
    hold(core, entry.player_id, entry.creature_id, call, prompt)


async def strike_person(core: TableCore, entry: QueueEntry, intent: PersonStrikeIntent) -> None:
    state = core.state
    node = node_plan(state, state.world.current_node)
    terrain = list(node.terrain_tags)[:MAX_TERRAIN] if node is not None else []
    args = StartEncounterArgs(
        against_npcs=[intent.npc_id],
        terrain_tags=terrain,
        opening_strike_on=intent.npc_id,
        opening_attack=intent.attack,
    )
    call = ToolCall("session-start_encounter", "start_encounter", args)
    result = execute_tool(state, call, ToolContext(actor_id=intent.actor_id), core.rng, core.regs)
    if result.pending is not None:
        await _hold(core, entry, call, result.pending.prompt)
        return
    if not result.ok:
        npc = state.world.npcs.get(intent.npc_id)
        name = npc.name if npc is not None else "They"
        core.notice(entry.player_id, NoticeKind.REFUSED, NO_FIGHT.format(name=name))
        return
    events = core.apply_all(list(result.events))
    events += strike_if_opening(core, call, intent.actor_id, events)
    events = await conclude(core, None, events, actor_id=intent.actor_id, player_text=entry.text)
    await combat_flow.after_resolution(core, events)


def hold_parley(core: TableCore, player: Player, actor_id: str, skill: Skill) -> None:
    offer = AnswerOffer(choice=OfferChoice.PARLEY, skill=skill)
    core.pending = PendingHostile(player.id, actor_id, None, PARLEY_ASK, offer)
    core.send(player.id, PendingConfirmationMsg(player_id=player.id, prompt=PARLEY_ASK))


def _taken(core: TableCore, player: Player) -> PendingHostile | None:
    pending = core.pending
    if pending is None or pending.player_id != player.id:
        core.error(player.id, ErrorCode.REFUSED, _nothing_waits(core, pending))
        return None
    core.pending = None
    return pending


def _nothing_waits(core: TableCore, pending: PendingHostile | None) -> str:
    """M32.1a X4: a card held for another seat is named, so its own player can answer it."""
    hero = core.state.creatures.get(pending.actor_id) if pending is not None else None
    return NOT_YOURS.format(name=hero.name) if hero is not None else NOTHING_WAITS


async def confirm_hostile(core: TableCore, player: Player) -> None:
    pending = _taken(core, player)
    if pending is None:
        return
    if pending.offer is not None:  # M31.1a V4: the held parley answers the offer now
        await party_actions.answer(core, player, pending.offer)
        return
    if pending.call is None:
        return
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
    pending = _taken(core, player)
    if pending is None:
        return
    if pending.offer is not None:
        core.notice(player.id, NoticeKind.INFO, PARLEY_STAY)
        return
    crossing = pending.call is not None and pending.call.name == "move_party"
    await remember(core, await tell_text(core, CROSS_STAY if crossing else STAY_HAND))
