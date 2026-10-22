"""Gear boons (GOAL_ITEMS "engine-owned advantage from gear", M27.3). PURE lookups.

A boon (`World.boons`, gained through `aidm.rules.item_use`) gives its hero advantage on every
check of a listed skill, or on saves against listed harms, whatever the AI asked; `adv_why`
names it (*Magnifying glass*, *Rope*). A "place" boon counts only in the place it was gained
(the reducer drops it on `PartyMoved`); an "until_long_rest" boon until the long rest, which
ends it with `BoonEnded` (`long_rest_boon_events`). Advantage never stacks (`rules.d20`).
The long rest also ends every carried light (`LightEnded`, `long_rest_light_events`, M27.12);
it lives here, not in `aidm.rules.light`, because `rules.light` imports through `rules.rests`.

Checks apply them through `aidm.rules.gear_checks.gear_check`; saves against a harm through the
spell effect interpreter's save tags (`save_boon_names`, next to features like Dwarven
Resilience).

Public API: `hero_boons(state, creature_id)`, `skill_boons(state, creature_id, skill)`,
`save_boon_names(state, creature_id, tags)`, `boon_adds_nothing(state, boon)`,
`long_rest_boon_events(state)`, `long_rest_light_events(state)`.
"""

from collections.abc import Collection

from aidm.models.abilities import Skill
from aidm.models.events import AnyEvent
from aidm.models.item_events import BoonEnded, LightEnded
from aidm.models.state import GameState
from aidm.models.world import ActiveBoon


def _active(state: GameState, boon: ActiveBoon) -> bool:
    return boon.scope != "place" or boon.node == state.world.current_node


def hero_boons(state: GameState, creature_id: str) -> list[ActiveBoon]:
    return [b for b in state.world.boons if b.creature_id == creature_id and _active(state, b)]


def skill_boons(state: GameState, creature_id: str, skill: Skill | None) -> list[ActiveBoon]:
    if skill is None:
        return []
    return [b for b in hero_boons(state, creature_id) if skill.value in b.skills]


def save_boon_names(state: GameState, creature_id: str, tags: Collection[str]) -> tuple[str, ...]:
    boons = hero_boons(state, creature_id)
    return tuple(dict.fromkeys(b.name for b in boons if any(t in tags for t in b.saves_against)))


def boon_adds_nothing(state: GameState, boon: ActiveBoon) -> bool:
    """The hero's boons already cover every skill and save of `boon` (advantage never stacks)."""
    held = hero_boons(state, boon.creature_id)
    skills = {s for b in held for s in b.skills}
    saves = {s for b in held for s in b.saves_against}
    return set(boon.skills) <= skills and set(boon.saves_against) <= saves


def long_rest_boon_events(state: GameState) -> list[AnyEvent]:
    return [
        BoonEnded(creature_id=b.creature_id, use_id=b.use_id, reason="long rest")
        for b in state.world.boons
        if b.scope == "until_long_rest"
    ]


def long_rest_light_events(state: GameState) -> list[AnyEvent]:
    return [
        LightEnded(creature_id=light.creature_id, reason="long rest")
        for light in state.world.lights
    ]
