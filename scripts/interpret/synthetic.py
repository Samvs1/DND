"""Named scenes for the interpretation eval (M38.1): small game states for typed lines that no
committed playtest fixture holds (the keyword router's trap sentences,
docs/next/m36_router_sentences.jsonl).

A scene starts from the state just before one typed line of a committed fixture run (real heroes
with real gear and spells) and, where the old router tests used a made-up fight, starts that fight
through the DM's own `start_encounter` tool and the reducer. Nothing is mutated by hand. The old
tests' states map to scenes as listed in `COVERS`.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolContext, ToolRegistries, tool_registries
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import dm_tool
from aidm.models.state import GameState
from aidm.rules.turns import begin_turn, end_turn
from aidm.session.reducer import apply
from scripts.interpret import lib


@dataclass
class Scene:
    name: str
    state: GameState
    actors: dict[str, str]  # a short role -> creature id, for the labeller's reference
    note: str


def _base(run: str, seq: int) -> GameState:
    """A private copy of the state just before typed line `seq` of fixture run `run`."""
    line = next(lib.walk(run, frozenset({seq})))
    return line.state.model_copy(deep=True)


def _start_fight(state: GameState, actor: str, monsters: list[str]) -> GameState:
    """The DM's start_encounter tool, its events applied through the reducer."""
    args = dm_tool("start_encounter").args_model.model_validate({"monster_ids": monsters})
    call = ToolCall("call_0", "start_encounter", args)
    result = execute_tool(state, call, ToolContext(actor_id=actor), random.Random(1), _regs())
    if result.error:
        raise ValueError(f"start_encounter {monsters}: {result.error}")
    for event in result.events:
        apply(state, event)
    return state


def _open_turn_of(state: GameState, hero: str) -> str:
    """Open turns (every other turn is ended unplayed) until `hero`'s turn is open."""
    rng = random.Random(2)
    for _ in range(12):
        for event in begin_turn(rng, state):
            apply(state, event)
        enc = state.encounter
        active = enc.active_id() if enc is not None else None
        if active == hero:
            return hero
        for event in end_turn(rng, state):
            apply(state, event)
    raise ValueError(f"{hero} gets no turn within 12 turns")


@cache
def _regs() -> ToolRegistries:
    return tool_registries()


def _village_explore() -> Scene:
    state = _base("m29-p2", 34)
    note = "explore at Ash Hollow, four heroes with their kit"
    return Scene("village_explore", state, {"fighter": "pc-p2", "rogue": "pc-p4"}, note)


def _zombie_fight() -> Scene:
    state = _start_fight(_base("m29-p2", 34), "pc-p2", ["zombie"])
    active = _open_turn_of(state, "pc-p2")
    note = "a zombie fight; Brienne holds a longsword and a light crossbow"
    return Scene("zombie_fight", state, {"active": active}, note)


def _goblin_fight() -> Scene:
    state = _start_fight(_base("m32-r5-typed", 32), "pc-p2", ["goblin"])
    active = _open_turn_of(state, "pc-p2")
    note = "a goblin fight at a crossing with the quest givers standing by"
    return Scene("goblin_fight", state, {"active": active}, note)


def _toll_fight() -> Scene:
    state = _base("m32-r5-typed", 72)
    note = "a fight at the toll; Tamsin (pc-p8, cleric, healing word) acts"
    return Scene("toll_fight", state, {"active": "pc-p8"}, note)


def _toll_offer() -> Scene:
    state = _base("m32-r5-typed", 61)
    note = "foes stand in the road and the party must choose fight, parley, escape or surprise"
    return Scene("toll_offer", state, {"fighter": "pc-p2"}, note)


def _downed_ally() -> Scene:
    state = _base("m32-r5-typed", 281)
    note = "Elowen (pc-p4) is down at 0 HP, Brienne (pc-p2) is hurt, no foes"
    return Scene("downed_ally", state, {"fighter": "pc-p2", "downed": "pc-p4"}, note)


def _merre_shop() -> Scene:
    state = _base("m31-r4-typed", 34)
    note = "Merre Wenslow's shop at Vossmoor; the party is in the shop's town"
    return Scene("merre_shop", state, {"fighter": "pc-p2", "rogue": "pc-p4"}, note)


SCENES: dict[str, Callable[[], Scene]] = {
    "village_explore": _village_explore,
    "zombie_fight": _zombie_fight,
    "goblin_fight": _goblin_fight,
    "toll_fight": _toll_fight,
    "toll_offer": _toll_offer,
    "downed_ally": _downed_ally,
    "merre_shop": _merre_shop,
}

# Which deleted router test files each scene stands in for (record: m36_router_sentences.jsonl).
COVERS: dict[str, tuple[str, ...]] = {
    "village_explore": (
        "tests/ai/test_precheck.py",
        "tests/ai/test_what_now_precheck.py",
        "tests/ai/test_item_tools.py",
        "tests/ai/test_use_intent.py",
        "tests/session/test_m31_typed_explore.py",
        "tests/session/test_m29_typed_intents.py",
        "tests/session/test_m30_free_spells.py",
        "tests/session/test_m31_utility_cantrips.py",
        "tests/ai/test_m30_intent_router.py",
        "tests/ai/test_quest_item_tools.py",
        "tests/session/test_quest_items_flow.py",
    ),
    "zombie_fight": (
        "tests/session/test_m32_typed_fight.py",
        "tests/session/test_m31_typed_fight.py",
    ),
    "goblin_fight": (
        "tests/ai/test_creative_gear.py",
        "tests/ai/test_m27_typed_gear.py",
        "tests/ai/test_combat_intent.py",
    ),
    "toll_fight": (
        "tests/session/test_m30_r3_intents.py",
        "tests/session/test_m29_r3_surrender.py",
    ),
    "toll_offer": ("tests/session/test_m32_typed_offer.py", "tests/session/test_m29_r3_offers.py"),
    "downed_ally": ("tests/ai/test_help_intent.py",),
    "merre_shop": (
        "tests/session/test_m29_r3_pay.py",
        "tests/session/test_m31_pay_path.py",
        "tests/session/test_m29_hand_over.py",
    ),
}


# Test files that replayed a committed playtest run: their lines are `run`+`seq` rows of the
# main corpus (or M38.2 adds them), so they need no scene.
REPLAYED: tuple[str, ...] = (
    "tests/ai/test_m29_honest_goods.py",
    "tests/ai/test_m29_locks_levels.py",
    "tests/session/test_m29_keepsake_hand_over.py",
    "tests/session/test_m29_r3_ending.py",
    "tests/session/test_m29_typed_gear_words.py",
    "tests/session/test_m29_typed_rest_feature.py",
    "tests/session/test_m31_quests.py",
    "tests/session/test_m31_typed_answers.py",
    "tests/session/test_m32_typed_compound.py",
    "tests/session/test_m33_typed_flow.py",
    "tests/session/test_m35_waiting_foe.py",
)


@cache
def _built(name: str) -> Scene:
    return SCENES[name]()


def scene(name: str) -> Scene:
    """The scene `name` as a private copy (the eval and the chooser may not share one state)."""
    if name not in SCENES:
        raise KeyError(f"no scene {name!r}; known: {', '.join(sorted(SCENES))}")
    built = _built(name)
    return Scene(built.name, built.state.model_copy(deep=True), dict(built.actors), built.note)
