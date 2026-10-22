"""The effect handlers of the item-use interpreter (M27.3; dispatched by `aidm.rules.item_use`).

ONE `match` on the closed effect vocabulary of data/bg3/item_uses.json; never a per-item
branch. Each handler returns the effect's events (EXISTING events wherever one exists) or a
refusal message (str) that tells the model what to narrate instead; a refusal consumes nothing.

- light_place: `LightLit(creature_id, item, reach)`: the hero carries the lit light from place to
  place until the next long rest (M27.12); in a fight it must light a zone no light reaches yet.
  Its `skills` give a boon that lasts as long as the light (until the long rest; bullseye).
- boon: `BoonGained` (refused when the hero's boons already cover it: advantage never stacks).
- surface: the surface interpreter in the target zone (own or touching zone: a 20 ft throw).
- condition: `apply_condition` on a target creature in reach (refused when nothing changes).
- supplies: a Survival-style `gear_check` at DC 10 (easy) -> `CampSuppliesChanged(+amount)` on
  success; the place's once-per-place use is spent either way (`ItemUsed.forage`).
- stabilize: `Stabilized` on a dying ally in reach, no check (SRD healer's kit).
- craft: needs the tool proficiency (SRD herbalism) and the camp supplies ->
  `CampSuppliesChanged(-n)` + `InventoryChanged(output +1)`.
- reveal_map: `PlacesCharted` (the unknown neighbours of the current place).
- unlock (M27.4), cast_spell (M27.7), damage (thrown attacks, M27.6): not wired yet
  (`not_wired`), refused with a plain message.

Public API: `UseCtx`, `gear_name(item_id)`, `FORAGE_DC`, `not_wired(use) -> str | None`,
`in_reach(state, actor_id, zone_id) -> bool`, `effect_events(ctx) -> list[AnyEvent] | str`.
"""

from dataclasses import dataclass

from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import (
    Boon,
    CastSpell,
    ConditionUse,
    Craft,
    DamageUse,
    ItemUse,
    LightPlace,
    RevealMap,
    Stabilize,
    Supplies,
    SurfaceUse,
    Unlock,
)
from aidm.data.surface_defs import surface_defs
from aidm.models.abilities import Skill
from aidm.models.character import InventoryItem
from aidm.models.checks import DcTier
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent, CampSuppliesChanged, CheckResolved, InventoryChanged
from aidm.models.item_events import BoonGained, LightLit, PlacesCharted
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.models.world import ActiveBoon, BoonScope
from aidm.models.zones import ZoneSurface
from aidm.rules.boons import boon_adds_nothing
from aidm.rules.checks import dc_for_tier, tool_proficient
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.death import is_dying, stabilize
from aidm.rules.dice import Rng
from aidm.rules.gear_checks import gear_check
from aidm.rules.light import light_reach_zones, lit_zones
from aidm.rules.surfaces import place_surface_events
from aidm.rules.zones import zone_neighbors

FORAGE_TIER = DcTier.EASY
FORAGE_DC = dc_for_tier(FORAGE_TIER)

_LATER = {
    "unlock": "Locks do not answer to gear yet",
    "cast_spell": "Reading scrolls is not wired yet",
    "damage": "Throwing gear at a foe is not wired yet",
}


@dataclass(frozen=True)
class UseCtx:
    state: GameState
    actor: Creature
    entry: InventoryItem
    use: ItemUse
    target: str | None
    rng: Rng
    resting: bool


def gear_name(item_id: str) -> str:
    """The catalogue name without its qualifier: "Rope, hempen (50 feet)" -> "Rope"."""
    found = item_catalogue().find(item_id)
    name = found.name if found is not None else item_id
    return name.split(" (")[0].split(",")[0].strip()


def not_wired(use: ItemUse) -> str | None:
    later = _LATER.get(use.effect.kind)
    if later is None:
        return None
    return f"{later}: narrate the attempt with the {gear_name(use.item).lower()} as a plain check."


def _fight(state: GameState) -> Encounter | None:
    enc = state.encounter
    return enc if enc is not None and enc.status is EncounterStatus.ACTIVE else None


def in_reach(state: GameState, actor_id: str, zone_id: str) -> bool:
    enc = _fight(state)
    if enc is None:
        return True
    here = enc.combatants[actor_id].zone_id if actor_id in enc.combatants else None
    if here is None:
        return False
    return zone_id == here or zone_id in {z for z, _ in zone_neighbors(enc.zone_map, here)}


def _creature_in_reach(ctx: UseCtx, *, touch: bool) -> Creature | str:
    target = ctx.state.creatures.get(ctx.target or "")
    if target is None or target.dead:
        return f"Name a living creature to use the {gear_name(ctx.use.item).lower()} on."
    enc = _fight(ctx.state)
    if enc is None:
        return target
    there = enc.combatants.get(target.id)
    mine = enc.combatants.get(ctx.actor.id)
    if there is None or mine is None:
        return f"{target.name} is not in this fight."
    near = (
        there.zone_id == mine.zone_id
        if touch
        else in_reach(ctx.state, mine.creature_id, there.zone_id)
    )
    return (
        target
        if near
        else f"{target.name} is out of reach of the {gear_name(ctx.use.item).lower()}."
    )


def _boon(
    ctx: UseCtx, skills: tuple[str, ...], saves: tuple[str, ...], scope: BoonScope
) -> ActiveBoon:
    use = ctx.use
    return ActiveBoon(
        creature_id=ctx.actor.id,
        use_id=use.id,
        name=gear_name(use.item),
        skills=skills,
        saves_against=saves,
        scope=scope,
        node=ctx.state.world.current_node if scope == "place" else None,
        tool=use.item if use.tool else None,
    )


def _light(ctx: UseCtx, effect: LightPlace) -> list[AnyEvent] | str:
    state, actor = ctx.state, ctx.actor
    if _fight(state) is not None:
        new = light_reach_zones(state, actor.id, effect.reach) - lit_zones(state)
        if not new:
            gear = gear_name(ctx.use.item).lower()
            return f"Every zone the {gear} would reach is already lit; it changes nothing."
    events: list[AnyEvent] = [
        LightLit(creature_id=actor.id, item=ctx.entry.item, reach=effect.reach)
    ]
    if effect.skills:  # the light lasts until the long rest, and so does its boon
        events.append(BoonGained(boon=_boon(ctx, effect.skills, (), "until_long_rest")))
    return events


def _gain(ctx: UseCtx, effect: Boon) -> list[AnyEvent] | str:
    boon = _boon(ctx, effect.skills, effect.saves_against, effect.scope)
    if boon_adds_nothing(ctx.state, boon):
        return f"{boon.name} already helps {ctx.actor.name} here; using it again changes nothing."
    return [BoonGained(boon=boon)]


def _surface(ctx: UseCtx, effect: SurfaceUse) -> list[AnyEvent] | str:
    enc = _fight(ctx.state)
    gear = gear_name(ctx.use.item).lower()
    zones = {z.id: z for z in enc.zone_map.zones} if enc is not None else {}
    zone = zones.get(ctx.target or "")
    if zone is None:
        return f"Name the zone of this fight to throw the {gear} into."
    if not in_reach(ctx.state, ctx.actor.id, zone.id):
        return f"{zone.name} is too far for the {gear}: your zone or a touching one."
    duration = surface_defs().get(effect.surface).duration_rounds
    surface = ZoneSurface(kind=effect.surface, rounds_left=duration, source_id=ctx.actor.id)
    return place_surface_events(ctx.rng, ctx.state, zone.id, surface)


def _condition(ctx: UseCtx, effect: ConditionUse) -> list[AnyEvent] | str:
    target = _creature_in_reach(ctx, touch=False)
    if isinstance(target, str):
        return target
    gear = gear_name(ctx.use.item).lower()
    if any(c.name == effect.condition for c in target.conditions):
        return f"{target.name} is already {effect.condition}; the {gear} changes nothing."
    rounds = effect.rounds
    tick = ctx.actor.id if rounds is not None else None
    mark = new_condition(
        effect.condition, source_id=ctx.actor.id, rounds=rounds, tick_creature_id=tick
    )
    events = apply_condition(target, mark)
    return events or f"{target.name} shrugs it off; the {gear} changes nothing."


def _supplies(ctx: UseCtx, effect: Supplies) -> list[AnyEvent] | str:
    state = ctx.state
    if state.world.current_node in state.world.foraged:
        return "This place has already given what it can; trying again finds nothing."
    tool = ctx.use.item if ctx.use.tool else None
    result = gear_check(ctx.rng, state, ctx.actor, Skill(effect.skill), FORAGE_DC, tool=tool)
    result = result.model_copy(update={"tier": FORAGE_TIER})
    events: list[AnyEvent] = [
        CheckResolved(creature_id=ctx.actor.id, result=result, reason=ctx.use.label)
    ]
    if result.success:
        total = state.camp_supplies + effect.amount
        events.append(CampSuppliesChanged(delta=effect.amount, camp_supplies=total))
    return events


def _stabilize(ctx: UseCtx) -> list[AnyEvent] | str:
    target = _creature_in_reach(ctx, touch=True)
    if isinstance(target, str):
        return target
    enc = _fight(ctx.state)
    if enc is not None:
        ally = enc.combatants[target.id].side is enc.combatants[ctx.actor.id].side
    else:
        ally = target.kind is not CreatureKind.MONSTER
    if not ally or not is_dying(target):
        return f"{target.name} is not a dying ally; the {gear_name(ctx.use.item).lower()} waits."
    return stabilize(target)


def _craft(ctx: UseCtx, effect: Craft) -> list[AnyEvent] | str:
    gear = gear_name(ctx.use.item).lower()
    if ctx.use.tool and not tool_proficient(ctx.actor, ctx.use.item):
        return f"{ctx.actor.name} is not trained with the {gear}; crafting needs that proficiency."
    have = ctx.state.camp_supplies
    if have < effect.supplies:
        return f"Crafting needs {effect.supplies} camp supplies; the party has {have}."
    pc = ctx.actor.pc
    held = next((e.qty for e in pc.inventory if e.item == effect.output), 0) if pc else 0
    return [
        CampSuppliesChanged(delta=-effect.supplies, camp_supplies=have - effect.supplies),
        InventoryChanged(creature_id=ctx.actor.id, item=effect.output, delta=1, qty=held + 1),
    ]


def _reveal(ctx: UseCtx) -> list[AnyEvent] | str:
    world = ctx.state.world
    node = world.current_node
    known = {*world.visited, *world.charted, node}
    fresh = tuple(n for n in world.neighbours.get(node or "", ()) if n not in known)
    if not fresh:
        return "Every way from here is already known; charting changes nothing."
    return [PlacesCharted(nodes=fresh)]


def effect_events(ctx: UseCtx) -> list[AnyEvent] | str:
    effect = ctx.use.effect
    match effect:
        case LightPlace():
            return _light(ctx, effect)
        case Boon():
            return _gain(ctx, effect)
        case SurfaceUse():
            return _surface(ctx, effect)
        case ConditionUse():
            return _condition(ctx, effect)
        case Supplies():
            return _supplies(ctx, effect)
        case Stabilize():
            return _stabilize(ctx)
        case Craft():
            return _craft(ctx, effect)
        case RevealMap():
            return _reveal(ctx)
        case Unlock() | CastSpell() | DamageUse():
            return not_wired(ctx.use) or "That use is not wired yet."
