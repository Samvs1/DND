"""A typed talk-down while an encounter offer waits (M29.7a R4: "I call out to Hearthkeeper Veles
and ask whether he will let us pass" rolled a storyteller Persuasion check that passed, then the
parley rolled again and failed: two rolls for one act, the first counting for nothing).

`parley_intent(state, actor_id, clean)`: while the campaign's encounter offer is open and lists
parley, a sentence that talks to the foes answers the offer as parley with the skill it names
(one roll, `aidm.rules.offer_answer.answer_offer`):
- intimidate, threaten, menace, scare, frighten, bully, demand, warn ... -> Intimidation;
- deceive, lie to, bluff, trick, fool, pretend, feign, mislead -> Deception ("lie low" is not);
- persuade, convince, plead, reason, negotiate, parley, bargain, beg, appeal, calm, soothe,
  and the plain talking words (talk, speak, ask, call out, hail, greet, shout, tell, say) ->
  Persuasion. A sentence that names another hero ("I ask Elowen what she thinks", "I warn Rook")
  or the party ("I tell the others to get ready") is not a parley.
Anything else is None (an attack, a sneak or a run is the offer's other buttons, or the AI).

Public API: `ParleyIntent(actor_id, skill)`, `parley_intent(state, actor_id, clean)`.
"""

import re
from dataclasses import dataclass

from aidm.models.abilities import Skill
from aidm.models.campaign_state import OfferChoice
from aidm.models.state import CreatureKind, GameState

_SKILL_WORDS: tuple[tuple[Skill, frozenset[str]], ...] = (
    (
        Skill.INTIMIDATION,
        frozenset(
            {"intimidate", "intimidates", "threaten", "threatens", "menace", "menaces", "scare"}
            | {"scares", "frighten", "frightens", "bully", "bullies", "demand", "demands", "warn"}
            | {"warns", "intimidation", "cow", "cows"}
        ),
    ),
    (
        Skill.DECEPTION,
        frozenset(
            {"deceive", "deceives", "bluff", "bluffs", "trick", "tricks", "fool", "fools"}
            | {"pretend", "pretends", "feign", "feigns", "deception", "mislead", "misleads"}
        ),
    ),
    (
        Skill.PERSUASION,
        frozenset(
            {"persuade", "persuades", "convince", "convinces", "plead", "pleads", "reason"}
            | {"reasons", "negotiate", "negotiates", "parley", "parleys", "bargain", "bargains"}
            | {"beg", "begs", "appeal", "appeals", "calm", "calms", "soothe", "soothes"}
            | {"persuasion", "diplomacy"}
        ),
    ),
)
_TALK = frozenset(
    {"talk", "talks", "speak", "speaks", "ask", "asks", "call", "calls", "hail", "hails", "greet"}
    | {"greets", "shout", "shouts", "tell", "tells", "say", "says", "address", "addresses"}
)


@dataclass(frozen=True)
class ParleyIntent:
    actor_id: str
    skill: Skill


_OWN_SIDE = frozenset({"everyone", "others", "party", "friends", "companions", "allies", "group"})


def _names_a_friend(state: GameState, actor_id: str, words: set[str]) -> bool:
    return bool(words & _OWN_SIDE) or any(
        c.kind is CreatureKind.PC and c.id != actor_id and c.name.lower().split()[0] in words
        for c in state.creatures.values()
    )


def parley_intent(state: GameState, actor_id: str, clean: str) -> ParleyIntent | None:
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    if offer is None or OfferChoice.PARLEY not in offer.options or actor_id not in state.creatures:
        return None
    words = set(re.findall(r"[a-z]+", clean))
    if _names_a_friend(state, actor_id, words):
        return None
    if re.search(r"\blies? to\b", clean):
        words.add("deceive")
    for skill, said in _SKILL_WORDS:
        if words & said:
            return ParleyIntent(actor_id, skill)
    return ParleyIntent(actor_id, Skill.PERSUASION) if words & _TALK else None
