"""Typed feature use and typed healing in a fight (M29.5b: "Brienne uses Second Wind" got only
narration, p6 702; "I drink my potion" worked from the hotbar only). A deterministic precheck
like `aidm.dm.combat_intent`: the sentence becomes the SAME command the hotbar sends, so the
rules charge it exactly as the button would (action, bonus action, use, slot, draught) or refuse
it with their reason. Anything else is None and stays a creative action.

The fight rows of data/bg3/intent_phrases.json, in precedence order:
- `move` (`aidm.dm.combat_intent`): a typed move is the Move list's commands;
- `attack` (M29.7a R22): a plain weapon attack on a foe ("I swing my longsword at Luth") ->
  `AttackCommand` with that weapon (`aidm.dm.attack_intent`), rolled against AC;
- `feature`: a class or race feature the hotbar offers as a command
  (`rules.features.feature_actions`, `command=True`) whose name words all appear in the
  sentence and that aims at the hero itself (Second Wind, Action Surge...) ->
  `FeatureActionCommand`; the longest name wins. A feature aimed at others needs the board's
  target and stays on the hotbar;
- `fight_heal_*`: healing read by `aidm.dm.heal_intent` (the one reader of typed healing): a
  healing spell -> `CastCommand` (its targets), a healing draught the actor carries ->
  `UseItemCommand` on the hero it names (an ally's own draught cannot be reached mid-fight);
- `surrender_*` (`aidm.dm.surrender_intent`).

Public API: `FightCommand`, `RESOLVERS` (`feature`, `fight_heal_spell`, `fight_heal_item`),
`fight_command(state, actor_id, text) -> FightCommand | None` (the attack, feature and
healing rows).
"""

import re

from aidm.data.combat_data import combat_registries
from aidm.dm.attack_intent import RESOLVERS as ATTACK_RESOLVERS
from aidm.dm.heal_intent import HealIntent, heal_item, heal_spell
from aidm.dm.intent_match import Found, Resolver, route
from aidm.models.commands import (
    AttackCommand,
    CastCommand,
    FeatureActionCommand,
    UseItemCommand,
)
from aidm.models.state import GameState
from aidm.rules.features import feature_actions

type FightCommand = AttackCommand | FeatureActionCommand | CastCommand | UseItemCommand


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower().replace("-", " ")))


def feature(found: Found) -> FeatureActionCommand | None:
    actor = found.state.creatures.get(found.actor_id)
    if actor is None:
        return None
    feats = combat_registries().chars.features
    named = [
        (len(_words(o.name)), o.feature)
        for o in feature_actions(actor, feats)
        if o.command and o.target_kind == "self" and o.name and _words(o.name) <= found.words
    ]
    if not named:
        return None
    return FeatureActionCommand(actor_id=actor.id, feature_id=max(named)[1])


def _command(actor_id: str, intent: HealIntent | None) -> FightCommand | None:
    if intent is None:
        return None
    if intent.spell is not None:
        return CastCommand(actor_id=actor_id, spell_id=intent.spell, target_ids=intent.target_ids)
    if intent.item is None or intent.owner_id != actor_id:
        return None
    return UseItemCommand(actor_id=actor_id, item=intent.item, target_id=intent.target_ids[0])


def fight_heal_spell(found: Found) -> FightCommand | None:
    return _command(found.actor_id, heal_spell(found))


def fight_heal_item(found: Found) -> FightCommand | None:
    return _command(found.actor_id, heal_item(found))


RESOLVERS: dict[str, Resolver] = ATTACK_RESOLVERS | {
    "feature": feature,
    "fight_heal_spell": fight_heal_spell,
    "fight_heal_item": fight_heal_item,
}
_COMMANDS = (AttackCommand, FeatureActionCommand, CastCommand, UseItemCommand)


def fight_command(state: GameState, actor_id: str, text: str) -> FightCommand | None:
    families = ("attack", "feature", "fight_heal")
    found = route(state, actor_id, text, RESOLVERS, families=families, base="as_is")
    return found if isinstance(found, _COMMANDS) else None
