"""Fight acts: what a hero does in a fight, as frozen data and command plans (M36.1, moved from
`aidm.dm.attack_intent`, `surrender_intent`, `combat_intent`, `fight_intent` and `intent_router`;
SPEC 6.2). Pure types, no logic. The acts out of a fight are in `aidm.rules.acts`.

Public API:
- `DrawAttack(item, attack)`: a stowed weapon the hero carries, drawn for free, then the attack;
- `SurrenderIntent(actor_id, skill)`: a demand that the foes surrender (one engine check);
- `MoveCommands`: the move plan (`DashCommand` first when the walk needs it, then `MoveCommand`);
- `FightCommand`: an attack, feature action, cast or item use, the same commands the hotbar sends;
- `FightIntent`: the union of what a typed fight line can be.
"""

from dataclasses import dataclass

from aidm.models.abilities import Skill
from aidm.models.commands import (
    AttackCommand,
    CastCommand,
    DashCommand,
    FeatureActionCommand,
    MoveCommand,
    UseItemCommand,
)
from aidm.rules.acts import ImpossibleIntent, RefusedIntent


@dataclass(frozen=True)
class DrawAttack:
    """A stowed weapon the hero carries, drawn for free, then the attack with it."""

    item: str
    attack: AttackCommand


@dataclass(frozen=True)
class SurrenderIntent:
    actor_id: str
    skill: Skill


type MoveCommands = list[MoveCommand | DashCommand]
type FightCommand = AttackCommand | FeatureActionCommand | CastCommand | UseItemCommand
type FightIntent = (
    MoveCommands | FightCommand | DrawAttack | SurrenderIntent | RefusedIntent | ImpossibleIntent
)
