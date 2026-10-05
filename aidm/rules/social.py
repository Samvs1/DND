"""NPC attitude: capped and floored social contribution plus uncapped deeds (SPEC 6.3, 9).

v1 failure (docs/V1_LESSONS.md): failed social checks drove relationships unboundedly negative,
and talk alone could make an ally. Here the score is DERIVED, never accumulated directly:

    talk  = base + social              social is kept within [SOCIAL_FLOOR, SOCIAL_CAP]
    talk  = min(talk, max(base, ALLY_BAR - 1))   talk alone never crosses the ally bar
    score = clamp(talk + deeds, SCORE_MIN, SCORE_MAX)

So many failed rolls lower the score at most `-SOCIAL_FLOOR` below the base (an indifferent NPC
ends unfriendly, never hostile), and only deeds (`deed_attitude_events`, e.g. a completed quest
for the NPC) reach ALLY. Hostility from violence is the separate `hostile` flag.

Public API:
- Constants: `SCORE_MIN`, `SCORE_MAX`, `ALLY_BAR`, `FRIENDLY_BAR`, `UNFRIENDLY_BAR`,
  `HOSTILE_BAR`, `SOCIAL_CAP`, `SOCIAL_FLOOR`, `DELTA_POINTS` (points per `DeltaTier`).
- `attitude_score(npc) -> int`, `attitude_band(score) -> AttitudeBand`,
  `npc_is_hostile(npc) -> bool` (flagged hostile, or the HOSTILE band).
- `social_attitude_events(npc, delta, reason) -> list[AnyEvent]`: one `AttitudeChanged` with the
  clamped social contribution (empty when nothing changes).
- `deed_attitude_events(npc, points, reason) -> list[AnyEvent]`: deeds add `points` (uncapped).
- `hostile_attitude_events(npc, reason) -> list[AnyEvent]`: the NPC becomes hostile.
"""

from aidm.models.dm_tiers import AttitudeBand, DeltaTier
from aidm.models.events import AnyEvent
from aidm.models.world import WorldNpc
from aidm.models.world_events import AttitudeChanged

SCORE_MIN = -100
SCORE_MAX = 100
ALLY_BAR = 50
FRIENDLY_BAR = 15
UNFRIENDLY_BAR = -15
HOSTILE_BAR = -50
SOCIAL_CAP = 40
SOCIAL_FLOOR = -25

DELTA_POINTS: dict[DeltaTier, int] = {
    DeltaTier.WORSEN_MAJOR: -20,
    DeltaTier.WORSEN: -10,
    DeltaTier.WORSEN_SLIGHT: -5,
    DeltaTier.IMPROVE_SLIGHT: 5,
    DeltaTier.IMPROVE: 10,
    DeltaTier.IMPROVE_MAJOR: 20,
}


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def attitude_score(npc: WorldNpc) -> int:
    talk = npc.base + _clamp(npc.social, SOCIAL_FLOOR, SOCIAL_CAP)
    talk = min(talk, max(npc.base, ALLY_BAR - 1))
    return _clamp(talk + npc.deeds, SCORE_MIN, SCORE_MAX)


def attitude_band(score: int) -> AttitudeBand:
    if score <= HOSTILE_BAR:
        return AttitudeBand.HOSTILE
    if score <= UNFRIENDLY_BAR:
        return AttitudeBand.UNFRIENDLY
    if score < FRIENDLY_BAR:
        return AttitudeBand.INDIFFERENT
    if score < ALLY_BAR:
        return AttitudeBand.FRIENDLY
    return AttitudeBand.ALLY


def npc_is_hostile(npc: WorldNpc) -> bool:
    return npc.hostile or attitude_band(attitude_score(npc)) is AttitudeBand.HOSTILE


def _changed(npc: WorldNpc, social: int, deeds: int, hostile: bool, reason: str) -> list[AnyEvent]:
    if (social, deeds, hostile) == (npc.social, npc.deeds, npc.hostile):
        return []
    return [
        AttitudeChanged(npc_id=npc.id, social=social, deeds=deeds, hostile=hostile, reason=reason)
    ]


def social_attitude_events(npc: WorldNpc, delta: DeltaTier, reason: str) -> list[AnyEvent]:
    social = _clamp(npc.social + DELTA_POINTS[delta], SOCIAL_FLOOR, SOCIAL_CAP)
    return _changed(npc, social, npc.deeds, npc.hostile, reason)


def deed_attitude_events(npc: WorldNpc, points: int, reason: str) -> list[AnyEvent]:
    return _changed(npc, npc.social, npc.deeds + points, npc.hostile, reason)


def hostile_attitude_events(npc: WorldNpc, reason: str) -> list[AnyEvent]:
    return _changed(npc, npc.social, npc.deeds, True, reason)
