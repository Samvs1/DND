"""Approach then strike: `rules.approach` edge cases (M36.2, round 6 Y10).

The state is the round-6 fight before seq 435: Brienne (30 ft of movement) in the Dripstone Hall
with a swarm of bats; two kobolds in the Caved-In Crypt, 15 ft away over rough ground (30 ft).
"""

from aidm.data.combat_data import combat_registries
from aidm.models.combat import AttackProfile
from aidm.models.commands import MoveCommand
from aidm.models.state import GameState
from aidm.rules.approach import approach_moves, plan_into_band
from aidm.rules.attack_profiles import find_option
from aidm.rules.condition_timing import new_condition
from aidm.rules.zones import MELEE_BAND
from tests.session.playtest_saves import replay_until

REGS = combat_registries()
HERO = "pc-p2"
CRYPT_MOVE = MoveCommand(actor_id=HERO, zone_id="collapsed_vault")


def _state(movement: int | None = None, condition: str | None = None) -> GameState:
    state = replay_until("m35-r6-typed", 435)
    enc = state.encounter
    assert enc is not None
    combatants = dict(enc.combatants)
    me = combatants[HERO]
    if movement is not None:
        economy = me.economy.model_copy(update={"movement_left": movement})
        combatants[HERO] = me.model_copy(update={"economy": economy})
    creatures = dict(state.creatures)
    if condition is not None:
        hero = creatures[HERO]
        conditions = [*hero.conditions, new_condition(condition)]
        creatures[HERO] = hero.model_copy(update={"conditions": conditions})
    encounter = enc.model_copy(update={"combatants": combatants})
    return state.model_copy(update={"encounter": encounter, "creatures": creatures})


def _option(state: GameState, key: str) -> AttackProfile:
    found = find_option(state.creatures[HERO], REGS.chars, key)
    assert found is not None
    return found


def test_approach_walks_to_the_foe_zone() -> None:
    state = _state()
    assert approach_moves(state, HERO, "kobold-1", _option(state, "main_hand"), REGS) == [
        CRYPT_MOVE
    ]
    plan = plan_into_band(state, HERO, "kobold-1", MELEE_BAND, REGS)
    assert plan is not None and plan.feet == 30


def test_approach_already_in_reach_is_empty() -> None:
    state = _state()
    sword = _option(state, "main_hand")
    assert approach_moves(state, HERO, "swarm-of-bats-1", sword, REGS) == []


def test_approach_ranged_option_needs_no_walk() -> None:
    state = _state()
    bow = _option(state, "ranged")
    assert approach_moves(state, HERO, "kobold-1", bow, REGS) == []


def test_approach_no_movement_left_is_none() -> None:
    state = _state(movement=0)
    assert approach_moves(state, HERO, "kobold-1", _option(state, "main_hand"), REGS) is None


def test_approach_rough_ground_too_far_is_none() -> None:
    state = _state(movement=20)
    assert approach_moves(state, HERO, "kobold-1", _option(state, "main_hand"), REGS) is None


def test_approach_blocked_by_restraint_is_none() -> None:
    state = _state(condition="restrained")
    assert approach_moves(state, HERO, "kobold-1", _option(state, "main_hand"), REGS) is None


def test_approach_prone_pays_to_stand_first() -> None:
    prone = _state(condition="prone")
    sword = _option(prone, "main_hand")
    assert approach_moves(prone, HERO, "kobold-1", sword, REGS) is None
    roomy = _state(movement=45, condition="prone")
    assert approach_moves(roomy, HERO, "kobold-1", sword, REGS) == [CRYPT_MOVE]


def test_approach_without_a_fight_is_none() -> None:
    state = _state().model_copy(update={"encounter": None})
    assert plan_into_band(state, HERO, "kobold-1", MELEE_BAND, REGS) is None
