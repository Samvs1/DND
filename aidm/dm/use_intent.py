"""Typed gear use (M27.5, docs/next/GOAL_ITEMS.md "Design": a deterministic precheck, like
`aidm.dm.give_intent`).

`use_intent(state, actor_id, clean)` reads the precheck's normalised sentence and returns a
`UseIntent` when it plainly uses gear the actor carries (`aidm.dm.gear_words`):
- "put out my torch", "douse the torch", "extinguish the lantern", "snuff out the candle",
  "put my torch out", "put out my light": `put_out` (the hero's carried light; free);
- "light my torch", "ignite the lantern", "light a candle": a use with that verb;
- "throw the oil at Z", "scatter the caltrops at Z": a use with the verb, aimed at Z;
- "read the scroll of X": a carried scroll that matches;
- "use X", "use X on Y": every use of X, aimed at Y;
- "brew a poultice", "craft with my herbalism kit": a use with the verb (a long-rest use sets
  `at_rest`: the session proposes the rest and crafts during it).
Y and Z resolve to a feature here, a fight zone or a creature present (in a fight a creature
becomes its zone for gear that covers a zone); a target that names nothing known is dropped
("use the rope on the cliff"). Gear aimed at a creature when no use of it takes a creature
("use the rope on the goblin") is not a gear use: None, so the AI judges it. Anything else is
None and goes on to the adjudicator. The rules decide (`aidm.rules.item_use.use_item`,
`aidm.rules.light.put_out`).

Public API: `UseIntent(actor_id, item, target, verb, put_out, at_rest)`,
`use_intent(state, actor_id, clean) -> UseIntent | None`.
"""

import re
from dataclasses import dataclass

from aidm.data.item_uses import (
    ConditionUse,
    DamageUse,
    ItemUse,
    Stabilize,
    SurfaceUse,
    uses_for_item,
)
from aidm.dm.gear_words import carried_entry, fits, words
from aidm.models.encounter import EncounterStatus
from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.light import hero_light
from aidm.rules.scene import current_scene

_THE = r"(?:my |the |a |an |our |this |that |some |his |her |their )?"
_THING = r"(?P<item>[a-z0-9 ,'-]+?)"
_AT = r"(?: (?:on|at|onto|into|against|to|toward|towards) (?:the |a |an |that |this )?"
_PUT_OUT = re.compile(
    rf"(?:put out|douse|extinguish|snuff out|snuff|blow out|smother) {_THE}{_THING}|"
    rf"put {_THE}(?P<item2>[a-z0-9 ,'-]+?) out"
)
_LIGHT = re.compile(rf"(?P<verb>light|ignite|kindle) (?:up )?{_THE}{_THING}(?: up)?")
_THROW = re.compile(
    rf"(?P<verb>throw|hurl|toss|lob|scatter|spill|pour) {_THE}{_THING}"
    rf"{_AT}(?P<target>[a-z0-9' -]+))?"
)
_READ = re.compile(rf"(?P<verb>read) {_THE}(?P<item>scroll(?: of [a-z0-9' -]+)?)")
_USE = re.compile(rf"use {_THE}{_THING}{_AT}(?P<target>[a-z0-9' -]+))?")
_CRAFT = re.compile(
    rf"(?P<verb>brew|craft) {_THE}(?P<what>[a-z0-9' -]+?)"
    rf"(?: (?:with|using) {_THE}(?P<item>[a-z0-9 ,'-]+))?"
)
_LIGHT_WORDS = frozenset({"light", "flame", "fire"})
_SAME_VERB = {
    "ignite": "light",
    "kindle": "light",
    "hurl": "throw",
    "toss": "throw",
    "lob": "throw",
}


@dataclass(frozen=True)
class UseIntent:
    actor_id: str
    item: str
    target: str | None = None
    verb: str | None = None
    put_out: bool = False
    at_rest: bool = False


def _fight(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def _put_out(state: GameState, actor: Creature, phrase: str) -> UseIntent | None:
    light = hero_light(state, actor.id)
    wanted = words(phrase)
    if light is not None and (wanted <= _LIGHT_WORDS or fits(wanted, gear_name(light.item))):
        return UseIntent(actor.id, light.item, put_out=True)
    item = carried_entry(actor, phrase)
    if item is None and not wanted <= _LIGHT_WORDS:
        return None
    return UseIntent(actor.id, item or "light", put_out=True)


def _zone_of(state: GameState, creature_id: str) -> str | None:
    enc = state.encounter
    there = enc.combatants.get(creature_id) if enc is not None else None
    return there.zone_id if there is not None else None


def _best(wanted: frozenset[str], named: list[tuple[str, str]]) -> str | None:
    """The id whose name shares the most words (of 3+ letters) with the phrase."""
    scored = [(len({w for w in words(name) if len(w) > 2} & wanted), i) for i, name in named]
    top = max(scored, default=(0, ""))
    return top[1] if top[0] > 0 else None


def _named(state: GameState) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(features and fight zones, creatures and NPCs present) as (id, name)."""
    scene = current_scene(state)
    places = [(f, state.world.features[f].name) for f in scene.feature_ids]
    enc = state.encounter
    if _fight(state) and enc is not None:
        places += [(z.id, z.name) for z in enc.zone_map.zones]
    people = [(c, state.creatures[c].name) for c in (*scene.party_ids, *scene.monster_ids)]
    people += [(n, state.world.npcs[n].name) for n in scene.npc_ids]
    return places, people


def _target(state: GameState, phrase: str | None, uses: tuple[ItemUse, ...]) -> str | None:
    """A known id for the phrase, '' when it names nothing known (dropped), None when absent
    or when it names a creature that no use of the gear takes."""
    if not phrase:
        return None
    wanted = words(phrase)
    places, people = _named(state)
    place = _best(wanted, places)
    if place is not None:
        return place
    creature = _best(wanted, people)
    if creature is None:
        return ""
    if any(isinstance(u.effect, SurfaceUse) for u in uses) and _fight(state):
        return _zone_of(state, creature) or ""
    takes = (ConditionUse, Stabilize, DamageUse)
    return creature if any(isinstance(u.effect, takes) for u in uses) else None


def _with_verb(
    state: GameState, actor: Creature, item: str | None, verb: str | None, target: str | None
) -> UseIntent | None:
    if item is None:
        return None
    said = (verb, _SAME_VERB.get(verb or ""))
    uses = tuple(u for u in uses_for_item(item) if verb is None or set(said) & set(u.verbs))
    if not uses or (not _fight(state) and all(u.when == "fight" for u in uses)):
        return None  # out of a fight a throw goes to the AI (it may start the fight)
    aimed = _target(state, target, uses)
    if target and aimed is None:  # aimed at a creature no use of it takes
        return None
    at_rest = all(u.when == "long_rest" for u in uses)
    return UseIntent(actor.id, item, aimed or None, verb, at_rest=at_rest)


def _crafter(actor: Creature, verb: str) -> str | None:
    if actor.pc is None:
        return None
    return next(
        (e.item for e in actor.pc.inventory if any(verb in u.verbs for u in uses_for_item(e.item))),
        None,
    )


def use_intent(state: GameState, actor_id: str, clean: str) -> UseIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    if m := _PUT_OUT.fullmatch(clean):
        return _put_out(state, actor, m["item"] or m["item2"])
    for pattern in (_LIGHT, _THROW, _READ):
        if m := pattern.fullmatch(clean):
            target = m["target"] if "target" in pattern.groupindex else None
            return _with_verb(state, actor, carried_entry(actor, m["item"]), m["verb"], target)
    if m := _USE.fullmatch(clean):
        return _with_verb(state, actor, carried_entry(actor, m["item"]), None, m["target"])
    if m := _CRAFT.fullmatch(clean):
        item = carried_entry(actor, m["item"]) if m["item"] else _crafter(actor, m["verb"])
        return _with_verb(state, actor, item, m["verb"], None)
    return None
