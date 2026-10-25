"""M31.2a: typed casts of the utility cantrips are read as casts, and only as casts: the names
are everyday words ("light"), so "I light the torch" stays the torch."""

import pytest

from aidm.dm.precheck import precheck
from aidm.models.state import GameState
from aidm.rules.acts import CastIntent
from tests.ai.tool_fixtures import party_state

UTILITY = ["light", "mage-hand", "prestidigitation", "mending", "message", "dancing-lights"]


def _wizard() -> GameState:
    state = party_state(3)
    pc = state.creatures["wizard"].pc
    assert pc is not None
    pc.cantrips = [*pc.cantrips, *UTILITY]
    return state


@pytest.mark.parametrize(
    ("text", "spell"),
    [
        ("cast Light on my shield", "light"),
        ("I cast mage hand to pull the lever", "mage-hand"),
        ("I cast prestidigitation to clean my cloak", "prestidigitation"),
        ("I cast mending on the strap", "mending"),
        ("I cast message to the guard", "message"),
        ("I cast dancing lights down the tunnel", "dancing-lights"),
    ],
)
def test_typed_utility_cast_is_a_cast_on_the_caster(text: str, spell: str) -> None:
    assert precheck(_wizard(), "wizard", text) == CastIntent("wizard", spell, ("wizard",))


@pytest.mark.parametrize("text", ["I light the torch", "I cast a glance at the light"])
def test_everyday_words_are_not_casts(text: str) -> None:
    assert not isinstance(precheck(_wizard(), "wizard", text), CastIntent)
