"""Typed help for a downed ally (M20.2) and the guard against prose that raises one (playtest 3:
"her breathing steadies" while nothing had happened; "Slendee stirs and opens her eyes")."""

import pytest

from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import HpChanged
from aidm.models.state import GameState
from aidm.rules.damage import resolve_damage
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state


def _down(state: GameState, cid: str) -> GameState:
    target = state.creatures[cid]
    packet = DamagePacket(amount=target.hp, damage_type=DamageType.PIERCING)
    for event in resolve_damage(target, [packet]):
        apply(state, event)
    return state


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
