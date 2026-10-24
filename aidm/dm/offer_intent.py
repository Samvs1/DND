"""Typed attacks and surrender demands while an encounter offer waits (M32.1a X3, X5, round 5).

X3 ("Rook shouts and lets fly an arrow at the bandit", "I cast Burning Hands at the violet
fungus", "I fling a scorching ray at the gnoll" only started the fight; no attack and no cast
followed while the story told the hit or the flame): the `offer_strike` phrase row (ranked
before the parley rows) hands a line that names a foe of the offer here, and the resolver
returns `OfferStrikeIntent` when the line strikes (a sneak or an ambush, the row's
`stealth_words` veto, stays the storyteller's surprise): a weapon the hero has (or a weapon kind,
`strike_intent.said_weapon`), a strike word of the lexicon's `strike_verbs`, or a harmful spell
the hero names (`spell_names.named_spell`, `rules.ai_spells.is_hostile_spell`). The session
starts the fight as the offer's Fight answer and plays the same line as the hero's own turn
(`session.offer_strike`).

X5 ("Drop your weapons and yield!" to a risen zombie rolled Intimidation and the story said it
obeyed): the `offer_surrender` row reads the surrender words; when every foe of the offer is a
kind that never yields the answer is the rules' plain line with no roll (`RefusedIntent`, the
offer still waits), else the demand is a parley with its row's skill (`ParleyIntent`, asked
first like every typed parley).

Public API: `OfferStrikeIntent(actor_id)`, `RESOLVERS` (`offer_strike`, `offer_surrender`).
"""

from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.dm.fight_cast_intent import RefusedIntent
from aidm.dm.fight_names import tokens
from aidm.dm.intent_match import Found, Resolver
from aidm.dm.parley_intent import ParleyIntent
from aidm.dm.spell_names import named_spell
from aidm.dm.strike_intent import said_weapon
from aidm.models.abilities import Skill
from aidm.models.state import Creature
from aidm.rules.ai_spells import is_hostile_spell
from aidm.rules.surrender import offer_never_yield_line


@dataclass(frozen=True)
class OfferStrikeIntent:
    actor_id: str


def _harmful_spell(actor: Creature, words: list[str]) -> bool:
    said = named_spell(actor, words)
    if said is None:
        return False
    if said[3]:  # a targeted ability (Turn Undead) aims at others
        return True
    spell = combat_registries().spells.find(said[0])
    return spell is not None and is_hostile_spell(spell)


def offer_strike(found: Found) -> OfferStrikeIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    words = tokens(found.text)
    plain = {w.removesuffix("'s") for w in words}
    strikes = bool(plain & intent_phrases().lexicon["strike_verbs"])
    if strikes or said_weapon(actor, words) is not None or _harmful_spell(actor, words):
        return OfferStrikeIntent(actor.id)
    return None


def offer_surrender(found: Found) -> RefusedIntent | ParleyIntent:
    line = offer_never_yield_line(found.state, combat_registries().monsters)
    if line is not None:
        return RefusedIntent(found.actor_id, line)
    kind = found.words & intent_phrases().lexicon["surrender_kind_words"]
    skill = Skill.PERSUASION if kind else Skill(str(found.params["skill"]))
    return ParleyIntent(found.actor_id, skill)


RESOLVERS: dict[str, Resolver] = {"offer_strike": offer_strike, "offer_surrender": offer_surrender}
