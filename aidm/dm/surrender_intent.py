"""A typed demand to surrender in a fight (M29.9a T12: "I lower my bow and call out for Sorrel Myn
and her cultists to surrender, they are beaten" won an Intimidation check that changed nothing).

The `surrender_*` phrase rows (data/bg3/intent_phrases.json): while a fight is on, a sentence
that asks the foes to give up ("surrender", "yield", "give up", "lay down / drop / throw down
your weapons or arms", "stand down") becomes ONE engine check (`aidm.rules.surrender`) with the
skill its row names: a word of the lexicon's `surrender_kind_words` (persuade, convince, plead,
reason, mercy, spare, offer, promise, quarter ...) -> Persuasion, ranked first; anything else
(a demand, a threat, a shout) -> Intimidation. The hero giving up ("I surrender", "we yield",
"I give up": the `self_surrender` veto) is not a demand and stays a creative action.

Its act type lives in `aidm.rules.acts_fight` (M36.1); this module only reads text.
Public API: `SurrenderIntent(actor_id, skill)`, `RESOLVERS` (`surrender`),
`surrender_intent(state, actor_id, text)` (the surrender rows).
"""

from aidm.dm.intent_match import Found, Resolver, route
from aidm.models.abilities import Skill
from aidm.models.state import GameState
from aidm.rules.acts_fight import SurrenderIntent


def surrender(found: Found) -> SurrenderIntent:
    return SurrenderIntent(found.actor_id, Skill(str(found.params["skill"])))


RESOLVERS: dict[str, Resolver] = {"surrender": surrender}


def surrender_intent(state: GameState, actor_id: str, text: str) -> SurrenderIntent | None:
    found = route(state, actor_id, text, RESOLVERS, families=("surrender",), base="as_is")
    return found if isinstance(found, SurrenderIntent) else None
