"""Gear named in a player's words (M27.5): the one word matcher of the use precheck
(`aidm.dm.use_intent`) and the scoped rope rule (`request_check`, `aidm.rules.gear_fit`).

Words are compared through `rules.quest_items.item_words` (lowercase, articles dropped, a plural
"s" dropped), and gear by its catalogue name without its qualifier (`item_effects.gear_name`:
"Rope, hempen (50 feet)" is "Rope"), so "my rope" names the hempen rope and "my thieves' tools"
the thieves' tools. A keepsake is named by its own name ("Rope" the keepsake is still a rope
in words, but it has no use: the rules say so).

Public API: `words(text) -> frozenset[str]`, `fits(wanted, name) -> bool` (one set of words
inside the other), `carried_entry(actor, phrase) -> str | None` (the inventory item a short
phrase names), `held_gear(state, actor, phrase) -> str | None` (the same, or by a substance
word, or the lit light: THE gear matcher of the typed precheck and of creative effects),
`named_gear(state, actor_id, text) -> list[str]` (the inventory items and the keepsake ids a
sentence names), `lock_named(state, text) -> str | None`, `aims_at_lock(state, text, feature)
-> bool`.
"""

from aidm.data.item_uses import SUBSTANCES, item_substances
from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.light import hero_light
from aidm.rules.locks import locked_here
from aidm.rules.quest_items import item_words

_NOISE = frozenset({"of", "my", "our", "his", "her", "their"})
_LOCK_WORDS = frozenset({"lock", "locked", "padlock", "keyhole"})


def words(text: str) -> frozenset[str]:
    return frozenset(w for w in item_words(text) if len(w) > 1 and w not in _NOISE)


def fits(wanted: frozenset[str], name: str) -> bool:
    have = words(name)
    return bool(wanted) and bool(have) and (wanted <= have or have <= wanted)


def _names(item: str) -> tuple[str, ...]:
    return (gear_name(item), item.replace("-", " "))


def carried_entry(actor: Creature, phrase: str) -> str | None:
    if actor.pc is None:
        return None
    wanted = words(phrase)
    return next(
        (e.item for e in actor.pc.inventory if any(fits(wanted, n) for n in _names(e.item))),
        None,
    )


def held_gear(state: GameState, actor: Creature, phrase: str) -> str | None:
    """The carried item a phrase names: by name, else by a substance word ("my bottle of
    water" is the carried waterskin, M27.6), else the hero's lit light ("my torch" in hand)."""
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
    return None


def named_gear(state: GameState, actor_id: str, text: str) -> list[str]:
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None:
        return []
    said = words(text)
    found = [e.item for e in actor.pc.inventory if (w := words(gear_name(e.item))) and w <= said]
    found += [k.id for k in actor.pc.keepsakes if (w := words(k.name)) and w <= said]
    return found


def lock_named(state: GameState, text: str) -> str | None:
    """The locked feature here that the words aim at: named by its name, else the first locked
    one when they say "lock" (M27.10: "use the rope to force open the lock")."""
    said = words(text)
    here = [
        (f, found)
        for f in state.world.features
        if not isinstance(found := locked_here(state, f), str)
    ]
    for fid, found in here:
        if {w for w in words(found.name) if len(w) > 2} & said:
            return fid
    return here[0][0] if here and said & _LOCK_WORDS else None


def aims_at_lock(state: GameState, text: str, feature: str | None) -> bool:
    """The check is aimed at a lock: it names a locked feature here, or says "lock"."""
    if feature is not None and not isinstance(locked_here(state, feature), str):
        return True
    return lock_named(state, text) is not None
