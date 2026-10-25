"""Typed help for a downed ally (M20.2) and the guard against prose that raises one (playtest 3:
"her breathing steadies" while nothing had happened; "Slendee stirs and opens her eyes")."""

import pytest

from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.dm.precheck import precheck
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import Encounter
from aidm.models.events import HpChanged
from aidm.models.state import GameState
from aidm.rules.acts import HelpUpIntent
from aidm.rules.damage import resolve_damage
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state
from tests.unit.rules.combat_fixtures import small_map


def _down(state: GameState, cid: str) -> GameState:
    target = state.creatures[cid]
    packet = DamagePacket(amount=target.hp, damage_type=DamageType.PIERCING)
    for event in resolve_damage(target, [packet]):
        apply(state, event)
    return state


@pytest.mark.parametrize(
    "text",
    [
        "I help Brannoc up",
        "help her up",
        "I try to wake Brannoc.",
        "We get Brannoc back on his feet",
        "I help Brannoc to his feet",
        "rouse brannoc",
        "I stabilize him",
        "Let's revive Brannoc",
        "I pull Brannoc up",
    ],
)
def test_help_up_typed(text: str) -> None:
    state = _down(inn_state(), "rogue")
    assert precheck(state, "fighter", text) == HelpUpIntent("fighter", "rogue")


def test_help_up_typed_needs_a_downed_named_ally() -> None:
    state = _down(inn_state(), "rogue")
    assert precheck(state, "fighter", "I help Celes up") is None  # Celes is standing
    assert precheck(state, "rogue", "I help Brannoc up") is None  # not yourself
    _down(state, "wizard")
    assert precheck(state, "fighter", "help her up") is None  # two are down: name one
    assert precheck(state, "fighter", "wake Celes") == HelpUpIntent("fighter", "wizard")
    state.encounter = Encounter(id="f1", zone_map=small_map())
    assert precheck(state, "fighter", "wake Celes") is None  # in a fight: the Help action


@pytest.mark.parametrize(
    "text",
    [
        "Brannoc stirs, coughs, and opens his eyes.",
        "Brannoc gets to his feet, shaky but alive.",
        "Brannoc comes to with a gasp.",
    ],
)
def test_guard_downed_hero_cannot_rise_without_an_event(text: str) -> None:
    state = _down(inn_state(), "rogue")
    kinds = {v.kind for v in check_prose(text, state).violations}
    assert ViolationKind.DOWNED_RISING in kinds


def test_guard_downed_hero_still_or_helped_is_fine() -> None:
    state = _down(inn_state(), "rogue")
    for text in (
        "Brannoc lies still, his breathing shallow.",
        "Brannoc does not wake.",
        "You kneel beside Brannoc while Aria gets to her feet.",
    ):
        assert check_prose(text, state).violations == (), text
    apply(state, HpChanged(creature_id="rogue", delta=1, new_hp=1))
    assert check_prose("Brannoc opens his eyes and sits up.", state).violations == ()
