"""Typed help for a downed ally outside a fight (M20.2, owner playtest 3: "I rouse Slendee" was
a Medicine check that changed nothing; the hero stayed at 0 HP until the next fight).

The phrase rows (`help_up` in data/bg3/intent_phrases.json: "help her up", "wake slendee", "get
slendee back on her feet", "stabilise him", "revive slendee") give the `who` slot; the resolver
returns a `HelpUpIntent` when it names a downed party member (alive at 0 HP) other than the
actor, or is a pronoun while exactly one is down. Anything else is None and goes on. The rules
decide (`aidm.rules.downed.help_up_events`).

Public API: `HelpUpIntent(actor_id, target_id)`, `RESOLVERS` (`help_up`).
"""

import re
from dataclasses import dataclass

from aidm.dm.intent_match import Found, Resolver
from aidm.models.state import Creature, GameState

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


def help_up(found: Found) -> HelpUpIntent | None:
    who = (found.group("who") or "").strip()
    downed = _downed(found.state, found.actor_id)
    if who in _PRONOUNS:
        return HelpUpIntent(found.actor_id, downed[0].id) if len(downed) == 1 else None
    wanted = _words(who)
    for hero in downed:
        have = _words(hero.name)
        if wanted and (wanted <= have or have <= wanted):
            return HelpUpIntent(found.actor_id, hero.id)
    return None


RESOLVERS: dict[str, Resolver] = {"help_up": help_up}
