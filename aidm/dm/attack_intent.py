"""Typed weapon attacks in a fight (M29.7a R22: "I swing my longsword at Mirrorwarden Luth" became
a creative action, a Strength check and a flat 2d6 with no roll against AC, and killed a master).

`typed_attack(state, actor_id, text)` reads a PLAIN weapon attack on a foe of the fight and
returns the SAME `AttackCommand` the hotbar sends, so armour class, advantage, the weapon's own
damage dice and the turn economy all apply (the rules refuse it with their reason: out of
reach, no attack left). Read forms (the hero's own name with a third-person verb reads the same):
- "<verb> [at] <foe> [with my <weapon>]": attack, strike, hit, swing at, slash, stab, shoot ...;
- "<verb> my <weapon> at/into <foe>": swing, thrust, drive, fire, loose ...
The foe is a living creature of the fight on another side whose name words fit the words said.
The weapon is the attack option (`rules.attack_profiles.attack_options`) whose name words fit
the weapon words; no weapon named: the ranged option for shoot / fire / loose, else the main
hand. A named weapon that is no option of the hero (not in hand) or anything more ("swing from
the chandelier into him", "kick the brazier at it") is None: it stays a creative action.

Public API: `typed_attack(state, actor_id, text) -> AttackCommand | None`.
"""

import re

from aidm.data.combat_data import combat_registries
from aidm.dm.sentence import normalise, own_reading
from aidm.models.commands import AttackCommand
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.state import Creature, GameState
from aidm.rules.attack_profiles import UNARMED_KEY, attack_options

_MINE = r"(?:my|the|his|her|their|our)"
_NAME = r"[a-z0-9' ,-]+?"
_PLAIN = re.compile(
    r"(?P<verb>attack|strike|strike at|hit|swing at|slash|slash at|stab|stab at|cut|cut at|"
    r"hack at|chop at|lunge at|thrust at|smash|bash|shoot|shoot at|fire at|loose at) "
    rf"(?:the )?(?P<target>{_NAME})(?: with {_MINE} (?P<weapon>{_NAME}))?"
)
_SWING = re.compile(
    r"(?P<verb>swing|thrust|drive|bring down|slash|stab|jab|fire|shoot|loose|aim|point) "
    rf"{_MINE} (?P<weapon>{_NAME}) (?:at|into|toward|towards|against|on|down on) "
    rf"(?:the )?(?P<target>{_NAME})"
)
_RANGED_VERBS = frozenset({"shoot", "shoot at", "fire", "fire at", "loose", "loose at"})
_SMALL = frozenset({"the", "a", "an", "of", "my", "his", "her", "their", "our"})


def _words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9']+", text.lower().replace("-", " "))) - _SMALL


def _fits(wanted: frozenset[str], name: str) -> bool:
    have = _words(name)
    return bool(wanted) and bool(have) and (wanted <= have or have <= wanted)


def _foe(state: GameState, enc: Encounter, actor_id: str, phrase: str) -> str | None:
    side = enc.combatants[actor_id].side
    wanted = _words(phrase)
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or combatant.side is side:
            continue
        if combatant.withdrawn is None and _fits(wanted, creature.name):
            return cid
    return None


def _weapon_fits(wanted: frozenset[str], name: str) -> bool:
    """ "sword" fits a Longsword, "bow" a Shortbow: a said word inside a name word counts."""
    have = _words(name)
    return _fits(wanted, name) or any(w in h for w in wanted for h in have if len(w) > 2)


def _option(actor: Creature, weapon: str | None, verb: str) -> str | None:
    options = attack_options(actor, combat_registries().chars)
    if weapon is not None:
        wanted = _words(weapon)
        if wanted & {"fist", "fists", "unarmed"}:
            return UNARMED_KEY
        named = [o for o in options if o.key != UNARMED_KEY and _weapon_fits(wanted, o.name)]
        return named[0].key if named else None
    if verb in _RANGED_VERBS:
        return next((o.key for o in options if o.ranged), None)
    return "main_hand" if any(o.key == "main_hand" for o in options) else UNARMED_KEY


def typed_attack(state: GameState, actor_id: str, text: str) -> AttackCommand | None:
    enc = state.encounter
    actor = state.creatures.get(actor_id)
    if enc is None or enc.status is not EncounterStatus.ACTIVE or actor is None:
        return None
    if actor_id not in enc.combatants or actor.pc is None:
        return None
    clean = own_reading(actor.name, normalise(text))
    match = _PLAIN.fullmatch(clean) or _SWING.fullmatch(clean)
    if match is None:
        return None
    target = _foe(state, enc, actor_id, match["target"])
    if target is None:
        return None
    option = _option(actor, match["weapon"], match["verb"])
    if option is None:
        return None
    return AttackCommand(actor_id=actor_id, target_id=target, option=option)
