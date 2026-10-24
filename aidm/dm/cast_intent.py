"""Typed casting outside a fight (M30.0b T7, round 3: a spell typed out of a fight stayed prose:
no spell event, a slot never spent, while the story kept the spell's effect).

The `cast_spell` phrase row (data/bg3/intent_phrases.json; a word of the lexicon's
`cast_words`, ranked after the healing rows, which read healing spells first) gives the
sentence; the resolver finds the spell it names (a spell of the engine's registry whose id words
are all said, the longest name winning) and returns a `CastIntent` the session casts through
the same engine path as typed healing (`rules.spells.cast_spell`: the spell must be on the
hero's sheet and ready, the lowest fitting slot is spent, else the rules refuse in plain
words). Only a spell that needs no battlefield (`rules.spell_targets.needs_battlefield`: no
attack, save, damage, area or point) is cast here, on the caster or on other heroes:
- a self spell targets the caster;
- the heroes the sentence names (by first name; "me", "myself", "herself" ... add the caster):
  the last one for a one-target spell, all of them for a many-target spell;
- nobody named: the caster.
A spell aimed at an NPC who stands here, a spell that needs a fight, or a sentence that names
no known spell is None: it goes on to the storyteller as before (which may start the fight).

Public API: `CastIntent(actor_id, spell, target_ids)`, `RESOLVERS` (`cast_spell`).
"""

import re
from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.spell_defs import SpellDef
from aidm.dm.heal_intent import named_heroes
from aidm.dm.intent_match import Found, Resolver
from aidm.models.state import GameState
from aidm.rules.scene import current_scene
from aidm.rules.spell_targets import needs_battlefield

_SELF_WORDS = frozenset({"me", "myself", "herself", "himself", "themself", "themselves", "self"})
_FILLER = frozenset({"the", "of", "and", "old", "young", "a", "an", "in", "at", "to"})


@dataclass(frozen=True)
class CastIntent:
    actor_id: str
    spell: str
    target_ids: tuple[str, ...]


def _id_words(index: str) -> frozenset[str]:
    return frozenset(index.split("-"))


def _named_spell(words: frozenset[str]) -> SpellDef | None:
    named = [s for s in combat_registries().spells.all() if _id_words(s.index) <= words]
    return max(named, key=lambda s: len(_id_words(s.index)), default=None)


def _names_npc_here(state: GameState, words: frozenset[str]) -> bool:
    npcs = (state.world.npcs[i] for i in current_scene(state).npc_ids)
    return any(words & (set(re.findall(r"[a-z]+", n.name.lower())) - _FILLER) for n in npcs)


def _targets(found: Found, spell: SpellDef) -> tuple[str, ...] | None:
    kind, actor_id = spell.targeting.kind, found.actor_id
    if kind == "self":
        return (actor_id,)
    named = named_heroes(found.state, actor_id, found.text)
    if found.words & _SELF_WORDS:
        named = [actor_id, *named]
    if not named:
        return None if _names_npc_here(found.state, found.words) else (actor_id,)
    return (named[-1],) if kind == "creature" else tuple(dict.fromkeys(named))


def _cast(found: Found) -> CastIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    spell = _named_spell(found.words)
    if spell is None or needs_battlefield(spell):
        return None
    targets = _targets(found, spell)
    return CastIntent(actor.id, spell.index, targets) if targets is not None else None


RESOLVERS: dict[str, Resolver] = {"cast_spell": _cast}
