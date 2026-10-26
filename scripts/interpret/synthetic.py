"""Named scenes for the interpretation eval (M38.1): small game states for typed lines that no
committed playtest fixture holds (the keyword router's trap sentences,
docs/next/m36_router_sentences.jsonl).

A scene starts from the state just before one typed line of a committed fixture run (real heroes
with real gear and spells) and, where the old router tests used a made-up fight, starts that fight
through the DM's own `start_encounter` tool and the reducer. Nothing is mutated by hand. The old
tests' states map to scenes as listed in `COVERS`.

M38.2 adds variants for the record's lines: another hero's turn in a fight (`_open_turn_of`, the
turns before it ended unplayed), a hero who joins between scenes (`synthetic_join`), a pouch
dropped through the drop rules, and the real fixture states some old tests replayed (the vault
door, the dark wharf, the ferry, Glimmerwharf).
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
from aidm.rules.equipment import drop_events
from aidm.rules.turns import begin_turn, end_turn
from aidm.session.reducer import apply
from scripts.interpret import lib
from scripts.interpret.synthetic_join import JOINED_ID, join_cleric


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
        enc = state.encounter
        if enc is not None and enc.turn_open:
            if enc.active_id() == hero:
                return hero
            for event in end_turn(rng, state):
                apply(state, event)
        for event in begin_turn(rng, state):
            apply(state, event)
        enc = state.encounter
        if enc is not None and enc.turn_open and enc.active_id() == hero:
            return hero
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


def _toll_turn(hero: str, name: str, note: str) -> Scene:
    state = _base("m32-r5-typed", 72)
    return Scene(name, state, {"active": _open_turn_of(state, hero)}, note)


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


def _zombie_fight_rook() -> Scene:
    state = _start_fight(_base("m29-p2", 34), "pc-p6", ["zombie"])
    active = _open_turn_of(state, "pc-p6")
    note = "the zombie fight on Rook's turn (rogue: shortbow, oil flasks)"
    return Scene("zombie_fight_rook", state, {"active": active}, note)


def _caster_explore() -> Scene:
    state = _base("m29-p2", 34)
    joined = join_cleric(state)
    note = "Ash Hollow with Corin (pc-p10), a joined cleric: Light, Mending, Mage Hand"
    return Scene("caster_explore", state, {"caster": joined}, note)


def _caster_fight() -> Scene:
    state = _base("m29-p2", 34)
    join_cleric(state)
    state = _start_fight(state, JOINED_ID, ["zombie"])
    active = _open_turn_of(state, JOINED_ID)
    note = "a zombie fight on Corin's turn: Light ready, a light crossbow in hand"
    return Scene("caster_fight", state, {"active": active}, note)


def _village_pouch() -> Scene:
    state = _base("m29-p2", 34)
    for event in drop_events(state, state.creatures["pc-p6"], "pouch", lib.regs().chars):
        apply(state, event)
    note = "Ash Hollow; Rook has dropped his pouch on the ground"
    return Scene("village_pouch", state, {"fighter": "pc-p2", "dropper": "pc-p6"}, note)


def _vault_door() -> Scene:
    state = _base("m29-r2-full", 122)
    note = "Spinners' Row before the locked Foundling Vault; Serin Vale stands here"
    return Scene("vault_door", state, {"rogue": "pc-p6"}, note)


def _dark_wharf() -> Scene:
    state = _base("m29-r2-p4", 243)
    note = "the dark wharf: Brienne (rogue) holds a lit candle and the Bailiff's Broken Link"
    return Scene("dark_wharf", state, {"actor": "pc-p2"}, note)


def _ferry_casters() -> Scene:
    state = _base("m29-r3-casters", 288)
    note = "Greywater Ferry with Old Renn; Brienne wizard, Elowen cleric, Rook has the lockbox"
    return Scene("ferry_casters", state, {"wizard": "pc-p2", "cleric": "pc-p4"}, note)


def _glimmerwharf() -> Scene:
    state = _base("m31-r4-typed", 1291)
    note = "Glimmerwharf; Rook (wizard 3) carries a potion of healing"
    return Scene("glimmerwharf", state, {"wizard": "pc-p6"}, note)


SCENES: dict[str, Callable[[], Scene]] = {
    "village_explore": _village_explore,
    "zombie_fight": _zombie_fight,
    "goblin_fight": _goblin_fight,
    "toll_fight": _toll_fight,
    "toll_offer": _toll_offer,
    "downed_ally": _downed_ally,
    "merre_shop": _merre_shop,
    "zombie_fight_rook": _zombie_fight_rook,
    "toll_fight_rook": lambda: _toll_turn(
        "pc-p6", "toll_fight_rook", "the toll fight, Rook's turn"
    ),
    "toll_fight_brienne": lambda: _toll_turn(
        "pc-p2", "toll_fight_brienne", "the toll fight, Brienne's turn (longsword, shield)"
    ),
    "caster_explore": _caster_explore,
    "caster_fight": _caster_fight,
    "village_pouch": _village_pouch,
    "vault_door": _vault_door,
    "dark_wharf": _dark_wharf,
    "ferry_casters": _ferry_casters,
    "glimmerwharf": _glimmerwharf,
}

# Which deleted router test files have lines on each scene (record: m36_router_sentences.jsonl;
# M38.2: a file whose lines need different states is listed under each of them).
COVERS: dict[str, tuple[str, ...]] = {
    "village_explore": (
        "tests/ai/test_combat_intent.py",
        "tests/ai/test_m30_intent_router.py",
        "tests/ai/test_precheck.py",
        "tests/ai/test_quest_item_tools.py",
        "tests/ai/test_use_intent.py",
        "tests/ai/test_what_now_precheck.py",
        "tests/session/test_m29_hand_over.py",
        "tests/session/test_m29_typed_rest_feature.py",
        "tests/session/test_m30_r3_intents.py",
        "tests/session/test_m31_quests.py",
        "tests/session/test_m33_typed_flow.py",
    ),
    "zombie_fight": ("tests/session/test_m31_typed_fight.py",),
    "goblin_fight": (
        "tests/ai/test_combat_intent.py",
        "tests/ai/test_creative_gear.py",
        "tests/ai/test_precheck.py",
        "tests/ai/test_use_intent.py",
        "tests/ai/test_what_now_precheck.py",
    ),
    "toll_fight": (
        "tests/session/test_m29_r3_surrender.py",
        "tests/session/test_m29_typed_rest_feature.py",
    ),
    "toll_offer": (
        "tests/session/test_m29_r3_offers.py",
        "tests/session/test_m29_typed_intents.py",
        "tests/session/test_m32_typed_offer.py",
        "tests/session/test_m33_typed_flow.py",
        "tests/session/test_m35_waiting_foe.py",
    ),
    "downed_ally": ("tests/ai/test_help_intent.py",),
    "merre_shop": (
        "tests/ai/test_precheck.py",
        "tests/session/test_m31_pay_path.py",
        "tests/session/test_m31_typed_answers.py",
        "tests/session/test_m31_typed_explore.py",
    ),
    "zombie_fight_rook": (
        "tests/ai/test_use_intent.py",
        "tests/session/test_m33_typed_flow.py",
    ),
    "toll_fight_rook": ("tests/session/test_m31_typed_fight.py",),
    "toll_fight_brienne": (
        "tests/session/test_m29_typed_intents.py",
        "tests/session/test_m29_typed_rest_feature.py",
        "tests/session/test_m32_typed_fight.py",
    ),
    "caster_explore": ("tests/session/test_m31_utility_cantrips.py",),
    "caster_fight": ("tests/session/test_m33_typed_flow.py",),
    "village_pouch": (
        "tests/ai/test_item_tools.py",
        "tests/session/test_quest_items_flow.py",
    ),
    "vault_door": (
        "tests/ai/test_m27_typed_gear.py",
        "tests/ai/test_m29_locks_levels.py",
    ),
    "dark_wharf": (
        "tests/session/test_m29_keepsake_hand_over.py",
        "tests/session/test_m29_typed_gear_words.py",
    ),
    "ferry_casters": (
        "tests/ai/test_what_now_precheck.py",
        "tests/session/test_m29_r3_pay.py",
        "tests/session/test_m30_free_spells.py",
        "tests/session/test_m30_r3_intents.py",
    ),
    "glimmerwharf": (
        "tests/session/test_m29_hand_over.py",
        "tests/session/test_m31_typed_explore.py",
    ),
}


# Test files whose every line is a typed line of a committed playtest run (a `run`+`seq` row of
# the main corpus, or a fixture line M38.2 lists as not yet there), so they need no scene. M38.2:
# the other files that replayed a run typed their own lines on its state: those are scene rows.
REPLAYED: tuple[str, ...] = (
    "tests/ai/test_m29_honest_goods.py",
    "tests/session/test_m29_r3_ending.py",
    "tests/session/test_m32_typed_compound.py",
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
