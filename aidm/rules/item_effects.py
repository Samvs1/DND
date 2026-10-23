"""The effect handlers of the item-use interpreter (M27.3; dispatched by `aidm.rules.item_use`).

ONE `match` on the closed effect vocabulary of data/bg3/item_uses.json; never a per-item
branch. Each handler returns the effect's events (EXISTING events wherever one exists) or a
refusal message (str) that tells the model what to narrate instead; a refusal consumes nothing.
Data adds effects, it never forbids actions (owner, 2026-10-22): a handler refuses only what is
impossible (no such target, out of reach, a lock that is not there, no key, missing supplies or
the know-how to craft); a use that would change nothing HAPPENS with no events (`[]`: the item
is spent per its data and the interpreter marks `ItemUsed.no_effect`).

- light_place: `LightLit(creature_id, item, reach)`: the hero carries the lit light from place to
  place until the next long rest (M27.12), lit anywhere (daylight too: it matters in the next
  dark place); in a fight it may light no new zone (the bonus action is spent all the same).
  Its `skills` give a boon that lasts as long as the light (until the long rest; bullseye).
- boon: `BoonGained` (refused when the hero's boons already cover it: advantage never stacks).
- surface: the surface interpreter in the target zone (own or touching zone: a 20 ft throw).
- condition: `apply_condition` on a target creature in reach (none when it already has it or is
  immune).
- supplies: a Survival-style `gear_check` at DC 10 (easy) -> `CampSuppliesChanged(+amount)` on
  success; the place's once-per-place use is spent either way (`ItemUsed.forage`); a place
  already foraged gives nothing (no check).
- stabilize: `Stabilized` on a dying ally in touch reach, no check (SRD healer's kit); on anyone
  else the charge is spent for nothing.
- craft: needs the tool proficiency (SRD herbalism) and the camp supplies ->
  `CampSuppliesChanged(-n)` + `InventoryChanged(output +1)`.
- reveal_map: `PlacesCharted` (the unknown neighbours of the current place; none when all known).
- unlock (M27.4): the target is a locked feature here (`aidm.rules.locks`); one pick or force
  roll at the lock's DC with this gear (`attempt_lock`: the tool's proficiency, the crowbar's
  named advantage); `FeatureUnlocked` on success. The `noise` of a force use alerts the place
  either way (`aidm.rules.item_use`); a failed roll can be retried.
- damage (M27.6): a thrown attack through THE attack path (`aidm.rules.item_throw`): improvised
  weapon, 20/60 ft, the item's dice and type, its `condition` on a hit (burning), then the
  substance weakness of the item's `substances`.
- surface / ignite aimed at a creature of the fight land in that creature's zone.
- ignite (M27.6): damage of a type into a zone in reach (`rules.surfaces.zone_damage_events`:
  a lit torch into oil sets it alight); where nothing reacts the torch just lands there.
- unpack (M29.3b): the sealed pack's SRD contents (`pack_items`, the creation function) are added
  as `InventoryChanged`; the use `consumes` the pack. Out of a fight only (no cost).
- cast_spell (M27.7): the scroll's spell through THE spell engine with the SRD Spell Scroll
  numbers and no slot (`aidm.rules.scroll_read.read_scroll`).

`UseCtx.regs` are the registries of the attack path and the spell engine (None: the shipped
ones); `UseCtx.free` skips the fight cost (the opening strike of a fight, M27.7).

Public API: `UseCtx`, `use_regs(ctx)`, `gear_name(item_id)`, `FORAGE_DC`,
`in_reach(state, actor_id, zone_id) -> bool`, `effect_events(ctx) -> list[AnyEvent] | str`.
"""

from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries, combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import (
    Boon,
    CastSpell,
    ConditionUse,
    Craft,
    DamageUse,
    Ignite,
    ItemUse,
    LightPlace,
    RevealMap,
    Stabilize,
    Supplies,
    SurfaceUse,
    Unlock,
    Unpack,
    item_substances,
)
from aidm.data.srd import srd
from aidm.data.srd_equipment import pack_items
from aidm.data.surface_defs import surface_defs
from aidm.models.abilities import Ability, Skill
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
from aidm.rules.item_throw import thrown_item_events
from aidm.rules.locks import LockGear, attempt_lock, key_open, locked_here
from aidm.rules.scroll_read import read_scroll
from aidm.rules.surfaces import place_surface_events, zone_damage_events
from aidm.rules.zones import zone_neighbors

FORAGE_TIER = DcTier.EASY
FORAGE_DC = dc_for_tier(FORAGE_TIER)


@dataclass(frozen=True)
class UseCtx:
    state: GameState
    actor: Creature
    entry: InventoryItem
    use: ItemUse
    target: str | None
    rng: Rng
    resting: bool
    regs: CombatRegistries | None = None
    free: bool = False


def use_regs(ctx: UseCtx) -> CombatRegistries:
    return ctx.regs if ctx.regs is not None else combat_registries()


def gear_name(item_id: str) -> str:
    """The catalogue name without its qualifier: "Rope, hempen (50 feet)" -> "Rope"."""
    found = item_catalogue().find(item_id)
    name = found.name if found is not None else item_id
    return name.split(" (")[0].split(",")[0].strip()


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
    actor = ctx.actor
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


def _zone_in_reach(ctx: UseCtx) -> str | tuple[str, str]:
    """(zone id, zone name) of the target zone in reach (own or touching), or a refusal."""
    enc = _fight(ctx.state)
    gear = gear_name(ctx.use.item).lower()
    zones = {z.id: z for z in enc.zone_map.zones} if enc is not None else {}
    there = enc.combatants.get(ctx.target or "") if enc is not None else None
    zone = zones.get(there.zone_id if there is not None else ctx.target or "")
    if zone is None:
        return f"Name the zone of this fight to throw the {gear} into."
    if not in_reach(ctx.state, ctx.actor.id, zone.id):
        return f"{zone.name} is too far for the {gear}: your zone or a touching one."
    return zone.id, zone.name


def _surface(ctx: UseCtx, effect: SurfaceUse) -> list[AnyEvent] | str:
    zone = _zone_in_reach(ctx)
    if isinstance(zone, str):
        return zone
    duration = surface_defs().get(effect.surface).duration_rounds
    surface = ZoneSurface(kind=effect.surface, rounds_left=duration, source_id=ctx.actor.id)
    return place_surface_events(ctx.rng, ctx.state, zone[0], surface)


def _ignite(ctx: UseCtx, effect: Ignite) -> list[AnyEvent] | str:
    zone = _zone_in_reach(ctx)
    if isinstance(zone, str):
        return zone
    return zone_damage_events(ctx.rng, ctx.state, zone[0], effect.damage_type)


def _throw(ctx: UseCtx, effect: DamageUse) -> list[AnyEvent] | str:
    feats = use_regs(ctx).chars.features
    name = gear_name(ctx.use.item).lower()
    stuff = item_substances(ctx.entry.item)
    return thrown_item_events(
        ctx.rng, ctx.state, ctx.actor.id, ctx.target, name, effect, feats, stuff
    )


def _condition(ctx: UseCtx, effect: ConditionUse) -> list[AnyEvent] | str:
    target = _creature_in_reach(ctx, touch=False)
    if isinstance(target, str):
        return target
    if any(c.name == effect.condition for c in target.conditions):
        return []
    rounds = effect.rounds
    tick = ctx.actor.id if rounds is not None else None
    mark = new_condition(
        effect.condition, source_id=ctx.actor.id, rounds=rounds, tick_creature_id=tick
    )
    return apply_condition(target, mark)


def _supplies(ctx: UseCtx, effect: Supplies) -> list[AnyEvent] | str:
    state = ctx.state
    if state.world.current_node in state.world.foraged:
        return []  # this place already gave what it can
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
    return stabilize(target) if ally and is_dying(target) else []


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
    return [PlacesCharted(nodes=fresh)] if fresh else []


def _unlock(ctx: UseCtx, effect: Unlock) -> list[AnyEvent] | str:
    feature = locked_here(ctx.state, ctx.target)
    if isinstance(feature, str):
        return feature
    if effect.method == "key":
        return key_open(ctx.state, ctx.actor.id, feature) or "No key the party carries fits."
    default = Ability.DEX if effect.method == "pick" else Ability.STR
    what = Skill(effect.skill) if effect.skill else Ability(effect.ability or default)
    use = ctx.use
    aid = gear_name(use.item) if effect.advantage else None
    gear = LockGear(ctx.entry.item, use.item if use.tool else None, aid)
    return attempt_lock(
        ctx.rng, ctx.state, ctx.actor, feature, effect.method, what, gear, use.label
    )


def _unpack(ctx: UseCtx, effect: Unpack) -> list[AnyEvent] | str:
    """The pack's SRD contents join the hero's gear (the interpreter removes the pack itself)."""
    items = pack_items(srd().equipment.find(ctx.entry.item))
    pc = ctx.actor.pc
    held = {e.item: e.qty for e in pc.inventory} if pc else {}
    events: list[AnyEvent] = []
    for item, qty in items:
        events.append(
            InventoryChanged(
                creature_id=ctx.actor.id, item=item, delta=qty, qty=held.get(item, 0) + qty
            )
        )
    return events


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
        case Unlock():
            return _unlock(ctx, effect)
        case DamageUse():
            return _throw(ctx, effect)
        case Ignite():
            return _ignite(ctx, effect)
        case Unpack():
            return _unpack(ctx, effect)
        case CastSpell():
            item, target = ctx.entry.item, ctx.target
            return read_scroll(
                ctx.state, ctx.actor.id, item, effect.spell, target, ctx.rng, use_regs(ctx)
            )
