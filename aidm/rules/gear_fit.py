"""The scoped rope rule (M27.5, owner 2026-10-22; docs/next/GOAL_ITEMS.md "Design"). PURE.

Only in a situation the item table (data/bg3/item_uses.json) covers does an action naming a
carried item with no fitting use lose the AI's advantage on its check; elsewhere the AI's
judgment stands ("I tie up the goblin with my rope" gets a fair call). The situations come from
the `when`/skill pairs of the data, never from a per-item branch:
- a lock (`locked`): the check is aimed at a locked feature here; only `locked` uses whose
  unlock skill or ability is the check's cover it (a rope's climbing use does not);
- a dark place (`dark_place`): a search check (Perception, Investigation, WIS/INT) or a light's
  own skill in a dark place;
- a place use (`place`): climbing or crossing (Athletics), inspecting, scouting, disguise,
  performing... the use's skills, anywhere;
- a tagged place (`tagged_place`): its skill (Survival for fishing, trapping) where its tags
  match.
A keepsake (or anything that is not a catalogue item) has no use, so it never fits.

Public API: `covered(state, what, locked) -> bool`, `misfit(state, item, what, locked) -> bool`
(`item` a catalogue id; a keepsake passes its id, which has no uses).
"""

from aidm.data.item_uses import (
    Boon,
    ItemUse,
    LightPlace,
    Supplies,
    Unlock,
    item_use_data,
    uses_for_item,
)
from aidm.models.abilities import Ability, Skill
from aidm.models.state import GameState
from aidm.rules.light import place_dark
from aidm.rules.progression import node_plan
from aidm.rules.scene import is_search_check


def _skills(use: ItemUse) -> tuple[str, ...]:
    effect = use.effect
    match effect:
        case LightPlace() | Boon():
            return effect.skills
        case Unlock():
            return tuple(x for x in (effect.skill, effect.ability) if x)
        case Supplies():
            return (effect.skill,)
        case _:
            return ()


def _tagged(state: GameState, use: ItemUse) -> bool:
    plan = node_plan(state, state.world.current_node)
    tags = {t.strip().lower() for t in plan.terrain_tags} if plan is not None else set[str]()
    return bool(tags & set(use.tags))


def _covers(state: GameState, use: ItemUse, what: Skill | Ability, locked: bool) -> bool:
    named = what.value in _skills(use)
    if locked:
        return use.when == "locked" and named
    if use.when == "dark_place":
        return place_dark(state) and (named or is_search_check(what))
    if use.when == "tagged_place":
        return named and _tagged(state, use)
    return use.when == "place" and named


def covered(state: GameState, what: Skill | Ability, locked: bool) -> bool:
    return any(_covers(state, use, what, locked) for use in item_use_data().uses)


def misfit(state: GameState, item: str, what: Skill | Ability, locked: bool) -> bool:
    if not covered(state, what, locked):
        return False
    return not any(_covers(state, use, what, locked) for use in uses_for_item(item))
