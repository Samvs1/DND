"""THE item-use interpreter (docs/next/GOAL_ITEMS.md "Design", M27.3). PURE: returns events.

The AI proposes (`use_item(actor, item, target?)`, M27.5), the engine disposes. In order:
1. the actor is a hero carrying the CATALOGUE item (matched by catalogue id or name; a keepsake
   never counts, even one named "Rope");
2. one item use per action: an `ItemUsed` by the same hero among `prior` (the events already
   produced for this action) refuses the next;
3. a use of that item (`candidate_uses`: data/bg3/item_uses.json, optionally the one `use_id`;
   aimed at a creature of the fight only the uses that take a creature or its zone, then the
   SRD improvised throw, M27.6) fits:
   - its effect is wired (`item_effects.not_wired`: cast_spell M27.7),
   - the situation (`when`): a use without a fight `cost` is never used in a fight (it takes
     longer than a turn); `fight` needs one; `dark_place` (a light) needs a hero without a lit
     light and is lit anywhere (M27.6, owner: daylight too, it is carried into the next dark
     place); `tagged_place` a place with one of its terrain tags; `long_rest` the caller's
     `resting`; `locked` a target that is a locked feature here (M27.4,
     `aidm.rules.locks.locked_here`); `place` and `ally_down` anywhere,
   - charges left (an entry without `charges` is full),
   - in a fight its cost (action / bonus) through the action economy (`command_checks.spend`),
   - the target (`item_effects.effect_events`);
4. events: `EconomyChanged` (in a fight), `ItemUsed` (`no_effect` when the use changed nothing:
   data adds effects, it never forbids actions, owner 2026-10-22), the effect's events,
   `InventoryChanged` (-1 when the use consumes the item or spends its last charge),
   `PlaceAlerted` (a `noise` use, once per place; a light only in a dark place).
A use that is not a `locked` one, aimed at a locked feature here, is refused (M27.5: a rope
never forces a lock). A fitting key the party carries opens a locked target before any
`locked` use is tried
(`aidm.rules.locks.key_open`: automatic, no check, nothing used or alerted).
Otherwise the ONLY event is `ItemUseRefused(message)`, telling the model what to narrate
instead (an attempt, never a result); nothing is consumed. When several uses could apply, the
first that fits wins and the first refusal is reported.

M27.6: a `from_light` use (a lit torch thrown) is made with the hero's carried LIT light of that
item (found by `carried_gear` even when no such item is left in the pack) and ends it with
`LightEnded(reason="thrown")` instead of consuming anything; the effect sees the state with the
use's action already spent (the attack path's once-per-turn riders build on it); `feats` is the
feature registry for thrown attacks (None: the shipped one).

Public API: `use_item(state, actor_id, item, target=None, *, rng, use_id=None, resting=False,
prior=(), feats=None) -> list[AnyEvent]`, `refused(actor_id, item, message) -> ItemUseRefused`,
`situation_problem(state, actor, use, target, resting) -> str | None` (step 3's situation),
`candidate_uses(state, actor_id, item, target, use_id=None) -> list[ItemUse] | str`,
`carried_gear(state, actor, item) -> InventoryItem | str`, `keepsake_message(item)`,
`lacks_message(actor, item)` (the refusals of step 1),
`usable_uses(state, actor_id) -> list[(item, use, target)]` (the uses of the hero's gear that
fit here now: the adjudicator's usable-gear line, M27.5; long-rest uses are left out).
A light use that alerts names its cause (`PlaceAlerted(reason="light")`, M27.5).
"""

from collections.abc import Sequence
from dataclasses import replace

from aidm.data.feature_defs import FeatureDef
from aidm.data.item_catalogue import ItemCategory, item_catalogue
from aidm.data.item_uses import (
    CastSpell,
    ConditionUse,
    DamageUse,
    Ignite,
    ItemUse,
    LightPlace,
    Stabilize,
    Supplies,
    SurfaceUse,
    improvised_use,
    uses_for_item,
)
from aidm.data.registry import Registry
from aidm.models.character import InventoryItem
from aidm.models.combat_events import AttackRolled
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import AnyEvent, ConditionRemoved, InventoryChanged
from aidm.models.item_events import ItemUsed, ItemUseRefused, LightEnded, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.models.world import AlertCause
from aidm.rules.command_checks import CommandRefused, changed, spend
from aidm.rules.death import is_dying
from aidm.rules.dice import Rng
from aidm.rules.item_effects import UseCtx, effect_events, gear_name, not_wired
from aidm.rules.light import hero_light, place_dark
from aidm.rules.locks import key_open, locked_here
from aidm.rules.progression import node_plan
from aidm.rules.projection import project_state

THROWN = "thrown"  # LightEnded.reason when a lit light is thrown (M27.6)
_AT_CREATURE = (DamageUse, ConditionUse, Stabilize, SurfaceUse, Ignite, CastSpell)


def refused(actor_id: str, item: str, message: str) -> ItemUseRefused:
    return ItemUseRefused(creature_id=actor_id or "?", item=item or "?", message=message)


def _named(item_id: str, key: str) -> bool:
    found = item_catalogue().find(item_id)
    return key in {item_id.lower(), found.name.lower() if found is not None else ""}


def keepsake_message(item: str) -> str:
    return (
        f"{item} is a keepsake, not gear: it has no use here. "
        "Narrate the attempt as a plain check without advantage."
    )


def lacks_message(actor: Creature, item: str) -> str:
    return f"{actor.name} does not carry {item}; narrate that they reach for it and find nothing."


def carried_gear(state: GameState, actor: Creature, item: str) -> InventoryItem | str:
    """The hero's carried catalogue item named `item` (id or name), else the refusal."""
    key = item.strip().lower()
    pc = actor.pc
    if pc is None:
        return "Only a hero carries gear to use."
    for entry in pc.inventory:
        if _named(entry.item, key):
            return entry
    light = hero_light(state, actor.id)
    if light is not None and _named(light.item, key):  # M27.6: the lit light in hand
        return InventoryItem(item=light.item, qty=1)
    if any(key in {k.id.lower(), k.name.lower()} for k in pc.keepsakes):
        return keepsake_message(item)
    return lacks_message(actor, item)


def _in_fight(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def _dark_problem(state: GameState, actor: Creature, gear: str) -> str | None:
    """A light is lit anywhere (M27.6, owner: it is carried into the next dark place); only a
    hero who already carries a lit light cannot light a second one."""
    own = hero_light(state, actor.id)
    if own is not None:
        carried = gear_name(own.item).lower()
        return f"{actor.name} already carries a lit {carried}; the {gear} changes nothing."
    return None


def _tag_problem(state: GameState, use: ItemUse, gear: str) -> str | None:
    plan = node_plan(state, state.world.current_node)
    tags = {t.strip().lower() for t in plan.terrain_tags} if plan is not None else set[str]()
    if tags & set(use.tags):
        return None
    return f"The {gear} needs a place with {' or '.join(use.tags)}; this is not one."


def _not_a_key(state: GameState, use: ItemUse, target: str | None, gear: str) -> str | None:
    """A use that is not a `locked` one never opens a lock it is aimed at (the rope rule)."""
    feature = locked_here(state, target) if target in state.world.features else None
    if feature is None or isinstance(feature, str):
        return None
    return (
        f"The {gear} cannot open the {feature.name}; narrate the attempt as a plain check"
        " without its help."
    )


def _light_problem(state: GameState, actor: Creature, use: ItemUse, gear: str) -> str | None:
    light = hero_light(state, actor.id)
    if use.from_light and (light is None or light.item != use.item):
        return f"{actor.name} carries no lit {gear}; light one first."
    return None


def situation_problem(
    state: GameState, actor: Creature, use: ItemUse, target: str | None, resting: bool
) -> str | None:
    gear = gear_name(use.item).lower()
    fight = _in_fight(state)
    lit = _light_problem(state, actor, use, gear)
    if lit is not None:
        return lit
    if fight and use.cost is None:
        return f"The {gear} cannot be used during a fight."
    if use.when == "fight" and not fight:
        return f"The {gear} is for a fight, and there is none now."
    if use.when != "locked":
        problem = _not_a_key(state, use, target, gear)
        if problem is not None:
            return problem
    if use.when == "dark_place":
        return _dark_problem(state, actor, gear)
    if use.when == "tagged_place":
        return _tag_problem(state, use, gear)
    if use.when == "long_rest" and not resting:
        return f"The {gear} is used at a long rest; it happens when the party rests."
    if use.when == "locked":
        feature = locked_here(state, target)
        return feature if isinstance(feature, str) else None
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


def _bookkeeping(
    ctx: UseCtx, charges: int | None, no_effect: bool
) -> tuple[ItemUsed, list[AnyEvent]]:
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
        no_effect=no_effect,
    )
    after: list[AnyEvent] = []
    if use.from_light:
        after.append(LightEnded(creature_id=ctx.actor.id, reason=THROWN, item=use.item))
    elif used_up:
        after.append(
            InventoryChanged(creature_id=ctx.actor.id, item=entry.item, delta=-1, qty=entry.qty - 1)
        )
    world = ctx.state.world
    lighting = isinstance(use.effect, LightPlace)
    cause: AlertCause = "light" if lighting else "noise"
    fresh = world.alerted != node or (cause == "light" and world.alerted_by != "light")
    heard = use.noise and (not lighting or place_dark(ctx.state))  # a light alerts in the dark
    if heard and node is not None and fresh:
        after.append(PlaceAlerted(node=node, reason=cause))
    return used, after


def _changed_nothing(effects: Sequence[AnyEvent]) -> bool:
    """No effect events, or only a throw that hit and did nothing (holy water on a beast)."""
    hits = [e for e in effects if isinstance(e, AttackRolled)]
    neutral = all(isinstance(e, AttackRolled | EconomyChanged | ConditionRemoved) for e in effects)
    return not effects or (neutral and all(h.hit for h in hits))


def _try_use(ctx: UseCtx) -> list[AnyEvent] | str:
    problem = not_wired(ctx.use) or situation_problem(
        ctx.state, ctx.actor, ctx.use, ctx.target, ctx.resting
    )
    if problem is not None:
        return problem
    charges = _charges(ctx)
    if charges is not None and charges <= 0:
        return f"The {gear_name(ctx.use.item).lower()} is used up; nothing is left to use."
    economy = _fight_cost(ctx)
    if isinstance(economy, str):
        return economy
    spent = replace(ctx, state=project_state(ctx.state, economy)) if economy else ctx
    effects = effect_events(spent)
    if isinstance(effects, str):
        return effects
    used, after = _bookkeeping(ctx, charges, _changed_nothing(effects))
    return [*economy, used, *effects, *after]


def _key_first(
    state: GameState, actor_id: str, uses: Sequence[ItemUse], target: str | None
) -> list[AnyEvent]:
    if not any(u.when == "locked" for u in uses):
        return []
    feature = locked_here(state, target)
    return [] if isinstance(feature, str) else key_open(state, actor_id, feature)


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
    feats: Registry[FeatureDef] | None = None,
) -> list[AnyEvent]:
    actor = state.creatures.get(actor_id)
    if actor is None:
        return [refused(actor_id, item, "Only a hero carries gear to use.")]
    entry = carried_gear(state, actor, item)
    if isinstance(entry, str):
        return [refused(actor_id, item, entry)]
    if any(isinstance(e, ItemUsed) and e.creature_id == actor_id for e in prior):
        message = "One item use per action: this one waits for the next action."
        return [refused(actor_id, entry.item, message)]
    uses = candidate_uses(state, actor_id, entry.item, target, use_id)
    if isinstance(uses, str):
        return [refused(actor_id, entry.item, uses)]
    opened = _key_first(state, actor_id, uses, target)
    if opened:
        return opened
    first: str | None = None
    for use in uses:
        outcome = _try_use(UseCtx(state, actor, entry, use, target, rng, resting, feats))
        if not isinstance(outcome, str):
            return outcome
        first = first or outcome
    return [refused(actor_id, entry.item, first or "That use does not fit here.")]


def _at_creature(state: GameState, actor_id: str, target: str | None) -> bool:
    return _in_fight(state) and target != actor_id and target in state.creatures


def _at_zone(state: GameState, target: str | None) -> bool:
    enc = state.encounter
    return _in_fight(state) and enc is not None and enc.zone_map.has_zone(target or "")


def candidate_uses(
    state: GameState, actor_id: str, item: str, target: str | None, use_id: str | None = None
) -> list[ItemUse] | str:
    """The uses to try, in order: the item's listed uses; aimed at a zone of the fight those that
    cover a zone first; aimed at a creature of the fight only those that take a creature (or
    its zone), and when it has none, the SRD improvised throw
    (any item but a weapon or armor: those have their own attacks)."""
    listed = [u for u in uses_for_item(item) if use_id is None or u.id == use_id]
    gear = gear_name(item).lower()
    if not _at_creature(state, actor_id, target):
        if _at_zone(state, target):
            return [u for u in listed if isinstance(u.effect, SurfaceUse | Ignite)] or listed
        if listed:
            return listed
        return f"The {gear} has no use here: narrate it as flavour or a plain check."
    fit = [u for u in listed if isinstance(u.effect, _AT_CREATURE)]
    found = item_catalogue().find(item)
    if found is not None and found.category in (ItemCategory.WEAPON, ItemCategory.ARMOR):
        return fit or f"The {gear} is a weapon or armor: attack or throw it from the fight menu."
    improvised = improvised_use(item)
    if fit or (use_id is not None and use_id != improvised.id):
        return fit or listed
    return [improvised]


def _dying_ally(state: GameState) -> bool:
    return any(c.pc is not None and is_dying(c) for c in state.creatures.values())


def usable_uses(state: GameState, actor_id: str) -> list[tuple[str, ItemUse, str | None]]:
    """(item, use, target) for each use of the hero's carried gear that fits here now."""
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return []
    locks = [f for f in state.world.features if not isinstance(locked_here(state, f), str)]
    out: list[tuple[str, ItemUse, str | None]] = []
    light = hero_light(state, actor_id)
    items = [e.item for e in actor.pc.inventory]
    for item in [*items, *([light.item] if light is not None and light.item not in items else [])]:
        for use in uses_for_item(item):
            skip = use.when == "long_rest" or not_wired(use) is not None
            if skip or (use.when == "ally_down" and not _dying_ally(state)):
                continue
            targets: list[str | None] = [*locks] if use.when == "locked" else [None]
            out += [
                (item, use, target)
                for target in targets
                if situation_problem(state, actor, use, target, False) is None
            ]
    return out
