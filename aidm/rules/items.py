"""Using consumable items (potions): ONE generic path driven by data/bg3/consumables.json.

BG3 (SPEC 7.2): drinking a healing potion, or giving one to an ally in the same zone, is a
bonus action. A potion is refused (and NOT consumed, no economy spent) when it would do nothing:
the target is at full HP (v1 regression, SPEC 13) or dead.

Public API:
- `check_item_use(state, user_id, item, target_id, regs) -> tuple[ConsumableDef, Creature]`:
  the item def and the target, or `CommandRefused` (not carried, not usable, bad target, full HP).
- `use_item_events(rng, state, user_id, item, target_id, regs) -> list[AnyEvent]`: validated
  use without economy (exploration and the DM tools use it too): `InventoryChanged` (-1), the
  `DiceRolled` heal, then `rules.damage.resolve_healing`.
- `use_item_command(state, cmd, regs, rng) -> list[AnyEvent]`: in combat: the target is the
  user or a living ally combatant in the same zone; costs the bonus action.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.data.consumable_defs import ConsumableDef
from aidm.models.commands import RefusalCode, UseItemCommand
from aidm.models.dice import RollKind
from aidm.models.events import AnyEvent, DiceRolled, InventoryChanged
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused, acting, changed, combat_target, spend
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng, roll


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
    if item_def.heal and target.hp >= target.max_hp:
        raise CommandRefused(RefusalCode.FULL_HP, f"{target.name} is already at full health.")
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
