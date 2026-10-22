"""THE item-use interpreter (docs/next/GOAL_ITEMS.md "Design", M27.3). PURE: returns events.

The AI proposes (`use_item(actor, item, target?)`, M27.5), the engine disposes. In order:
1. the actor is a hero carrying the CATALOGUE item (matched by catalogue id or name; a keepsake
   never counts, even one named "Rope");
2. one item use per action: an `ItemUsed` by the same hero among `prior` (the events already
   produced for this action) refuses the next;
3. a use of that item (data/bg3/item_uses.json, optionally the one `use_id`) fits:
   - its effect is wired (`item_effects.not_wired`: unlock M27.4, cast_spell M27.7, damage M27.6),
   - the situation (`when`): a use without a fight `cost` is never used in a fight; `fight` needs
     one; `dark_place` needs a dark place and a hero without a lit light, and out of a fight a
     place no carried light lights yet (in a fight the light must reach a new zone,
     `item_effects`); `tagged_place` a place with one of its terrain
     tags; `long_rest` the caller's `resting`; `place` and `ally_down` anywhere,
   - charges left (an entry without `charges` is full),
   - in a fight its cost (action / bonus) through the action economy (`command_checks.spend`),
   - the target, and the effect changes something (`item_effects.effect_events`);
4. events: `EconomyChanged` (in a fight), `ItemUsed`, the effect's events, `InventoryChanged`
   (-1 when the use consumes the item or spends its last charge), `PlaceAlerted` (a `noise` use,
   once per place).
Otherwise the ONLY event is `ItemUseRefused(message)`, telling the model what to narrate
instead (an attempt, never a result); nothing is consumed. When several uses could apply, the
first that fits wins and the first refusal is reported.

Public API: `use_item(state, actor_id, item, target=None, *, rng, use_id=None, resting=False,
prior=()) -> list[AnyEvent]`, `refused(actor_id, item, message) -> ItemUseRefused`.
"""

from collections.abc import Sequence

from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import ItemUse, Supplies, uses_for_item
from aidm.models.character import InventoryItem
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.item_events import ItemUsed, ItemUseRefused, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused, changed, spend
from aidm.rules.dice import Rng
from aidm.rules.item_effects import UseCtx, effect_events, gear_name, not_wired
from aidm.rules.light import hero_light, place_dark, place_light
from aidm.rules.progression import node_plan


def refused(actor_id: str, item: str, message: str) -> ItemUseRefused:
    return ItemUseRefused(creature_id=actor_id or "?", item=item or "?", message=message)


def _carried(actor: Creature, item: str) -> InventoryItem | str:
    key = item.strip().lower()
    pc = actor.pc
    if pc is None:
        return "Only a hero carries gear to use."
    catalogue = item_catalogue()
    for entry in pc.inventory:
        found = catalogue.find(entry.item)
        if key in {entry.item.lower(), found.name.lower() if found is not None else ""}:
            return entry
    if any(key in {k.id.lower(), k.name.lower()} for k in pc.keepsakes):
        return (
            f"{item} is a keepsake, not gear: it has no use here. "
            "Narrate the attempt as a plain check without advantage."
        )
    return f"{actor.name} does not carry {item}; narrate that they reach for it and find nothing."


def _in_fight(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def _dark_problem(ctx: UseCtx, gear: str) -> str | None:
    state, actor = ctx.state, ctx.actor
    own = hero_light(state, actor.id)
    if own is not None:
        carried = gear_name(own.item).lower()
        return f"{actor.name} already carries a lit {carried}; the {gear} changes nothing."
    if not place_dark(state):
        return f"It is not dark here; the {gear} changes nothing."
    lit = place_light(state)
    if lit is not None and not _in_fight(state):
        bearer = state.creatures.get(lit.creature_id)
        who = bearer.name if bearer is not None else "a hero"
        return f"This place is already lit by {who}; the {gear} changes nothing."
    return None


def _tag_problem(state: GameState, use: ItemUse, gear: str) -> str | None:
    plan = node_plan(state, state.world.current_node)
    tags = {t.strip().lower() for t in plan.terrain_tags} if plan is not None else set[str]()
    if tags & set(use.tags):
        return None
    return f"The {gear} needs a place with {' or '.join(use.tags)}; this is not one."


def _situation_problem(ctx: UseCtx) -> str | None:
    use, state = ctx.use, ctx.state
    gear = gear_name(use.item).lower()
    fight = _in_fight(state)
    if fight and use.cost is None:
        return f"The {gear} cannot be used during a fight."
    if use.when == "fight" and not fight:
        return f"The {gear} is for a fight, and there is none now."
    if use.when == "dark_place":
        return _dark_problem(ctx, gear)
    if use.when == "tagged_place":
        return _tag_problem(state, use, gear)
    if use.when == "long_rest" and not ctx.resting:
        return f"The {gear} is used at a long rest; it happens when the party rests."
    if use.when == "locked":
        return f"There is nothing locked here for the {gear}."
    return None


def _charges(ctx: UseCtx) -> int | None:
    if ctx.use.charges is None:
        return None
    return ctx.entry.charges if ctx.entry.charges is not None else ctx.use.charges


def _fight_cost(ctx: UseCtx) -> list[AnyEvent] | str:
    use = ctx.use
    if not _in_fight(ctx.state) or use.cost is None:
        return []
    try:
        economy = spend(
            ctx.state,
            ctx.actor.id,
            action=use.cost == "action",
            bonus_action=use.cost == "bonus",
            reason=use.label,
        )
    except CommandRefused as error:
        return error.reason
    return [changed(ctx.actor.id, economy, use.label)]


def _bookkeeping(ctx: UseCtx, charges: int | None) -> tuple[ItemUsed, list[AnyEvent]]:
    use, entry, node = ctx.use, ctx.entry, ctx.state.world.current_node
    left = charges - 1 if charges is not None else None
    used_up = use.consumes or left == 0
    used = ItemUsed(
        creature_id=ctx.actor.id,
        item=entry.item,
        use_id=use.id,
        target=ctx.target,
        node=node,
        spends_charge=charges is not None,
        charges_left=None if left == 0 and entry.qty > 1 else left,
        forage=isinstance(use.effect, Supplies),
    )
    after: list[AnyEvent] = []
    if used_up:
        after.append(
            InventoryChanged(creature_id=ctx.actor.id, item=entry.item, delta=-1, qty=entry.qty - 1)
        )
    if use.noise and node is not None and ctx.state.world.alerted != node:
        after.append(PlaceAlerted(node=node))
    return used, after


def _try_use(ctx: UseCtx) -> list[AnyEvent] | str:
    problem = not_wired(ctx.use) or _situation_problem(ctx)
    if problem is not None:
        return problem
    charges = _charges(ctx)
    if charges is not None and charges <= 0:
        return f"The {gear_name(ctx.use.item).lower()} is used up; nothing is left to use."
    economy = _fight_cost(ctx)
    if isinstance(economy, str):
        return economy
    effects = effect_events(ctx)
    if isinstance(effects, str):
        return effects
    used, after = _bookkeeping(ctx, charges)
    return [*economy, used, *effects, *after]


def use_item(
    state: GameState,
    actor_id: str,
    item: str,
    target: str | None = None,
    *,
    rng: Rng,
    use_id: str | None = None,
    resting: bool = False,
    prior: Sequence[AnyEvent] = (),
) -> list[AnyEvent]:
    actor = state.creatures.get(actor_id)
    if actor is None:
        return [refused(actor_id, item, "Only a hero carries gear to use.")]
    entry = _carried(actor, item)
    if isinstance(entry, str):
        return [refused(actor_id, item, entry)]
    if any(isinstance(e, ItemUsed) and e.creature_id == actor_id for e in prior):
        message = "One item use per action: this one waits for the next action."
        return [refused(actor_id, entry.item, message)]
    uses = [u for u in uses_for_item(entry.item) if use_id is None or u.id == use_id]
    if not uses:
        gear = gear_name(entry.item).lower()
        message = f"The {gear} has no use here: narrate it as flavour or a plain check."
        return [refused(actor_id, entry.item, message)]
    first: str | None = None
    for use in uses:
        outcome = _try_use(UseCtx(state, actor, entry, use, target, rng, resting))
        if not isinstance(outcome, str):
            return outcome
        first = first or outcome
    return [refused(actor_id, entry.item, first or "That use does not fit here.")]
