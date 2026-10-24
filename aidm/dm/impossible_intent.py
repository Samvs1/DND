"""A typed feat no body could do is impossible at once (M32.1a X8, round 5: "I lift the whole
thicket out of the ground and hurl it over the treetops" rolled Strength; M30 owner rule: an
impossible attempt rolls no dice, so no natural 20 rescues it).

The `impossible_feat` phrase row (data/bg3/intent_phrases.json, out of a fight and in one) reads a
lift or throw verb (lift, heave, hurl, uproot, pick up ...) whose object is a thing of the
`immovable` slot (a thicket, a bridge, a house, a hill ...): no person can lift or throw those.
Anything that is only hard (climbing a sheer wall, forcing a door, pushing a cart) or a throw of
something small somewhere big ("throw a rock into the river") has no such object and stays a
check. The resolver returns `ImpossibleIntent` with the row's reason; the
session logs the engine's `ActionImpossible` (no dice) and tells it failing.

Public API: `ImpossibleIntent(actor_id, text, reason)`, `RESOLVERS` (`impossible_feat`).
"""

from dataclasses import dataclass

from aidm.dm.intent_match import Found, Resolver
from aidm.models.impossible import MAX_IMPOSSIBLE_REASON, MAX_IMPOSSIBLE_TEXT


@dataclass(frozen=True)
class ImpossibleIntent:
    actor_id: str
    text: str
    reason: str


def impossible_feat(found: Found) -> ImpossibleIntent | None:
    if found.actor_id not in found.state.creatures:
        return None
    thing = found.group("thing")
    if not thing:
        return None
    reason = str(found.params["reason"]).format(thing=thing)[:MAX_IMPOSSIBLE_REASON]
    return ImpossibleIntent(found.actor_id, found.text[:MAX_IMPOSSIBLE_TEXT], reason)


RESOLVERS: dict[str, Resolver] = {"impossible_feat": impossible_feat}
