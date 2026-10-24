"""Typed casting outside a fight (M30.0b T7, round 3: a spell typed out of a fight stayed prose:
no spell event, a slot never spent, while the story kept the spell's effect).

The `cast_spell` phrase row (data/bg3/intent_phrases.json; a word of the lexicon's
`cast_words`, ranked after the healing rows, which read healing spells first) gives the
sentence; the resolver finds the spell it names (a spell of the engine's registry whose id words
are all said, the longest name winning) and returns a `CastIntent` the session casts through
the same engine path as typed healing (`rules.spells.cast_spell`: the spell must be on the
hero's sheet and ready, the lowest fitting slot is spent, else the rules refuse in plain
words). A spell that strikes no one and has creature targets (no attack, save, damage, area or
point) is cast on the caster or on other heroes:
- a self spell targets the caster;
- the heroes the sentence names (by first name; "me", "myself", "herself" ... add the caster):
  the last one for a one-target spell, all of them for a many-target spell;
- nobody named: the caster.
Such a spell aimed at an NPC who stands here, or a sentence that names no known spell, is None:
it goes on to the storyteller as before.

M30.2b (live probe: "I cast misty step to reach the roof" got `no_mechanics`, a free spell): no
spell is cast without the engine. A spell aimed at no creature is cast AT THE SCENE (`at_scene`,
`rules.spells.scene_cast`: the slot or resource is spent, nothing moves, nothing is covered),
decided from the spell's data only:
- a point or area spell that strikes no one (`strikes_creatures` false: Misty Step, Fog Cloud);
- a hostile spell (`strikes_creatures`: an attack, a save, damage, an HP pool) aimed at nothing
  or at scenery. M31.1a V2 (round 4: Burning Hands at reeds and Thunderwave over water spent no
  slot because NPCs stood near): only a hostile spell aimed AT someone, a line naming an NPC
  standing here or a foe of the waiting offer, is None (an attack, or the start of a fight, is
  the storyteller's call); people standing near do not make it one.
A scene cast needs the spell's name right after the cast word (`cast`, `casts`, `casting`, at
most two words between: "I cast a quick misty step"), so "I cast a glance at the web" is no Web.

M31.1a V2: the `named_spell` row reads a READY spell named without a cast word ("I murmur a
healing word over Rook", `dm.spell_names`): a healing spell is the typed-healing path
(`heal_intent.heal_spell`), any other the cast above, its name counting as said.

M31.2a: a utility cantrip (Light, Mage Hand, Prestidigitation ...: no dice, no buff) is read
only after a cast word (`_plain_word_spell`), so "I light the torch" is still the torch.

Public API: `CastIntent(actor_id, spell, target_ids, at_scene)`, `RESOLVERS` (`cast_spell`,
`named_spell`).
"""

import re
from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.data.spell_defs import HealEffect, LightSourceEffect, SpellDef, UtilityEffect
from aidm.dm.fight_names import tokens
from aidm.dm.heal_intent import HealIntent, heal_spell, named_heroes
from aidm.dm.intent_conditions import foe_words
from aidm.dm.intent_match import Found, Resolver
from aidm.dm.spell_names import ready_spells, said_name
from aidm.models.state import GameState
from aidm.rules.scene import current_scene
from aidm.rules.spell_targets import strikes_creatures

_SELF_WORDS = frozenset({"me", "myself", "herself", "himself", "themself", "themselves", "self"})
_FILLER = frozenset({"the", "of", "and", "old", "young", "a", "an", "in", "at", "to"})
_SCENE_KINDS = frozenset({"area", "point"})


@dataclass(frozen=True)
class CastIntent:
    actor_id: str
    spell: str
    target_ids: tuple[str, ...]
    at_scene: bool = False


def _id_words(index: str) -> frozenset[str]:
    return frozenset(index.split("-"))


def _named_spell(words: frozenset[str]) -> SpellDef | None:
    named = [s for s in combat_registries().spells.all() if _id_words(s.index) <= words]
    return max(named, key=lambda s: len(_id_words(s.index)), default=None)


def _names_npc_here(state: GameState, words: frozenset[str]) -> bool:
    """A word of the name or role of an NPC standing here (M31.1a: "the ferryman")."""
    npcs = [state.world.npcs[i] for i in current_scene(state).npc_ids]
    return any(
        words & (set(re.findall(r"[a-z]+", f"{n.name} {n.role}".lower())) - _FILLER) for n in npcs
    )


def _aimed_at_someone(state: GameState, words: frozenset[str]) -> bool:
    """The line names a person standing here (or says "him", "her", "the man" with someone here)
    or a foe of the waiting offer (M31.1a V2)."""
    if words & foe_words(state) or _names_npc_here(state, words):
        return True
    here = [state.world.npcs[i] for i in current_scene(state).npc_ids]
    people = intent_phrases().lexicon["person_words"]
    return bool(words & people) and any(not n.dead for n in here)


def _said_after_cast(text: str, spell: SpellDef) -> bool:
    name = r"[\s-]+".join(re.escape(w) for w in spell.index.split("-"))
    low = text.lower().replace("'", "")
    return re.search(rf"\bcast(?:s|ing)?\s+(?:[a-z]+\s+){{0,2}}?{name}\b", low) is not None


def _plain_word_spell(spell: SpellDef) -> bool:
    """A utility spell with no dice or buff (Light, Mage Hand: M31.2a): its name is an everyday
    word ("I light the torch"), so it is cast only after a cast word ("I cast light on ...")."""
    return all(isinstance(e, LightSourceEffect | UtilityEffect) for e in spell.effects)


def _at_scene(found: Found, spell: SpellDef, named: bool) -> bool | None:
    """True: cast at the scene; False: aimed at heroes; None: the storyteller's. `named`: the
    spell's name was read as a ready spell's (no cast word needed)."""
    if strikes_creatures(spell) and _aimed_at_someone(found.state, found.words):
        return None
    if strikes_creatures(spell) or spell.targeting.kind in _SCENE_KINDS:
        return True if named or _said_after_cast(found.text, spell) else None
    if _plain_word_spell(spell) and not _said_after_cast(found.text, spell):
        return None
    return False


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


def _intent(found: Found, spell: SpellDef | None, named: bool) -> CastIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None or spell is None:
        return None
    scene = _at_scene(found, spell, named)
    if scene is None:
        return None
    if scene:
        return CastIntent(actor.id, spell.index, (), at_scene=True)
    targets = _targets(found, spell)
    return CastIntent(actor.id, spell.index, targets) if targets is not None else None


def _cast(found: Found) -> CastIntent | None:
    return _intent(found, _named_spell(found.words), named=False)


def _ready_named(found: Found) -> CastIntent | HealIntent | None:
    """M31.1a V2: a ready spell named without a cast word ("I murmur a healing word over Rook")
    is a cast of it; a healing spell is the typed-healing path."""
    actor = found.state.creatures.get(found.actor_id)
    said = said_name(tokens(found.text), ready_spells(actor)) if actor is not None else None
    spell = combat_registries().spells.find(said[0]) if said is not None else None
    if spell is None:
        return None
    if any(isinstance(e, HealEffect) for e in spell.effects):
        return heal_spell(found)
    return _intent(found, spell, named=True)


RESOLVERS: dict[str, Resolver] = {"cast_spell": _cast, "named_spell": _ready_named}
