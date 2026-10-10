"""Typed moves in a fight (M19.4, owner playtest 2026-10-10: "I move to the ravine" was narrated but
nothing moved; free text in a fight only had check/effect tools).

`combat_move(state, actor_id, text)` turns a plain move sentence into the same commands the phone's
Move list sends: `MoveCommand(actor_id, zone_id)`, preceded by a `DashCommand` when the player said
dash or sprint and the walk needs it. The destination is a zone of the fight (by name words) or a
creature in it ("I run to Old Kern" goes to Old Kern's zone). Anything else is None, and the
sentence goes on to the creative action path as before. The rules still decide (distance, rough
ground, standing up): a refused move is answered like the button's refusal.

Public API: `combat_move(state, actor_id, text) -> list[MoveCommand | DashCommand] | None`.
"""

import re

from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.state import GameState
from aidm.rules.zones import zone_path

_MOVE = re.compile(
    r"^(?:please |ok |okay )?(?:(?:i|we)(?: will| shall|'ll| want to| would like to| try to)? |"
    r"let'?s )?(?P<verb>move|go|run|walk|step|head|dash|sprint|charge|rush|advance|retreat|"
    r"hurry|climb|jump down|descend|cross|make (?:my|our) way)"
    r"(?: (?:back|over|down|up|across|out|quickly))?"
    r"(?: (?:to|towards?|into|in to|onto|up to|over to|across to|down to|down into|at))?"
    r" (?:the )?(?P<dest>[a-z0-9' -]+?)(?: zone| area)?$"
)
_DASH_VERBS = frozenset({"dash", "sprint"})


def _words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", name.lower().replace("-", " "))) - {"the", "a"}


def _matches(wanted: frozenset[str], name: str) -> bool:
    have = _words(name)
    return bool(wanted) and bool(have) and (have <= wanted or wanted <= have)


def _destination(state: GameState, enc: Encounter, wanted: frozenset[str]) -> str | None:
    for zone in enc.zone_map.zones:
        if _matches(wanted, zone.name):
            return zone.id
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is not None and not creature.dead and _matches(wanted, creature.name):
            return combatant.zone_id
    return None


def combat_move(
    state: GameState, actor_id: str, text: str
) -> list[MoveCommand | DashCommand] | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE or actor_id not in enc.combatants:
        return None
    clean = " ".join(text.lower().replace("’", "'").split()).rstrip(".!?").strip()
    match = _MOVE.fullmatch(clean)
    if match is None:
        return None
    here = enc.combatants[actor_id]
    zone_id = _destination(state, enc, _words(match["dest"]))
    if zone_id is None or zone_id == here.zone_id:
        return None
    move = MoveCommand(actor_id=actor_id, zone_id=zone_id)
    path = zone_path(enc.zone_map, here.zone_id, zone_id)
    wants_dash = match["verb"] in _DASH_VERBS and not here.economy.dashed
    if wants_dash and path.feet > here.economy.movement_left:
        return [DashCommand(actor_id=actor_id), move]
    return [move]
