"""A typed search where something is hidden (M31.1a V9, round 4: "I search the ash-buried shelves
for a note ..." lit a candle and rolled nothing, so the hidden quest key was never found; elsewhere
a search failed against the storyteller's DC 15 and still found an item whose own DC is 10).
Pure: returns events.

`search_events(rng, state, creature_id, skill)`: ONE search check (`rules.gear_checks.gear_check`:
gear boons, darkness at disadvantage out of a fight) against the lowest discover DC of what is
hidden in the current place (`rules.scene.hidden_dc`), then what the total finds
(`rules.scene.discovery_events`, each thing at its own DC). A success always finds something and a
failure finds nothing, so the line can agree with the result. Refused (`ValueError`) when nothing
is hidden here: that search is the storyteller's.

`dc_tier(dc)`: the tier of a DC from the SRD table, None for a DC off the table.

Public API: `search_events`, `dc_tier`.
"""

from aidm.models.abilities import Skill
from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import GameState
from aidm.rules.checks import DC_BY_TIER
from aidm.rules.dice import Rng
from aidm.rules.gear_checks import gear_check
from aidm.rules.scene import discovery_events, hidden_dc

SEARCH_REASON = "search"


def dc_tier(dc: int) -> DcTier | None:
    return next((tier for tier, value in DC_BY_TIER.items() if value == dc), None)


def search_events(rng: Rng, state: GameState, creature_id: str, skill: Skill) -> list[AnyEvent]:
    dc = hidden_dc(state)
    if dc is None:
        raise ValueError("nothing is hidden here")
    creature = state.creatures[creature_id]
    result = gear_check(rng, state, creature, skill, dc).model_copy(update={"tier": dc_tier(dc)})
    events: list[AnyEvent] = [
        CheckResolved(creature_id=creature_id, result=result, reason=SEARCH_REASON)
    ]
    return events + list(discovery_events(state, creature_id, result))
