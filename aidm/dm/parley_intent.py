"""A typed talk-down while an encounter offer waits (M29.7a R4: "I call out to Hearthkeeper Veles
and ask whether he will let us pass" rolled a storyteller Persuasion check that passed, then the
parley rolled again and failed: two rolls for one act, the first counting for nothing).

While the campaign's encounter offer is open and lists parley, a sentence that talks to the foes
answers the offer as parley with the skill it names (one roll,
`aidm.rules.offer_answer.answer_offer`). The skill is data: the `parley_*` rows of
data/bg3/intent_phrases.json, in precedence order (intimidation words, then deception words or
"lie(s) to", then persuasion words, then the plain talking words -> Persuasion). The rows'
named conditions (`aidm.dm.intent_conditions`) keep out a sentence that names another hero or
the party, and (M29.9a T16) one that names an NPC standing here who is not among the offer's
foes, unless it also names a foe. Anything else is None (an attack, a sneak or a run is the
offer's other buttons, or the AI).

Public API: `ParleyIntent(actor_id, skill)`, `RESOLVERS` (`parley`).
"""

from dataclasses import dataclass

from aidm.dm.intent_match import Found, Resolver
from aidm.models.abilities import Skill


@dataclass(frozen=True)
class ParleyIntent:
    actor_id: str
    skill: Skill


def parley(found: Found) -> ParleyIntent:
    return ParleyIntent(found.actor_id, Skill(str(found.params["skill"])))


RESOLVERS: dict[str, Resolver] = {"parley": parley}
