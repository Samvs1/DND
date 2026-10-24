"""Typed weapon attacks in a fight (M29.7a R22: "I swing my longsword at Mirrorwarden Luth" became
a creative action, a Strength check and a flat 2d6 with no roll against AC, and killed a master).

The `attack` phrase row (data/bg3/intent_phrases.json) reads a PLAIN weapon attack on a foe of
the fight and the resolver returns the SAME `AttackCommand` the hotbar sends, so armour class,
advantage, the weapon's own damage dice and the turn economy all apply (the rules refuse it with
their reason: out of reach, no attack left). The first of its forms that matches decides. Read
forms (the hero's own name with a third-person verb reads the same):
- "<verb> [at] <foe> [with my <weapon>]": attack, strike, hit, swing at, slash, stab, shoot ...;
- "<verb> my <weapon> at/into <foe>": swing, thrust, drive, fire, loose ...;
- M31.1a V3: "<verb> an arrow at <foe> [with my <weapon>]" (loose, fire, shoot, let fly: the
  ranged option), "jab <foe> in the ribs with my rapier" (a body part after the foe), and the
  longest verb first ("cut down the spider" is "cut down", never "cut" at "down the spider").
The foe is a living creature of the fight on another side whose name words fit the words said.
The weapon is the attack option (`rules.attack_profiles.attack_options`) whose name words fit
the weapon words; no weapon named: the ranged option for shoot / fire / loose (the lexicon's
`ranged_attack_verbs`), else the main hand. M30.0b T9 (round 3: "I stab the ice mephit with my
rapier" after `equip dagger` became a Dex check): a named weapon the hero carries but has stowed
is drawn as the free object interaction of the attack (`rules.equipment.draw_events`), then
attacks: `DrawAttack(item, attack)`. A named weapon the hero does not carry, or anything more
("swing from the chandelier into him", "kick the brazier at it") is None: it stays a creative
action.

Public API: `DrawAttack(item, attack)`, `RESOLVERS` (`attack`).
"""

import re
from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.dm.intent_match import Found, Resolver
from aidm.models.commands import AttackCommand
from aidm.models.encounter import Encounter
from aidm.models.state import Creature, GameState
from aidm.models.world_events import EquipmentChanged
from aidm.rules.attack_profiles import UNARMED_KEY, attack_options
from aidm.rules.equipment import EquipRefused, draw_events

_SMALL = frozenset({"the", "a", "an", "of", "my", "his", "her", "their", "our"})


@dataclass(frozen=True)
class DrawAttack:
    """A stowed weapon the hero carries, drawn for free, then the attack with it."""

    item: str
    attack: AttackCommand


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


def _option(actor: Creature, weapon: str | None, verb: str | None, ranged: bool) -> str | None:
    options = attack_options(actor, combat_registries().chars)
    if weapon is not None:
        wanted = _words(weapon)
        if wanted & {"fist", "fists", "unarmed"}:
            return UNARMED_KEY
        named = [o for o in options if o.key != UNARMED_KEY and _weapon_fits(wanted, o.name)]
        return named[0].key if named else None
    if ranged or verb in intent_phrases().lexicon["ranged_attack_verbs"]:
        return next((o.key for o in options if o.ranged), None)
    return "main_hand" if any(o.key == "main_hand" for o in options) else UNARMED_KEY


def _drawn_option(actor: Creature, item: str, wanted: frozenset[str]) -> str | None:
    """The attack option the carried weapon `item` gives once drawn (None: it cannot be)."""
    chars = combat_registries().chars
    try:
        events = draw_events(actor, item, chars)
    except EquipRefused:
        return None
    changed = next((e for e in events if isinstance(e, EquipmentChanged)), None)
    if changed is None or actor.pc is None:
        return None
    pc = actor.pc.model_copy(update={"equipped": changed.equipped})
    drawn = actor.model_copy(update={"pc": pc})
    options = attack_options(drawn, chars)
    named = [o for o in options if o.key != UNARMED_KEY and _weapon_fits(wanted, o.name)]
    return named[0].key if named else None


def _draw(actor: Creature, weapon: str) -> tuple[str, str] | None:
    """(item, option) of a carried, stowed weapon the words name."""
    if actor.pc is None:
        return None
    wanted = _words(weapon)
    equipment = combat_registries().chars.equipment
    for row in actor.pc.inventory:
        entry = equipment.find(row.item)
        if entry is None or entry.weapon_category is None or row.qty < 1:
            continue
        if not _weapon_fits(wanted, entry.name):
            continue
        option = _drawn_option(actor, row.item, wanted)
        if option is not None:
            return row.item, option
    return None


def attack(found: Found) -> AttackCommand | DrawAttack | None:
    enc = found.state.encounter
    actor = found.state.creatures.get(found.actor_id)
    if enc is None or actor is None or actor.pc is None:
        return None
    target = _foe(found.state, enc, found.actor_id, found.group("target") or "")
    if target is None:
        return None
    weapon = found.group("weapon")
    option = _option(actor, weapon, found.group("verb"), found.params.get("ranged") is True)
    if option is not None:
        return AttackCommand(actor_id=found.actor_id, target_id=target, option=option)
    drawn = _draw(actor, weapon) if weapon is not None else None
    if drawn is None:
        return None
    item, key = drawn
    return DrawAttack(item, AttackCommand(actor_id=found.actor_id, target_id=target, option=key))


RESOLVERS: dict[str, Resolver] = {"attack": attack}
