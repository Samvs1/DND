"""Names with typographic apostrophes (M20.1, playtest 3 save c-20261010-161143-6031: the ranger
was stored as "El’Skalfidar", the guard compared the prose with plain apostrophes against the
curly name, and every model sentence naming him was flagged "not a party member"; his deeds were
told by templates all session)."""

import pytest

from aidm.dm.guard import check_prose
from aidm.dm.guard_text import plain
from aidm.dm.guard_types import ViolationKind
from aidm.models.state import GameState
from tests.ai.guard_fixtures import add_dead, inn_state
from tests.ai.tool_fixtures import add_npc

RANGER = "El’Skalfidar"


def _state() -> GameState:
    state = inn_state()
    state.creatures["rogue"].name = RANGER
    add_npc(state, "npc-kel", name="Kel’Varra", role="ferry warden")
    return state


@pytest.mark.parametrize(
    "text",
    [
        "El’Skalfidar looses an arrow and the stirge drops into the reeds.",
        "El'Skalfidar's arrow takes the rat through the throat.",
        "El‘Skalfidar nods to Aria and lowers his bow.",
        "Aria glances at El’Skalfidar, the rogue, and grins.",
        "Kel’Varra lifts her lantern and waits.",
        "Kel'Varra's lantern sways over the bar.",
    ],
)
def test_guard_curly_apostrophe_hero(text: str) -> None:
    assert check_prose(text, _state()).violations == ()


def test_guard_apostrophe_near_miss_is_still_a_wrong_identity() -> None:
    kinds = {v.kind for v in check_prose("El'Skalfidor draws his bow.", _state()).violations}
    assert ViolationKind.WRONG_IDENTITY in kinds


def test_guard_dead_apostrophe_name_cannot_act() -> None:
    state = _state()
    add_dead(state, "orc-1", "Gro’mash")
    kinds = {v.kind for v in check_prose("Gro'mash swings his axe at Aria.", state).violations}
    assert ViolationKind.DEAD_ACTING in kinds


def test_plain_keeps_length_and_maps_every_apostrophe() -> None:
    text = "El’Skalfidar El‘Skalfidar Elʼ`´′"
    assert len(plain(text)) == len(text)
    assert plain(text) == "El'Skalfidar El'Skalfidar El''''"
