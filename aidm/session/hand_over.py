"""Picking things up and handing them over at the table (M19.3 take, M23.3 give).

- `take_intent`: a typed pick-up of a visible item here (`rules.equipment.take_events`; a quest
  item becomes a keepsake with its `quest_id`), then `telling.follow_ups` (so an `obtain` step
  moves at once) and one short engine line, followed by the template lines of what moved.
- `give` (the `give` client command) and `give_intent` (typed "give X to Y") share ONE path:
  `rules.handing.give_events` (a keepsake -> `KeepsakeGiven`; an inventory item -> the
  existing gift with its deed), then `telling.conclude` (follow-ups settle the quests, the
  narrator tells the hand-over). Refusals are typed and player-safe; nothing moves on one.

- `hand` (the `hand_over` client command) and `hand_intent` (typed "hand the crowbar to Elowen",
  M29.7a R8) share ONE path to another hero: `rules.hero_handing.hand_events`, then the engine
  line of the hand-over is told (no model call); a refusal is the rules' plain reason.

Public API: `take_intent`, `give`, `give_intent`, `hand`, `hand_intent`.
"""

from aidm.dm.event_text import event_line
from aidm.dm.give_intent import GiveIntent
from aidm.dm.hand_intent import HeroHandIntent
from aidm.dm.narration_templates import template_line
from aidm.dm.precheck import TakeIntent
from aidm.models.item_events import HandedOver
from aidm.models.protocol_client import Give, HandOver
from aidm.models.protocol_server import ErrorCode
from aidm.models.state import Creature
from aidm.rules.equipment import EquipRefused, take_events
from aidm.rules.handing import GiveRefused, give_events
from aidm.rules.hero_handing import HandRefused, hand_events
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude, follow_ups, remember, tell_text


async def take_intent(core: TableCore, player: Player, intent: TakeIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    item = core.state.world.items.get(intent.item_id)
    if pc is None or item is None:
        return
    try:
        events = take_events(core.state, pc, intent.item_id)
    except EquipRefused as refused:
        detail = refused.detail.capitalize() + "."
        core.error(player.id, ErrorCode.REFUSED, detail, refused.reason.value)
        return
    core.apply_all(events)
    moved = await follow_ups(core, events)
    name = item.name if item.catalog_id is None else item.name.lower()
    lines = [f"{pc.name} picks up the {name}."]
    lines += [line for e in moved if (line := template_line(core.state, e))]
    await remember(core, await tell_text(core, " ".join(lines)), [*events, *moved])


async def give(core: TableCore, player: Player, msg: Give) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    await _give(core, player, pc, msg.npc_id, msg.item_id)


async def give_intent(core: TableCore, player: Player, intent: GiveIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    if pc is not None:
        await _give(core, player, pc, intent.npc_id, intent.thing)


async def _give(core: TableCore, player: Player, pc: Creature, npc_id: str, thing: str) -> None:
    try:
        events = give_events(core.state, pc.id, npc_id, thing, core.regs.tiers)
    except GiveRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, refused.reason.value)
        return
    core.apply_all(events)
    await conclude(core, None, events, actor_id=pc.id)  # follow_ups settles regions and quests


async def hand(core: TableCore, player: Player, msg: HandOver) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    await _hand(core, player, HeroHandIntent(pc.id, msg.to_id, msg.item_id, msg.qty, msg.gold))


async def hand_intent(core: TableCore, player: Player, intent: HeroHandIntent) -> None:
    await _hand(core, player, intent)


async def _hand(core: TableCore, player: Player, intent: HeroHandIntent) -> None:
    try:
        events = hand_events(
            core.state,
            intent.actor_id,
            intent.to_id,
            core.regs.combat.chars,
            thing=intent.thing,
            qty=intent.qty,
            gold=intent.gold,
        )
    except HandRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, "hand_refused")
        return
    applied = core.apply_all(events)
    lines = [
        line for e in applied if isinstance(e, HandedOver) and (line := event_line(core.state, e))
    ]
    await remember(core, await tell_text(core, " ".join(lines)), applied)
