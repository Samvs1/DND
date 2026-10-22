"""THE substance-weakness rule (M27.6, docs/next/GOAL_ITEMS.md "D: substances, not one-off items").

PURE: returns events. When a hit (a thrown item, or a creative effect that delivers a carried
item) brings substances to a creature, every row of data/bg3/weaknesses.json for that
creature's stat block (`Creature.monster_index`) and one of those substances deals its flat
damage through THE damage path (`rules.attacks.deal_damage`: immunities and resistances apply),
announced by a `DiceRolled` labelled with the trait (SRD 5.1 Fire Elemental, Water
Susceptibility: 1 cold damage per gallon of water splashed on it). Damage-type vulnerabilities and
resistances are not substances: they stay in the damage path.

Public API: `weak_to(state, target_id, substances) -> list[(substance, WeaknessEffect)]`,
`substance_weakness_events(rng, state, actor_id, target_id, substances, feats)
-> list[AnyEvent]`.
"""

from collections.abc import Sequence

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.data.weakness_defs import WeaknessEffect, weaknesses_of
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import RollKind
from aidm.models.events import AnyEvent, DiceRolled
from aidm.models.state import GameState
from aidm.rules.attacks import deal_damage
from aidm.rules.dice import Rng, roll
from aidm.rules.projection import project_state


def weak_to(
    state: GameState, target_id: str, substances: Sequence[str]
) -> list[tuple[str, WeaknessEffect]]:
    target = state.creatures.get(target_id)
    if target is None or target.dead:
        return []
    rows = weaknesses_of(target.monster_index)
    return [(s, rows[s]) for s in dict.fromkeys(substances) if s in rows]


def substance_weakness_events(
    rng: Rng,
    state: GameState,
    actor_id: str,
    target_id: str,
    substances: Sequence[str],
    feats: Registry[FeatureDef],
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for _, effect in weak_to(state, target_id, substances):
        after = project_state(state, events)
        if after.creatures[target_id].dead:
            break
        rolled = roll(str(effect.amount), rng)
        events.append(
            DiceRolled(
                roll=rolled,
                roller_id=actor_id,
                label=effect.trait,
                kind=RollKind.DAMAGE,
                target_id=target_id,
            )
        )
        packet = DamagePacket(amount=rolled.total, damage_type=DamageType(effect.damage_type))
        events.extend(
            deal_damage(rng, after, actor_id, target_id, [packet], crit=False, feats=feats)
        )
    return events
