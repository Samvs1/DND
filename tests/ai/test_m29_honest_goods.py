"""M29.5c the honest storyteller: gold, gear and hand-overs (docs/playtests/M29_round1.md G1 G3
G9 G10 G31). Each test replays the live round 1 save to the narration the model wrote, shows THE
guard rejects that prose, the narrator's facts state the truth, and the narration falls back to
the engine template when the model repeats the false claim (FakeLLM only)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate
from aidm.dm.turn_facts import turn_facts
from aidm.models.state import GameState
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, replay_until, told_turn


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {v.kind for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(
        turn_facts(turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text)
    )


async def _told(tmp_path: Path, turn: ToldTurn, *replies: str) -> tuple[str, NarrationSource]:
    client, fake = fake_client(tmp_path, [fake_text(r) for r in replies])
    stream = narrate(
        turn.state,
        list(turn.events),
        client,
        actor_id=turn.actor_id,
        player_text=turn.player_text,
    )
    text = await stream.collect()
    assert len(fake.requests) == min(len(replies), 2)
    return text, stream.source


def _gold(state: GameState) -> dict[str, int]:
    return {c.name: c.pc.gold for c in state.creatures.values() if c.pc is not None}


async def test_m29_no_payment_without_a_sale(tmp_path: Path) -> None:
    """G1 (p6 60-61): "I pay now" made no shop event; the model told the ten gold paid and the
    silk rope handed over."""
    turn = told_turn("p6", 61)
    assert turn.player_text == "I pay now" and not turn.events
    assert {ViolationKind.UNPAID, ViolationKind.UNMADE_HANDOVER} <= _kinds(turn)
    assert "No coin changed hands and nothing was bought" in _facts(turn)
    text, source = await _told(tmp_path, turn, turn.prose, turn.prose)
    assert source is NarrationSource.TEMPLATE and "ten gold" not in text
    assert _gold(turn.state) == _gold(replay_until("p6", 59))


async def test_m29_counted_coin_is_flagged_but_a_refused_coin_is_not(tmp_path: Path) -> None:
    """G1 (p6 59, 69, 74): handing, setting or counting out gold with no gold event is a claim; a
    payment told as refused, or a price asked, is not."""
    for seq in (59, 69, 74):
        assert ViolationKind.UNPAID in _kinds(told_turn("p6", seq)), seq
    turn = told_turn("p6", 74)
    for honest in (
        "Elowen offers a gold piece, but Tann leaves it untouched on the stone.",
        "Tann taps the price slip: one gold for the rations, if she will pay it.",
    ):
        assert ViolationKind.UNPAID not in _kinds(turn, honest)
    good = "Elowen eyes the waxed packet of rations while Tann waits for a proper bargain."
    text, source = await _told(tmp_path, turn, turn.prose, good)
    assert source is NarrationSource.MODEL and text == good


async def test_m29_claimed_potion_is_told_as_not_there(tmp_path: Path) -> None:
    """G3 (p6 35-36): "I drink my potion of giant strength" without one; the model told it
    shattering (and the summary made the lost potion canon)."""
    turn = told_turn("p6", 36)
    assert ViolationKind.CLAIMED_ITEM in _kinds(turn)
    assert "Brienne does not carry any potion of giant strength" in _facts(turn)
    honest = "Brienne's hand finds no such potion in her pack, only rope and rations."
    assert not _kinds(turn, honest)
    text, source = await _told(tmp_path, turn, turn.prose, honest)
    assert source is NarrationSource.MODEL and "shatters" not in text


def test_m29_claimed_rope_and_javelin_are_not_real() -> None:
    """G3 (p6 39-40, 84-85): "silk rope" (Rook carries only hempen rope) and a javelin Elowen
    never had were told as real."""
    rope = told_turn("p6", 40)
    assert ViolationKind.CLAIMED_ITEM in _kinds(rope)
    assert "Rook does not carry any silk rope" in _facts(rope)
    assert not _kinds(rope, "Rook ties his hempen rope to the post.")
    javelin = told_turn("p6", 85)
    assert ViolationKind.CLAIMED_ITEM in _kinds(javelin)
    assert "Elowen does not carry any javelin" in _facts(javelin)


def test_m29_second_torch_does_not_catch() -> None:
    """G9 (p6 80-81): one torch was consumed at 78; "lights a second torch ... and a third" made
    no event, yet the model told the second catching."""
    turn = told_turn("p6", 81)
    assert ViolationKind.UNLIT_LIGHT in _kinds(turn)
    assert "No new light was lit" in _facts(turn)
    lit = told_turn("p6", 79)  # the real lighting (item_used + light_lit) stays clean
    assert ViolationKind.UNLIT_LIGHT not in _kinds(lit, "The torch catches and steadies.")


def test_m29_hand_over_not_made_is_flagged() -> None:
    """G31 (p3 415-419): the typed hand-overs made no event, yet Ranna was told taking and
    holding both scrolls."""
    for seq in (417, 419):
        turn = told_turn("p3", seq)
        assert ViolationKind.UNMADE_HANDOVER in _kinds(turn), seq
        assert "Nothing changed hands" in _facts(turn)
    real = told_turn("p3", 422)  # after "give the Receipt-scroll to Ranna": a keepsake_given
    assert ViolationKind.UNMADE_HANDOVER not in _kinds(real)


def test_m29_unknown_place_is_not_stood_in_for() -> None:
    """G10 (p6 88-89): "I travel to The Crystal Palace of Zorthak" was told as turning toward a
    real exit (the Hollow Bell) that "gives no passage"."""
    turn = told_turn("p6", 89)
    assert "no other place stands in for it" in _facts(turn)
    known = told_turn("p3", 314)  # a real move: no such fact
    assert "not on the map" not in _facts(known)
