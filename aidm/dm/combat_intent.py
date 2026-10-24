"""Typed moves in a fight (M19.4, owner playtest 2026-10-10: "I move to the ravine" was narrated but
nothing moved; free text in a fight only had check/effect tools).

The `move` phrase row (data/bg3/intent_phrases.json) reads a plain move sentence and the
resolver turns it into the same commands the phone's Move list sends: `MoveCommand(actor_id,
zone_id)`, preceded by a `DashCommand` when the player said dash or sprint (the lexicon's
`dash_verbs`) and the walk needs it. The destination is a zone of the fight (by name words) or
a creature in it ("I run to Old Kern" goes to Old Kern's zone). Anything else is None, and the
sentence goes on to the creative action path as before. The rules still decide (distance, rough
ground, standing up): a refused move is answered like the button's refusal.

Public API: `RESOLVERS` (`move`),
`combat_move(state, actor_id, text) -> list[MoveCommand | DashCommand] | None` (the move row).
"""

import re

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.intent_match import Found, Resolver, route
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.encounter import Encounter
from aidm.models.state import GameState
from aidm.rules.zones import zone_path

type MoveCommands = list[MoveCommand | DashCommand]


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


def move(found: Found) -> MoveCommands | None:
    enc = found.state.encounter
    if enc is None:
        return None
    here = enc.combatants[found.actor_id]
    zone_id = _destination(found.state, enc, _words(found.group("dest") or ""))
    if zone_id is None or zone_id == here.zone_id:
        return None
    step = MoveCommand(actor_id=found.actor_id, zone_id=zone_id)
    path = zone_path(enc.zone_map, here.zone_id, zone_id)
    dash = found.group("verb") in intent_phrases().lexicon["dash_verbs"]
    if dash and not here.economy.dashed and path.feet > here.economy.movement_left:
        return [DashCommand(actor_id=found.actor_id), step]
    return [step]


RESOLVERS: dict[str, Resolver] = {"move": move}


def combat_move(state: GameState, actor_id: str, text: str) -> MoveCommands | None:
    found = route(state, actor_id, text, RESOLVERS, families=("move",), base="as_is")
    return found if isinstance(found, list) else None
