"""The one intent router (M30.0b, owner 2026-10-23): every typed sentence that is not a button
goes through here before the storyteller sees it.

It joins the resolvers of every intent (each `aidm.dm.*_intent` module keeps only its state
lookups and exports `RESOLVERS`) and routes a sentence through the phrase table
(data/bg3/intent_phrases.json, read by `aidm.dm.intent_match`) for one scope:
- `explore_intent` (scope `explore`, out of a fight: help up, parley, rests, look, inventory,
  lift, give, pay, hand, heal, cast, shop, travel, locked ways, equip, gear use, take);
- `fight_intent` (scope `fight`: move, attack, feature, healing, M31.1a casts of ready spells
  and targeted features, surrender);
- `ask_intent` (scope `ask`: "what now?", unless the line helps a downed hero up).
Which intent wins is the rows' `precedence` field, never call order; the conditions a row
needs are named in the table and evaluated in `aidm.dm.intent_conditions`.

Public API: `RESOLVERS`, `FightIntent`, `explore_intent`, `fight_intent`, `ask_intent` (each
`(state, actor_id, text)`; None when no row resolves).
"""

from aidm.dm import (
    cast_intent,
    combat_intent,
    equip_intent,
    fight_cast_intent,
    give_intent,
    hand_intent,
    heal_intent,
    help_intent,
    lift_intent,
    parley_intent,
    pay_intent,
    scene_intent,
    surrender_intent,
    use_intent,
)
from aidm.dm import (
    fight_intent as fight_rows,
)
from aidm.dm.attack_intent import DrawAttack
from aidm.dm.combat_intent import MoveCommands
from aidm.dm.fight_cast_intent import RefusedIntent
from aidm.dm.fight_intent import FightCommand
from aidm.dm.intent_match import Resolver, route
from aidm.dm.surrender_intent import SurrenderIntent
from aidm.models.commands import AttackCommand, CastCommand, FeatureActionCommand, UseItemCommand
from aidm.models.state import GameState

type FightIntent = MoveCommands | FightCommand | DrawAttack | SurrenderIntent | RefusedIntent
_FIGHT = (
    list,
    RefusedIntent,
    SurrenderIntent,
    DrawAttack,
    AttackCommand,
    FeatureActionCommand,
    CastCommand,
    UseItemCommand,
)

RESOLVERS: dict[str, Resolver] = {}
for _module in (
    cast_intent,
    combat_intent,
    equip_intent,
    fight_cast_intent,
    fight_rows,
    give_intent,
    hand_intent,
    heal_intent,
    help_intent,
    lift_intent,
    parley_intent,
    pay_intent,
    scene_intent,
    surrender_intent,
    use_intent,
):
    _clash = set(RESOLVERS) & set(_module.RESOLVERS)
    if _clash:
        raise RuntimeError(f"intent resolver named twice: {sorted(_clash)}")
    RESOLVERS |= _module.RESOLVERS


def explore_intent(state: GameState, actor_id: str, text: str) -> object | None:
    return route(state, actor_id, text, RESOLVERS, scope="explore")


def fight_intent(state: GameState, actor_id: str, text: str) -> FightIntent | None:
    found = route(state, actor_id, text, RESOLVERS, scope="fight")
    return found if isinstance(found, _FIGHT) else None


def ask_intent(state: GameState, actor_id: str, text: str) -> object | None:
    return route(state, actor_id, text, RESOLVERS, scope="ask")
