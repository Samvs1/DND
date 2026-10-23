"""A typed demand to surrender in a fight (M29.9a T12: "I lower my bow and call out for Sorrel Myn
and her cultists to surrender, they are beaten" won an Intimidation check that changed nothing).

`surrender_intent(state, actor_id, text)`: while a fight is on, a sentence that asks the foes to
give up ("surrender", "yield", "give up", "lay down / drop / throw down your weapons or arms",
"stand down", "accept their surrender") becomes ONE engine check (`aidm.rules.surrender`) with
the skill it names: persuade, convince, plead, reason, mercy, spare, offer, promise, quarter
-> Persuasion; anything else (a demand, a threat, a shout) -> Intimidation. The hero giving up
("I surrender", "we yield", "I give up") is not a demand and stays a creative action.

Public API: `SurrenderIntent(actor_id, skill)`, `surrender_intent(state, actor_id, text)`.
"""

import re
from dataclasses import dataclass

from aidm.models.abilities import Skill
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState

_ASK = re.compile(
    r"\b(surrender|yield|give up|stand down|"
    r"(lay|put|drop|throw|cast) down (your|their|his|her|the) (weapons?|arms|blades?)|"
    r"(drop|lower) (your|their|his|her) (weapons?|arms|blades?))\b"
)
_SELF = re.compile(r"^(i|we|let us|let's)( all)? (surrender|yield|give up)\b")
_KIND = frozenset(
    {"persuade", "persuades", "convince", "convinces", "plead", "pleads", "reason", "reasons"}
    | {"mercy", "spare", "spares", "offer", "offers", "promise", "promises", "quarter"}
    | {"kindly", "gently", "calmly"}
)


@dataclass(frozen=True)
class SurrenderIntent:
    actor_id: str
    skill: Skill


def surrender_intent(state: GameState, actor_id: str, text: str) -> SurrenderIntent | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE or actor_id not in enc.combatants:
        return None
    clean = " ".join(text.lower().replace("’", "'").split()).strip(" .!?")
    actor = state.creatures.get(actor_id)
    name = actor.name.lower() if actor is not None else ""
    for prefix in (name, name.split()[0] if name else ""):
        if prefix and clean.startswith(f"{prefix} "):
            clean = clean[len(prefix) + 1 :]
            break
    if _SELF.search(clean) or not _ASK.search(clean):
        return None
    words = set(re.findall(r"[a-z]+", clean))
    return SurrenderIntent(actor_id, Skill.PERSUASION if words & _KIND else Skill.INTIMIDATION)
