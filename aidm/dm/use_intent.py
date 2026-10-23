"""Typed gear use (M27.5, docs/next/GOAL_ITEMS.md "Design": a deterministic precheck, like
`aidm.dm.give_intent`).

`use_intent(state, actor_id, clean)` reads the precheck's normalised sentence and returns a
`UseIntent` when it plainly uses gear the actor carries (`aidm.dm.gear_words`):
- "put out my torch", "douse the torch", "extinguish the lantern", "snuff out the candle",
  "put my torch out", "put out my light" (M29.7a R17: also pinch out, blow out, quench, shutter
  or cover the lantern): `put_out` (the hero's carried light; free);
- "light my torch", "ignite the lantern", "light a candle": a use with that verb;
  M29.7a: a purpose after the light ("light a candle to see", "douse the light so we can
  creep") is dropped;
- "throw the oil at Z", "scatter the caltrops at Z": a use with the verb, aimed at Z (M27.6:
  "throw my torch at Z" also finds the hero's lit torch; a verb that picks some of an item's
  several uses sets `use_id` to the one for the target: "light" vs "throw" the torch, at a
  creature the torch's hit; in a fight "throw my waterskin at Z", gear without a throw use, is
  the SRD improvised throw);
- "open my pack", "unpack my dungeoneer's pack" (M29.3b): the sealed pack's `unpack` use;
- "read the scroll of X" (M27.7: "... at/on Z"): a carried scroll that matches, aimed at Z;
- M29.9b T13 (`clue_read`): "read / examine / study the <clue keepsake>", any sentence part after
  it as `rest`: the read of a clue the hero carries (one `LoreLearned`);
- "use X", "use X on Y": every use of X, aimed at Y;
- "brew a poultice", "craft with my herbalism kit": a use with the verb (a long-rest use sets
  `at_rest`: the session proposes the rest and crafts during it).
Y and Z resolve to a feature here, a fight zone or a creature present (in a fight a creature
becomes its zone for gear that covers a zone); a target that names nothing known is dropped
("use the rope on the cliff"). Gear aimed at a creature when no use of it takes a creature
("use the rope on the goblin") is not a gear use: None, so the AI judges it. Anything else is
None and goes on to the adjudicator. The rules decide (`aidm.rules.item_use.use_item`,
`aidm.rules.light.put_out`).

`light_first(state, actor_id, clean)` (M29.7a R17): a compound sentence ("light a candle to see,
then look around", "pinch out the candle and we crouch low") whose FIRST act lights or puts out
a light is that intent with `rest`, the other act (the session does both).

Public API: `UseIntent(actor_id, item, target, verb, put_out, at_rest, use_id, rest)`,
`use_intent(state, actor_id, clean) -> UseIntent | None`, `light_first(...) -> UseIntent | None`,
`item_phrase(clean) -> (phrase, mine) | None`.
"""

import re
from dataclasses import dataclass, replace

from aidm.data.item_uses import (
    CastSpell,
    ConditionUse,
    DamageUse,
    Ignite,
    ItemUse,
    Stabilize,
    SurfaceUse,
    improvised_use,
    uses_for_item,
)
from aidm.dm.gear_words import carried_entry, fits, held_gear, lock_named, words
from aidm.dm.sentence import split_clause
from aidm.models.encounter import EncounterStatus
from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.light import hero_light
from aidm.rules.scene import current_scene

_THE = r"(?:my |the |a |an |our |this |that |some |his |her |their )?"
_THING = r"(?P<item>[a-z0-9 ,'-]+?)"
_AT = r"(?: (?:on|at|onto|into|against|to|toward|towards) (?:the |a |an |that |this )?"
_PUT_OUT = re.compile(
    r"(?:put out|douse|extinguish|snuff out|snuff|blow out|smother|pinch out|pinch|quench|"
    rf"shutter|cover|hood|close the shutter of|close the shutters of) {_THE}{_THING}|"
    rf"(?:put|pinch|blow|snuff) {_THE}(?P<item2>[a-z0-9 ,'-]+?) out"
)
_LIGHT = re.compile(rf"(?P<verb>light|ignite|kindle) (?:up )?{_THE}{_THING}(?: up)?")
_THROW = re.compile(
    rf"(?P<verb>throw|hurl|toss|lob|scatter|spill|pour|splash) {_THE}{_THING}"
    rf"{_AT}(?P<target>[a-z0-9' -]+))?"
)
_READ = re.compile(
    rf"(?P<verb>read) {_THE}(?P<item>scroll(?: of [a-z0-9' -]+?)?){_AT}(?P<target>[a-z0-9' -]+))?"
)
_OPEN = re.compile(rf"(?P<verb>open|unpack|unseal) (?:up )?{_THE}{_THING}")
_USE = re.compile(rf"use {_THE}{_THING}{_AT}(?P<target>[a-z0-9' -]+))?")
_CRAFT = re.compile(
    rf"(?P<verb>brew|craft) {_THE}(?P<what>[a-z0-9' -]+?)"
    rf"(?: (?:with|using) {_THE}(?P<item>[a-z0-9 ,'-]+))?"
)
_STUDY = re.compile(
    r"(?:read|reread|examine|study|inspect|peruse|unfold|look over|look at|pore over) "
    rf"{_THE}{_THING}(?: (?:carefully|closely|again|aloud|out loud|slowly))*"
)
_LIGHT_WORDS = frozenset({"light", "flame", "fire", "wick"})
_PURPOSE = re.compile(r" (?:so that|so|to|in order to|because|before|while|for) .+$")
_LIGHTS = frozenset({"light", "ignite", "kindle"})
_THROWS = frozenset({"throw", "hurl", "toss", "lob", "pour", "spill", "splash"})
_TAKES = (ConditionUse, Stabilize, DamageUse, CastSpell)  # uses that take a creature
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
    use_id: str | None = None  # M27.6: the use a verb picks ("throw" the torch, not "light")
    rest: str | None = None  # M29.7a: the other act of a compound sentence


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


def _target(
    state: GameState, phrase: str | None, uses: tuple[ItemUse, ...], throwing: bool
) -> str | None:
    """A known id for the phrase, '' when it names nothing known (dropped), None when absent
    or when it names a creature that no use of the gear takes. A creature stays the target
    when a use takes one or the gear is thrown in a fight (the interpreter puts a zone effect
    in its zone), else gear that covers a zone takes the creature's zone."""
    if not phrase:
        return None
    lock = lock_named(state, phrase)  # M27.10: "... to force open the lock" aims at the lock
    if lock is not None:
        return lock
    wanted = words(phrase)
    places, people = _named(state)
    place = _best(wanted, places)
    if place is not None:
        return place
    creature = _best(wanted, people)
    if creature is None:
        return ""
    if any(isinstance(u.effect, _TAKES) for u in uses) or (throwing and _fight(state)):
        return creature
    if any(isinstance(u.effect, SurfaceUse | Ignite) for u in uses) and _fight(state):
        return _zone_of(state, creature) or ""
    return None


def _pick(state: GameState, uses: tuple[ItemUse, ...], aimed: str | None) -> str:
    """Of the uses a verb picks, the one for the target: at a creature one that takes it."""
    at_creature = aimed in state.creatures
    found = (u.id for u in uses if isinstance(u.effect, _TAKES) == at_creature)
    return next(found, uses[0].id)


def _verb_uses(state: GameState, item: str, verb: str | None) -> tuple[ItemUse, ...]:
    """The item's uses the verb names; a throw in a fight of gear without a throw use is the
    SRD improvised throw (M27.6)."""
    said = {verb, _SAME_VERB.get(verb or "")}
    listed = uses_for_item(item)
    uses = tuple(u for u in listed if verb is None or said & set(u.verbs))
    improvised = improvised_use(item)
    if not uses and verb is not None and _fight(state) and said & set(improvised.verbs):
        return (improvised,)
    return uses


def _with_verb(
    state: GameState, actor: Creature, item: str | None, verb: str | None, target: str | None
) -> UseIntent | None:
    if item is None:
        return None
    uses = _verb_uses(state, item, verb)
    if not uses or (not _fight(state) and all(u.when == "fight" for u in uses)):
        return None  # out of a fight a throw goes to the AI (it may start the fight)
    aimed = _target(state, target, uses, verb in _THROWS)
    if target and aimed is None:  # aimed at a creature no use of it takes
        return None
    at_rest = all(u.when == "long_rest" for u in uses)
    every = uses_for_item(item)
    narrowed = verb is not None and len(every) > 1 and len(uses) < len(every)
    one = _pick(state, uses, aimed or None) if narrowed else None
    return UseIntent(actor.id, item, aimed or None, verb, at_rest=at_rest, use_id=one)


def _crafter(actor: Creature, verb: str) -> str | None:
    if actor.pc is None:
        return None
    return next(
        (e.item for e in actor.pc.inventory if any(verb in u.verbs for u in uses_for_item(e.item))),
        None,
    )


def clue_read(state: GameState, actor_id: str, clean: str) -> UseIntent | None:
    """M29.9b T13: "read the note", "examine the spore-ink note carefully" (and the rest of a
    compound sentence as `rest`) for a clue keepsake the hero carries (`rules.lore`); the read
    is a use of that keepsake (`rules.item_use.use_item`). Anything else: None."""
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    cut = split_clause(clean)
    head, rest = cut if cut is not None else (clean, None)
    m = _STUDY.fullmatch(head)
    if m is None:
        return None
    wanted = words(m["item"])
    clue = next((k for k in actor.pc.keepsakes if k.teaches and fits(wanted, k.name)), None)
    return UseIntent(actor.id, clue.name, verb="read", rest=rest) if clue is not None else None


def use_intent(state: GameState, actor_id: str, clean: str) -> UseIntent | None:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return None
    read = clue_read(state, actor_id, clean)
    if read is not None:
        return read
    aim = _PURPOSE.sub("", clean) if split_clause(clean) is None else clean
    if m := _PUT_OUT.fullmatch(aim):
        return _put_out(state, actor, m["item"] or m["item2"])
    if m := _LIGHT.fullmatch(aim):
        return _with_verb(state, actor, held_gear(state, actor, m["item"]), m["verb"], None)
    for pattern in (_LIGHT, _THROW, _READ, _OPEN):
        if m := pattern.fullmatch(clean):
            target = m["target"] if "target" in pattern.groupindex else None
            return _with_verb(state, actor, held_gear(state, actor, m["item"]), m["verb"], target)
    if m := _USE.fullmatch(clean):
        return _with_verb(state, actor, carried_entry(actor, m["item"]), None, m["target"])
    if m := _CRAFT.fullmatch(clean):
        item = carried_entry(actor, m["item"]) if m["item"] else _crafter(actor, m["verb"])
        return _with_verb(state, actor, item, m["verb"], None)
    return None


def light_first(state: GameState, actor_id: str, clean: str) -> UseIntent | None:
    cut = split_clause(clean)
    if cut is None:
        return None
    found = use_intent(state, actor_id, cut[0])
    if found is None or not (found.put_out or found.verb in _LIGHTS):
        return None
    return replace(found, rest=cut[1])


def item_phrase(clean: str) -> tuple[str, bool] | None:
    """(the gear phrase, said as the hero's own: "my"/"our") of a throw or use sentence (M27.6:
    the gear a creative effect leans on), else None."""
    for pattern in (_THROW, _USE):
        if m := pattern.fullmatch(clean):
            phrase = m["item"].strip()
            mine = re.search(rf"\b(?:my|our) {re.escape(phrase)}\b", clean) is not None
            return phrase, mine
    return None
