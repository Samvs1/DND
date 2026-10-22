"""Gear a creative effect leans on (M27.6, docs/next/GOAL_ITEMS.md "D: creative actions use the
same rules" and "D: substances, not one-off items").

The gear is the effect's `item` argument, else the gear phrase of the player's throw or use
sentence (`precheck.gear_phrase`, the M27.5 word matching of `aidm.dm.gear_words`). It resolves
to the hero's carried item (by name, by a substance word: "my bottle of water" is the carried
waterskin, the lit light in hand, or worn gear: "my shield"), else:
- a keepsake of that name: refused (a keepsake is never gear);
- a thing of the scene (a visible item or a feature): not gear, the creative effect runs;
- a catalogue item the hero does not carry, named by the model or said as the hero's own ("my
  rope"): refused, told as an attempt (the narrator's TRIED fact, `GEAR_REFUSED` prefix).
With carried gear, in this order (the item's own use, else a substance weakness, else the
creative effect):
1. damage aimed at a creature of the fight -> THE interpreter (`rules.item_use.use_item`): its
   listed use, else the SRD improvised throw (any item but a weapon or armor), spent per data;
2. aimed at a creature weak to one of the item's substances -> THE weakness rule
   (`rules.weaknesses`), and the item is used up (poured or splashed);
3. else None: the creative effect runs and the gear is kept.

Public API: `GEAR_REFUSED`, `leaned_gear(state, actor_id, item, text) -> str | None` (raises
`ToolRefused`), `gear_outcome(state, args, item, rng, regs) -> ToolResult | None`.
"""

from aidm.data.item_catalogue import ItemCategory, item_catalogue
from aidm.data.item_uses import SUBSTANCES, item_substances
from aidm.dm.gear_words import carried_entry, fits, words
from aidm.dm.precheck import gear_phrase
from aidm.dm.tool_context import ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_gear import gear_summary
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.dm_tiers import EffectKind
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.item_events import ItemUseRefused
from aidm.models.state import Creature, GameState
from aidm.rules.dice import Rng
from aidm.rules.item_effects import gear_name
from aidm.rules.item_use import keepsake_message, lacks_message, use_item
from aidm.rules.light import hero_light
from aidm.rules.scene import current_scene
from aidm.rules.weaknesses import substance_weakness_events, weak_to

GEAR_REFUSED = "Gear refused: "
_NOT_THROWN = (ItemCategory.WEAPON, ItemCategory.ARMOR)


def _carried(state: GameState, actor: Creature, phrase: str) -> str | None:
    found = carried_entry(actor, phrase)
    if found is not None or actor.pc is None:
        return found
    said = words(phrase) & SUBSTANCES
    for entry in actor.pc.inventory:
        if said & set(item_substances(entry.item)):
            return entry.item
    light = hero_light(state, actor.id)
    if light is not None and fits(words(phrase), gear_name(light.item)):
        return light.item
    worn = [w for w in actor.pc.equipped.model_dump().values() if isinstance(w, str)]
    return next((w for w in worn if fits(words(phrase), gear_name(w))), None)  # "my shield"


def _scenery(state: GameState, phrase: str) -> bool:
    scene = current_scene(state)
    world = state.world
    names = [world.items[i].name for i in scene.item_ids]
    names += [world.features[f].name for f in scene.feature_ids]
    wanted = words(phrase)
    return any(fits(wanted, n) for n in names)


def _catalogue(phrase: str) -> str | None:
    wanted = words(phrase)
    return next((i.id for i in item_catalogue().all() if fits(wanted, gear_name(i.id))), None)


def leaned_gear(state: GameState, actor_id: str, item: str | None, text: str) -> str | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    said = (item, True) if item else gear_phrase(text)
    if said is None:
        return None
    phrase, mine = said
    carried = _carried(state, actor, phrase)
    if carried is not None:
        return carried
    wanted = words(phrase)
    keepsake = next((k for k in actor.pc.keepsakes if fits(wanted, k.name)), None)
    if keepsake is not None:
        raise ToolRefused(GEAR_REFUSED + keepsake_message(keepsake.name))
    if _scenery(state, phrase):
        return None
    named = _catalogue(phrase)
    if named is not None and mine:
        raise ToolRefused(GEAR_REFUSED + lacks_message(actor, gear_name(named).lower()))
    return None


def _in_fight(state: GameState, target_id: str, actor_id: str) -> bool:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return False
    return target_id != actor_id and target_id in enc.combatants


def _thrown(
    state: GameState, args: CreativeEffectArgs, item: str, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    feats = regs.combat.chars.features
    events = use_item(state, args.actor, item, args.target, rng=rng, feats=feats)
    refusal = next((e for e in events if isinstance(e, ItemUseRefused)), None)
    if refusal is not None:
        raise ToolRefused(GEAR_REFUSED + refusal.message)
    return ToolResult(events=tuple(events), summary=gear_summary(state, events))


def _splashed(
    state: GameState, args: CreativeEffectArgs, item: str, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    target_id = args.target or ""
    feats = regs.combat.chars.features
    stuff = item_substances(item)
    events: list[AnyEvent] = list(
        substance_weakness_events(rng, state, args.actor, target_id, stuff, feats)
    )
    pc = state.creatures[args.actor].pc
    held = next((e.qty for e in pc.inventory if e.item == item), 1) if pc is not None else 1
    events.append(InventoryChanged(creature_id=args.actor, item=item, delta=-1, qty=held - 1))
    traits = ", ".join(e.trait for _, e in weak_to(state, target_id, stuff))
    target = state.creatures[target_id].name
    summary = f"the {gear_name(item).lower()} reaches {target}: {traits}; " + gear_summary(
        state, events
    )
    return ToolResult(events=tuple(events), summary=summary)


def gear_outcome(
    state: GameState, args: CreativeEffectArgs, item: str, rng: Rng, regs: ToolRegistries
) -> ToolResult | None:
    target_id = args.target or ""
    found = item_catalogue().find(item)
    throwable = found is None or found.category not in _NOT_THROWN
    damage = args.effect_kind is EffectKind.MINOR_DAMAGE
    if damage and throwable and _in_fight(state, target_id, args.actor):
        return _thrown(state, args, item, rng, regs)
    actor = state.creatures[args.actor]
    carried = actor.pc is not None and any(e.item == item for e in actor.pc.inventory)
    if (
        carried
        and target_id in state.creatures
        and weak_to(state, target_id, item_substances(item))
    ):
        return _splashed(state, args, item, rng, regs)
    return None
