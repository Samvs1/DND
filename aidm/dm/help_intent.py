"""Typed help for a downed ally outside a fight (M20.2, owner playtest 3: "I rouse Slendee" was
a Medicine check that changed nothing; the hero stayed at 0 HP until the next fight).

`help_up_intent(state, actor_id, clean)` reads the precheck's normalised sentence ("help her up",
"wake slendee", "get slendee back on her feet", "stabilise him", "revive slendee") and returns a
`HelpUpIntent` when it names a downed party member (alive at 0 HP) other than the actor, or uses a
pronoun while exactly one is down. Anything else is None and goes on to the adjudicator. The
rules decide (`aidm.rules.downed.help_up_events`).

Public API: `HelpUpIntent(actor_id, target_id)`, `help_up_intent(state, actor_id, clean)`.
"""

import re
from dataclasses import dataclass

from aidm.models.state import Creature, GameState

_WHO = r"([a-z0-9' -]+?)"
_FEET = r"(?: (?:back )?(?:up|on (?:to )?(?:her|his|their) feet|to (?:her|his|their) feet))"
_HELP = re.compile(
    rf"(?:try to |attempt to )?(?:"
    rf"(?:help|get|pull|lift|haul|heave|raise) (?:up )?{_WHO}{_FEET}|"
    rf"(?:help|pull|lift|haul) up {_WHO}|"
    rf"(?:wake|rouse|revive|stabili[sz]e|bring round|bring around) (?:up )?{_WHO}(?: up| round)?|"
    rf"bring {_WHO} (?:round|around|to)"
    rf")"
)
_PRONOUNS = frozenset({"her", "him", "them", "my friend", "my ally", "our friend", "our ally"})


@dataclass(frozen=True)
class HelpUpIntent:
    actor_id: str
    target_id: str


def _words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", name.lower().replace("’", "'"))) - {"the"}


def _downed(state: GameState, actor_id: str) -> list[Creature]:
    return [
        c
        for c in state.creatures.values()
        if c.pc is not None and not c.dead and c.hp <= 0 and c.id != actor_id
    ]


def help_up_intent(state: GameState, actor_id: str, clean: str) -> HelpUpIntent | None:
    match = _HELP.fullmatch(clean)
    if match is None:
        return None
    who = next(g for g in match.groups() if g is not None).strip()
    downed = _downed(state, actor_id)
    if who in _PRONOUNS:
        return HelpUpIntent(actor_id, downed[0].id) if len(downed) == 1 else None
    wanted = _words(who)
    for hero in downed:
        have = _words(hero.name)
        if wanted and (wanted <= have or have <= wanted):
            return HelpUpIntent(actor_id, hero.id)
    return None
