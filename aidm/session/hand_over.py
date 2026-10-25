"""Picking things up and handing them over at the table (M19.3 take, M23.3 give).

- `take_intent`: a typed pick-up of a visible item here (`rules.equipment.take_events`; a quest
  item becomes a keepsake with its `quest_id`), then `telling.follow_ups` (so an `obtain` step
  moves at once) and one short engine line, followed by the template lines of what moved.
- `give` (the `give` client command) and `give_intent` (typed "give X to Y") share ONE path:
  `rules.handing.give_events` (a keepsake -> `KeepsakeGiven`; an inventory item -> the
  existing gift with its deed), then `telling.conclude` (follow-ups settle the quests, the
  narrator tells the hand-over). Refusals are typed and player-safe; nothing moves on one.
  M32.1a X6: a counted typed give hands every keepsake of the count and says plainly when
  there were fewer (`ONLY`); M33.1: of a stacked item, that many units (one gift each), and
  `ONLY` only when the hero holds fewer than asked.

- `hand` (the `hand_over` client command) and `hand_intent` (typed "hand the crowbar to Elowen",
  M29.7a R8) share ONE path to another hero: `rules.hero_handing.hand_events`, then the engine
  line of the hand-over is told (no model call); a refusal is the rules' plain reason.

- `loot_intent` (M36.4 Y14, the menu's `loot:` entries): `rules.hero_handing.loot_events`, taking
  from a downed or dead hero's pack out of a fight, told the same way. M36.4: `take_intent`
  takes `qty` units of a stack when the act counts them.

- `pay_first` (typed "pay Rutter 4 silver", M29.9a T17): `rules.paying.pay_events` applied, or
  the rules' plain reason; the caller tells it (alone, or with the sentence's other act).

- `lift_intent` (typed "lift the link back out of his pouch", M29.7a R18):
  `rules.lifting.lift_events` (a Sleight of Hand check; the keepsake moves on a success, the
  NPC notices on a failure), then `telling.conclude` tells it.

Public API: `take_intent`, `give`, `give_intent`, `hand`, `hand_intent`, `loot_intent`,
`pay_first`, `lift_intent`.
"""

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.models.events import AnyEvent
from aidm.models.item_events import HandedOver
from aidm.models.protocol_client import Give, HandOver
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.state import Creature
from aidm.rules.acts import (
    GIVE_ALL,
    GiveIntent,
    HeroHandIntent,
    LiftIntent,
    LootIntent,
    PayIntent,
    TakeIntent,
)
from aidm.rules.equipment import EquipRefused, take_events
from aidm.rules.handing import GiveRefused, give_events
from aidm.rules.hero_handing import HandRefused, hand_events, loot_events
from aidm.rules.lifting import LiftRefused, lift_events
from aidm.rules.paying import PayRefused, pay_events
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude, follow_ups, remember, tell_text

ONLY = "{name} had only {n} of those to give."


async def take_intent(core: TableCore, player: Player, intent: TakeIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    item = core.state.world.items.get(intent.item_id)
    if pc is None or item is None:
        return
    try:
        events = take_events(core.state, pc, intent.item_id, intent.qty)
    except EquipRefused as refused:
        detail = refused.detail.capitalize() + "."
        core.error(player.id, ErrorCode.REFUSED, detail, refused.reason.value)
        return
    core.apply_all(events)
    moved = await follow_ups(core, events)
    name = item.name if item.catalog_id is None else item.name.lower()
    part = intent.qty is not None and intent.qty < item.qty and item.catalog_id is not None
    lines = [
        f"{pc.name} picks up {intent.qty} of the {name}."
        if part
        else f"{pc.name} picks up the {name}."
    ]
    lines += [line for e in moved if (line := template_line(core.state, e))]
    await remember(core, await tell_text(core, " ".join(lines)), [*events, *moved])


async def give(core: TableCore, player: Player, msg: Give) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    await _give(core, player, pc, msg.npc_id, (msg.item_id,))


async def give_intent(core: TableCore, player: Player, intent: GiveIntent) -> None:
    pc = core.state.creatures.get(intent.actor_id)
    if pc is None:
        return
    things = (intent.thing, *intent.more)
    given = await _give(core, player, pc, intent.npc_id, things)
    if given and GIVE_ALL > intent.said > len(things):  # M32.1a X6: say how many there were
        core.notice(player.id, NoticeKind.INFO, ONLY.format(name=pc.name, n=len(things)))


async def _give(
    core: TableCore, player: Player, pc: Creature, npc_id: str, things: tuple[str, ...]
) -> bool:
    events: list[AnyEvent] = []
    try:
        for thing in things:  # one hand-over per keepsake or unit of a counted give (M32.1a X6)
            events += core.apply_all(give_events(core.state, pc.id, npc_id, thing, core.regs.tiers))
    except GiveRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, refused.reason.value)
        if not events:
            return False
    await conclude(core, None, events, actor_id=pc.id)  # follow_ups settles regions and quests
    return True


async def hand(core: TableCore, player: Player, msg: HandOver) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    await _hand(core, player, HeroHandIntent(pc.id, msg.to_id, msg.item_id, msg.qty, msg.gold))


async def hand_intent(core: TableCore, player: Player, intent: HeroHandIntent) -> None:
    await _hand(core, player, intent)


async def loot_intent(core: TableCore, player: Player, intent: LootIntent) -> None:
    """M36.4 Y14: taking from a fallen hero's pack out of a fight; told like a hand-over."""
    try:
        events = loot_events(
            core.state,
            intent.actor_id,
            intent.from_id,
            core.regs.combat.chars,
            thing=intent.thing,
            qty=intent.qty,
            gold=intent.gold,
        )
    except HandRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, "hand_refused")
        return
    await _told(core, core.apply_all(events))


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
    await _told(core, core.apply_all(events))


async def _told(core: TableCore, applied: list[AnyEvent]) -> None:
    lines = [
        line for e in applied if isinstance(e, HandedOver) and (line := event_line(core.state, e))
    ]
    await remember(core, await tell_text(core, " ".join(lines)), applied)


def pay_first(core: TableCore, player: Player, intent: PayIntent) -> list[AnyEvent] | None:
    try:
        events = pay_events(core.state, intent.actor_id, intent.npc_id, intent.gold)
    except PayRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, "pay_refused")
        return None
    return core.apply_all(events)


async def lift_intent(core: TableCore, player: Player, intent: LiftIntent) -> None:
    try:
        events = lift_events(
            core.state,
            intent.actor_id,
            intent.npc_id,
            intent.keepsake_id,
            core.rng,
            core.regs.tiers,
        )
    except LiftRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.detail, "lift_refused")
        return
    core.apply_all(events)
    await conclude(core, None, events, actor_id=intent.actor_id)
