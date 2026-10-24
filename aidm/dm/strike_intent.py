"""A typed line in a fight that names a weapon and a foe is that weapon's attack (M32.1a X1, round
5: "I run the thug through with my longsword", "I put an arrow in the zombie's chest", "Elowen
lets fly with her shortbow at the fungus" and "I hammer the Duke again with my longsword" were
creative checks that dealt flat damage with no roll against armour, or none at all while the
story told a kill).

ONE general rule, any verb: the `weapon_strike` phrase row (data/bg3/intent_phrases.json, after
the plain `attack` row, the casts and the surrender demands) hands the line here, and the line
is an attack when it names
- a living foe of the fight (`dm.fight_names.named_in_fight`: a word of its name, "the
  zombie's chest" too), and
- a weapon (`said_weapon`): the head word of one of the hero's attack options ("longsword",
  "shortbow", "crossbow"; M33.1: never another word of its name, "light" of "Crossbow, light"),
  else a weapon kind of the lexicon: a `weapon_ranged_words` word ("arrow", "bolt", "bow") is
  the ranged option, a `weapon_melee_words` word ("blade", "sword") the melee option whose name
  holds it ("sword" in Longsword), else the main hand; a named weapon the hero carries stowed
  is drawn first (`attack_intent.draw_attack`). M33.1 (ultrareview 3): a word counts only in a
  weapon reading (`dm.strike_words.as_weapon`: "my bow", "an arrow", "with a bow"), so "I bow to
  the goblin" is a courtesy, never a shot.
The result is the hotbar's own `AttackCommand` (or `DrawAttack`), so armour class, the weapon's
dice and the turn economy apply and the rules refuse it with their reason. The row's vetoes keep
real stunts creative: a shove or trip, a throw (the creative weapon rule throws it), sheathing
or showing a weapon; a named spell is never a weapon line (the `no_spell_named` condition).

Public API: `RESOLVERS` (`weapon_strike`), `said_weapon(actor, words) -> str | None` (the
attack option key the words name; the creative weapon rule asks it too), `head_word(name)`.
"""

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.dm.attack_intent import DrawAttack, draw_attack
from aidm.dm.fight_names import named_in_fight, tokens
from aidm.dm.intent_match import Found, Resolver
from aidm.dm.strike_words import marked, weapon_words
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.commands import AttackCommand
from aidm.models.state import Creature, GameState
from aidm.rules.attack_profiles import UNARMED_KEY, attack_options


def _options(actor: Creature) -> list[AttackProfile]:
    return [
        o
        for o in attack_options(actor, combat_registries().chars)
        if o.key != UNARMED_KEY and o.economy is AttackEconomy.ATTACK
    ]


def head_word(name: str) -> str:
    """The word that names the weapon: "Crossbow, light" -> "crossbow", "Light hammer" ->
    "hammer"."""
    words = tokens(name.partition(",")[0])
    return words[-1] if words else ""


def said_weapon(actor: Creature, words: list[str]) -> str | None:
    """The attack option the words name in a weapon reading: its head word, else a kind."""
    said = weapon_words(words)
    options = _options(actor)
    named = [o for o in options if head_word(o.name) in said]
    if named:
        return named[0].key
    lexicon = intent_phrases().lexicon
    if said & lexicon["weapon_ranged_words"]:
        return next((o.key for o in options if o.ranged), None)
    kinds = said & lexicon["weapon_melee_words"]
    if not kinds:
        return None
    melee = [o for o in options if not o.ranged]
    holding = [o for o in melee if any(k in w for k in kinds for w in tokens(o.name))]
    return (holding or melee)[0].key if melee else None


def _carried_weapon(actor: Creature, words: list[str]) -> str | None:
    """A word naming a weapon the hero carries but has not in hand ("my rapier" when stowed)."""
    if actor.pc is None:
        return None
    said = weapon_words(words)
    equipment = combat_registries().chars.equipment
    for row in actor.pc.inventory:
        entry = equipment.find(row.item)
        if entry is None or entry.weapon_category is None or row.qty < 1:
            continue
        if head_word(entry.name) in said:
            return head_word(entry.name)
    return None


def _foe(state: GameState, actor_id: str, words: list[str]) -> str | None:
    enc = state.encounter
    if enc is None or actor_id not in enc.combatants:
        return None
    side = enc.combatants[actor_id].side
    named = named_in_fight(state, actor_id, words).creatures
    foes = [c for c in named if enc.combatants[c].side is not side]
    return foes[0] if foes else None


def weapon_strike(found: Found) -> AttackCommand | DrawAttack | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None or actor.pc is None:
        return None
    target = _foe(found.state, actor.id, tokens(found.text))
    if target is None:
        return None
    words = marked(found.text)
    option = said_weapon(actor, words)
    if option is not None:
        return AttackCommand(actor_id=actor.id, target_id=target, option=option)
    stowed = _carried_weapon(actor, words)
    return draw_attack(actor, stowed, actor.id, target) if stowed is not None else None


RESOLVERS: dict[str, Resolver] = {"weapon_strike": weapon_strike}
