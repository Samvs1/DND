"""Typed casts in a fight (M31.1a V1, round 4: "I cast magic missile at the sahuagin" became a
model check and a "creative action" with no slot and no damage; "I call down sacred flame on the
zombie" a model save at DC 15 where the real DC is 12; Turn Undead a model save).

The `fight_cast` phrase row (data/bg3/intent_phrases.json, after the healing rows) gives the
line, read without the hero's own name. The resolver finds what it names, from data only:
- a ready spell of the hero (`dm.spell_names.ready_spells`) whose name words stand together in
  the line, with or without a cast word ("I call down sacred flame on X" casts it);
- else an active ability aimed at others (`targeted_features`: Turn Undead);
- else, when the line has a cast word, any spell of the registry it names: the rules then
  refuse it in plain words (not on the sheet, not prepared).
The targets come from the words after the name is cut out (`dm.fight_names`), by the spell's
own targeting:
- self: none; one creature: the first combatant named (a foe or a friend, "me" the caster);
  several creatures: every one named;
- an area or a point: the zone named, else the zone of the first combatant named; a self-ranged
  area with nothing named starts at the caster.
The result is the hotbar's own command (`CastCommand` / `FeatureActionCommand`), so the slot or
use is spent and the real attack or save is rolled at the real DC (the rules refuse it with
their reason: out of range, no slot). A line that names a spell but no valid target is refused
plainly (`RefusedIntent`): nothing is spent and no creative check is made.

Public API: `RefusedIntent(actor_id, text)`, `RESOLVERS` (`fight_cast`).
"""

from dataclasses import dataclass

from aidm.data.combat_data import combat_registries
from aidm.data.feature_hooks import ActiveAbilityHook
from aidm.data.intent_phrases import intent_phrases
from aidm.data.spell_defs import SpellDef
from aidm.dm.fight_names import Named, named_in_fight, tokens
from aidm.dm.intent_match import Found, Resolver
from aidm.dm.spell_names import Option, ready_spells, said_name, targeted_features
from aidm.models.commands import CastCommand, FeatureActionCommand
from aidm.models.state import Creature, GameState
from aidm.rules.feature_commands import ability_spell
from aidm.rules.features import command_hook

WHO = "Name who {name} is aimed at: a foe or a friend in this fight."
WHERE = "Name where {name} goes: a foe or a place on this battlefield."
UNKNOWN = "{name} has no effect the engine can run in a fight yet."

type _Aim = tuple[tuple[str, ...], str | None]


@dataclass(frozen=True)
class RefusedIntent:
    actor_id: str
    text: str


def _all_spells() -> list[Option]:
    return [(s.index, s.name) for s in combat_registries().chars.spells.all()]


def _feature_spell(actor: Creature, feature_id: str) -> SpellDef | None:
    hook = command_hook(actor, combat_registries().chars.features, feature_id)
    return ability_spell(hook, feature_id) if isinstance(hook, ActiveAbilityHook) else None


def _aim(state: GameState, enc_zone: str | None, spell: SpellDef, named: Named) -> _Aim | None:
    kind = spell.targeting.kind
    if kind == "self" or (spell.range.kind == "self" and spell.targeting.shape is None):
        return (), None
    if kind == "creature":
        return ((named.creatures[0],), None) if named.creatures else None
    if kind == "creatures":
        return (named.creatures, None) if named.creatures else None
    if named.zones:
        return (), named.zones[0]
    enc = state.encounter
    if named.creatures and enc is not None:
        return (), enc.combatants[named.creatures[0]].zone_id
    return ((), enc_zone) if spell.range.kind == "self" else None


def _command(
    found: Found, key: str, spell: SpellDef, aim: _Aim, feature: bool
) -> CastCommand | FeatureActionCommand:
    targets, zone = aim
    if feature:
        return FeatureActionCommand(
            actor_id=found.actor_id, feature_id=key, target_ids=targets, target_zone=zone
        )
    return CastCommand(actor_id=found.actor_id, spell_id=key, target_ids=targets, target_zone=zone)


def _said(actor: Creature, words: list[str]) -> tuple[str, str, tuple[int, int], bool] | None:
    said = said_name(words, ready_spells(actor))
    if said is not None:
        return (*said, False)
    feature = said_name(words, targeted_features(actor))
    if feature is not None:
        return (*feature, True)
    if not set(words) & intent_phrases().lexicon["cast_words"]:
        return None
    other = said_name(words, _all_spells())
    return (*other, False) if other is not None else None


def fight_cast(found: Found) -> CastCommand | FeatureActionCommand | RefusedIntent | None:
    actor = found.state.creatures.get(found.actor_id)
    enc = found.state.encounter
    if actor is None or actor.pc is None or enc is None or actor.id not in enc.combatants:
        return None
    words = tokens(found.text)
    said = _said(actor, words)
    if said is None:
        return None
    key, name, (start, end), feature = said
    spell = _feature_spell(actor, key) if feature else combat_registries().spells.find(key)
    if spell is None:
        return RefusedIntent(actor.id, UNKNOWN.format(name=name))
    named = named_in_fight(found.state, actor.id, [*words[:start], "", *words[end:]])
    aim = _aim(found.state, enc.combatants[actor.id].zone_id, spell, named)
    if aim is None:
        wanted = WHO if spell.targeting.kind in ("creature", "creatures") else WHERE
        return RefusedIntent(actor.id, wanted.format(name=name))
    return _command(found, key, spell, aim, feature)


RESOLVERS: dict[str, Resolver] = {"fight_cast": fight_cast}
