"""Typed attacks and surrender demands while an encounter offer waits (M32.1a X3, X5, round 5).

X3 ("Rook shouts and lets fly an arrow at the bandit", "I cast Burning Hands at the violet
fungus", "I fling a scorching ray at the gnoll" only started the fight; no attack and no cast
followed while the story told the hit or the flame): the `offer_strike` phrase row (ranked
before the parley rows) hands a line that names a foe of the offer here, and the resolver
returns `OfferStrikeIntent` when the line strikes (a sneak or an ambush, the row's
`stealth_words` veto, stays the storyteller's surprise): a weapon the hero has (or a weapon kind,
`strike_intent.said_weapon`), a strike word of the lexicon's `strike_verbs`, or a harmful spell
the hero names (`spell_names.named_spell`, `rules.ai_spells.is_hostile_spell`; M35.2 Y9: or
`spell_targets.strikes_creatures`, so an HP pool such as Sleep counts). The session
starts the fight as the offer's Fight answer and plays the same line as the hero's own turn
(`session.offer_strike`). M33.1 (ultrareview 3): the words are read by position
(`dm.strike_words`): a weapon word only as a weapon ("my bow", not "I bow to the captain"), a
strike word only as the line's act (not "by the fire"), and a negated act or spell ("I won't
attack the bandit") strikes nothing, so a courtesy or a refusal never answers the offer as Fight.

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
from aidm.dm.intent_match import Found, Resolver
from aidm.dm.parley_intent import ParleyIntent
from aidm.dm.spell_names import named_spell
from aidm.dm.strike_intent import said_weapon
from aidm.dm.strike_words import marked, negated, strikes
from aidm.models.abilities import Skill
from aidm.models.state import Creature
from aidm.rules.ai_spells import is_hostile_spell
from aidm.rules.spell_targets import strikes_creatures
from aidm.rules.surrender import offer_never_yield_line


@dataclass(frozen=True)
class OfferStrikeIntent:
    actor_id: str


def _harmful_spell(actor: Creature, words: list[str]) -> bool:
    said = named_spell(actor, words)
    if said is None or negated(words, said[2][0]):
        return False
    if said[3]:  # a targeted ability (Turn Undead) aims at others
        return True
    spell = combat_registries().spells.find(said[0])  # M35.2 Y9: an HP pool (Sleep) harms too
    return spell is not None and (is_hostile_spell(spell) or strikes_creatures(spell))


def offer_strike(found: Found) -> OfferStrikeIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    words = marked(found.text)
    if strikes(words) or said_weapon(actor, words) is not None or _harmful_spell(actor, words):
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
