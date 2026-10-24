"""M31.2b: two storyteller defects left from rounds 3 and 4. Each test replays the live save to
the narration the model wrote, feeds its REAL text with that beat's facts to THE guard and checks
the kind flagged; the honest telling passes (FakeLLM only, no network)."""

import dataclasses

from aidm.dm.guard import prose_checker
from aidm.dm.guard_types import ViolationKind
from aidm.models.events import ConditionApplied, GoldChanged
from aidm.models.state import ActiveCondition
from tests.session.playtest_saves import ToldTurn, told_turn

K = ViolationKind
ITEMS = "r3-items"
R4 = "m31-r4-typed"


def _found(turn: ToldTurn, text: str | None = None) -> set[tuple[ViolationKind, str]]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {(v.kind, v.span) for v in check(text if text is not None else turn.prose).violations}


def _kinds(turn: ToldTurn, text: str) -> set[ViolationKind]:
    return {kind for kind, _ in _found(turn, text)}


def test_v1_m31_invented_foe_ability() -> None:
    """Round 3 items 908: the ice mephit "splitting into three icy shards that skitter away and
    reform on the far side", an ability no mephit has, told with no attack verb."""
    turn = told_turn(ITEMS, 908)
    assert (K.INVENTED_FEAT, "splitting into") in _found(turn)
    honest = (
        "The mephit flattens itself against the pillar, frost webbing across the floor where it"
        " drags its broken arm. It turns its jagged face toward the torch."
    )
    assert K.INVENTED_FEAT not in _kinds(turn, honest)


def test_v1_m31_foe_ability_from_the_stat_block() -> None:
    """What the stat block holds may be told: an ice mephit flies (fly 30 ft.) and has Frost
    Breath; a foe's growl that "splits into two notes" is no ability of the foe; a hero's spell
    may split ("Tamsin's bolt splits into three darts")."""
    turn = told_turn(ITEMS, 908)
    allowed = (
        "The mephit takes wing and hangs above the pillar.",
        "The mephit breathes frost across the floor.",
        "Its growl splits into two notes that pull at the dark.",
        "Tamsin's bolt splits into three gleaming darts.",
    )
    for text in allowed:
        assert K.INVENTED_FEAT not in _kinds(turn, text), text
    for text in ("The mephit turns invisible.", "The mephit summons two more of its kind."):
        assert K.INVENTED_FEAT in _kinds(turn, text), text


def test_v1_m31_foe_ability_from_the_events() -> None:
    """A foe the engine made invisible this turn may be told vanishing: the turn's events
    support what the stat block lacks (here a condition applied to it)."""
    turn = told_turn(ITEMS, 908)
    assert K.INVENTED_FEAT in _kinds(turn, "The mephit turns invisible.")
    applied = ConditionApplied(
        creature_id="ice-mephit-1", condition=ActiveCondition(name="invisible")
    )
    hid = dataclasses.replace(turn, events=(*turn.events, applied))
    assert K.INVENTED_FEAT not in _kinds(hid, "The mephit turns invisible.")


def test_v1_m31_coins_on_the_table_unpaid() -> None:
    """Round 4 typed 45: "Rook slaps the coins onto the table" while no gold moved (he carried
    15 of the 50 named). THE guard's unpaid-coin check catches coins put down with no gold
    event; with a gold event, or told honestly, it passes."""
    turn = told_turn(R4, 45)
    assert (K.UNPAID, "slaps the coins") in _found(turn)
    honest = (
        "Rook reaches for his purse, but Merre shrinks back, his eyes wide as if the gold is"
        " another reminder of the debt he cannot settle."
    )
    assert K.UNPAID not in _kinds(turn, honest)
    assert K.UNPAID not in _kinds(turn, "Rook drops the gold chain onto the table.")
    paid = dataclasses.replace(
        turn, events=(*turn.events, GoldChanged(creature_id="pc-p6", delta=-10, gold=5))
    )
    assert K.UNPAID not in _kinds(paid, "Rook slaps the coins onto the table.")
