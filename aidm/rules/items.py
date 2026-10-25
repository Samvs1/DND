"""Using consumable items (potions): ONE generic path driven by data/bg3/consumables.json.

BG3 (SPEC 7.2): drinking a healing potion, or giving one to an ally in the same zone, is a
bonus action. A potion is refused (and NOT consumed, no economy spent) only when the target is
dead. Data adds effects, it never forbids actions (owner 2026-10-22, M27.7, superseding the SPEC
13 full-HP refusal): a healing potion drunk at full health is drunk and wasted, with an
`ItemUsed(use_id="drink", no_effect=True)` so every line says it had no effect.

Public API:
- `check_item_use(state, user_id, item, target_id, regs) -> tuple[ConsumableDef, Creature]`:
  the item def and the target, or `CommandRefused` (not carried, not usable, bad target, dead).
- `use_item_events(rng, state, user_id, item, target_id, regs) -> list[AnyEvent]`: validated
  use without economy (exploration and the DM tools use it too): `InventoryChanged` (-1), the
  `DiceRolled` heal, then `rules.damage.resolve_healing`; at full health `InventoryChanged` and
  the no-effect `ItemUsed` only (no roll).
- `use_item_command(state, cmd, regs, rng) -> list[AnyEvent]`: in combat: the target is the
  user or a living ally combatant in the same zone; costs the bonus action. An item that is not
  a consumable but has gear uses (data/bg3/item_uses.json, M27.6: thrown flasks, oil, caltrops,
  a torch, the healer's kit), or a command that names a use (`use_id`, M36.10b: the menu's
  improvised throw of any carried item) goes through THE item interpreter
  (`rules.item_use.use_item`, aimed at `target_zone` or `target_id`, its own cost); its refusal
  becomes
  `CommandRefused(GEAR_REFUSED, message)`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.data.consumable_defs import ConsumableDef
from aidm.data.item_uses import uses_for_item
from aidm.models.commands import RefusalCode, UseItemCommand
from aidm.models.dice import RollKind
from aidm.models.events import AnyEvent, DiceRolled, InventoryChanged
from aidm.models.item_events import ItemUsed, ItemUseRefused
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused, acting, changed, combat_target, spend
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng, roll
from aidm.rules.item_use import use_item

DRINK = "drink"  # ItemUsed.use_id of a potion drunk for nothing (M27.7)


def _carried(user: Creature, item: str) -> int:
    pc = user.pc
    if pc is None:
        return 0
    return sum(row.qty for row in pc.inventory if row.item == item)


def check_item_use(
    state: GameState, user_id: str, item: str, target_id: str | None, regs: CombatRegistries
) -> tuple[ConsumableDef, Creature]:
    user = state.creatures.get(user_id)
    if user is None or _carried(user, item) < 1:
        raise CommandRefused(RefusalCode.ITEM_NOT_OWNED, "You are not carrying that.")
    item_def = regs.consumables.find(item)
    if item_def is None:
        raise CommandRefused(RefusalCode.UNKNOWN_ITEM, "That item cannot be used like this.")
    target = state.creatures.get(target_id or user_id)
    if target is None:
        raise CommandRefused(RefusalCode.UNKNOWN_TARGET, "There is no one like that here.")
    if target.dead:
        raise CommandRefused(RefusalCode.INVALID_TARGET, f"It is too late to help {target.name}.")
    return item_def, target


def use_item_events(
    rng: Rng,
    state: GameState,
    user_id: str,
    item: str,
    target_id: str | None,
    regs: CombatRegistries,
) -> list[AnyEvent]:
    item_def, target = check_item_use(state, user_id, item, target_id, regs)
    left = _carried(state.creatures[user_id], item) - 1
    events: list[AnyEvent] = [InventoryChanged(creature_id=user_id, item=item, delta=-1, qty=left)]
    if item_def.heal and target.hp >= target.max_hp:  # drunk and wasted (owner rule, M27.7)
        wasted = ItemUsed(
            creature_id=user_id, item=item, use_id=DRINK, target=target.id, no_effect=True
        )
        return [wasted, *events]
    if item_def.heal:
        healed = roll(item_def.heal, rng)
        events.append(
            DiceRolled(
                roll=healed,
                roller_id=user_id,
                label=item_def.name,
                kind=RollKind.HEAL,
                target_id=target.id,
            )
        )
        events.extend(resolve_healing(target, max(0, healed.total)))
    return events


def use_item_command(
    state: GameState, cmd: UseItemCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    actor = acting(state, cmd.actor_id)
    gear = uses_for_item(cmd.item) or cmd.use_id is not None  # a named use is gear (M36.10b)
    if regs.consumables.find(cmd.item) is None and gear:
        return _gear_command(state, cmd, regs, rng)
    target_id = cmd.target_id or cmd.actor_id
    if target_id != cmd.actor_id:
        target = combat_target(state, actor, target_id)
        other = actor.enc.combatant(target.id)
        if other.side is not actor.combatant.side:
            raise CommandRefused(RefusalCode.INVALID_TARGET, f"{target.name} is not your ally.")
        if other.zone_id != actor.combatant.zone_id:
            raise CommandRefused(RefusalCode.OUT_OF_RANGE, f"{target.name} is not close enough.")
    check_item_use(state, cmd.actor_id, cmd.item, target_id, regs)
    economy = spend(state, cmd.actor_id, bonus_action=True, reason="use item")
    events = use_item_events(rng, state, cmd.actor_id, cmd.item, target_id, regs)
    return [changed(cmd.actor_id, economy, "use item"), *events]


def _gear_command(
    state: GameState, cmd: UseItemCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    target = cmd.target_zone or cmd.target_id
    events = use_item(state, cmd.actor_id, cmd.item, target, rng=rng, use_id=cmd.use_id, regs=regs)
    refused = next((e for e in events if isinstance(e, ItemUseRefused)), None)
    if refused is not None:
        raise CommandRefused(RefusalCode.GEAR_REFUSED, refused.message)
    return events
