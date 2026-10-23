"""Typed feature use and typed healing in a fight (M29.5b: "Brienne uses Second Wind" got only
narration, p6 702; "I drink my potion" worked from the hotbar only). A deterministic precheck
like `aidm.dm.combat_intent`: the sentence becomes the SAME command the hotbar sends, so the
rules charge it exactly as the button would (action, bonus action, use, slot, draught) or refuse
it with their reason. Anything else is None and stays a creative action.

`fight_command(state, actor_id, text)`:
- M29.7a R22: a plain weapon attack on a foe ("I swing my longsword at Luth") ->
  `AttackCommand` with that weapon (`aidm.dm.attack_intent`), rolled against AC;
- a class or race feature the hotbar offers as a command (`rules.features.feature_actions`,
  `command=True`) whose name words all appear in the sentence and that aims at the hero itself
  (Second Wind, Action Surge...) -> `FeatureActionCommand`; the longest name wins. A feature
  aimed at others needs the board's target and stays on the hotbar;
- healing read by `aidm.dm.heal_intent` (the one reader of typed healing): a healing spell ->
  `CastCommand` (its targets), a healing draught the actor carries -> `UseItemCommand` on the
  hero it names (an ally's own draught cannot be reached mid-fight: None).

Public API: `fight_command(state, actor_id, text) -> FightCommand | None`.
"""

import re

from aidm.data.combat_data import combat_registries
from aidm.dm.attack_intent import typed_attack
from aidm.dm.heal_intent import heal_intent
from aidm.models.commands import (
    AttackCommand,
    CastCommand,
    FeatureActionCommand,
    UseItemCommand,
)
from aidm.models.encounter import EncounterStatus
from aidm.models.state import Creature, GameState
from aidm.rules.features import feature_actions

type FightCommand = AttackCommand | FeatureActionCommand | CastCommand | UseItemCommand


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower().replace("-", " ")))


def _feature(actor: Creature, words: set[str]) -> FeatureActionCommand | None:
    feats = combat_registries().chars.features
    named = [
        (len(_words(o.name)), o.feature)
        for o in feature_actions(actor, feats)
        if o.command and o.target_kind == "self" and o.name and _words(o.name) <= words
    ]
    if not named:
        return None
    return FeatureActionCommand(actor_id=actor.id, feature_id=max(named)[1])


def _healing(state: GameState, actor_id: str, clean: str) -> FightCommand | None:
    intent = heal_intent(state, actor_id, clean)
    if intent is None:
        return None
    if intent.spell is not None:
        return CastCommand(actor_id=actor_id, spell_id=intent.spell, target_ids=intent.target_ids)
    if intent.item is None or intent.owner_id != actor_id:
        return None
    return UseItemCommand(actor_id=actor_id, item=intent.item, target_id=intent.target_ids[0])


def fight_command(state: GameState, actor_id: str, text: str) -> FightCommand | None:
    enc = state.encounter
    actor = state.creatures.get(actor_id)
    if enc is None or enc.status is not EncounterStatus.ACTIVE or actor is None:
        return None
    if actor_id not in enc.combatants:
        return None
    attack = typed_attack(state, actor_id, text)
    if attack is not None:
        return attack
    clean = " ".join(text.lower().replace("’", "'").split()).rstrip(".!?").strip()
    feature = _feature(actor, _words(clean))
    return feature if feature is not None else _healing(state, actor_id, clean)
