"""M29.7b the honest storyteller beyond fights (docs/playtests/M29_round2.md R2 R12 R17 R13 R21
R28). Each test replays a live round 2 save to the prose the model wrote: THE guard flags the
claim, the narrator's facts carry the truth, the scene summary and its facts do not record the
claim, and honest prose of the same turn stays clean (FakeLLM only)."""

from dataclasses import replace
from pathlib import Path

from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.memory import summary_checker
from aidm.dm.narrator import narrate
from aidm.dm.turn_facts import turn_facts
from aidm.models.events import AnyEvent
from aidm.models.item_events import LightEnded, LightLit
from aidm.models.world_events import FactRecorded, SceneSummarised
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, logged, replay_until, told_turn


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {v.kind for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(
        turn_facts(turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text)
    )


def _recorded(run: str, seq: int) -> str:
    event = logged(run, seq).event
    if isinstance(event, SceneSummarised):
        return event.summary.text
    assert isinstance(event, FactRecorded)
    return event.fact.text


def _memory_kinds(turn: ToldTurn, run: str, seq: int) -> set[ViolationKind]:
    """What the summary guard says of the summary or fact recorded at `seq` (same turn)."""
    state = replay_until(run, seq)
    check = summary_checker(state, turn.events, player_text=turn.player_text)
    return {v.kind for v in check(_recorded(run, seq)).violations}


def _with(turn: ToldTurn, event: AnyEvent) -> ToldTurn:
    return replace(turn, state=apply(turn.state, event), events=(*turn.events, event))


async def test_m29_travel_stopped_short_is_told_where_it_stopped(tmp_path: Path) -> None:
    """R2 (p5 682-691): "I travel to The False Hearth" stopped at Mothfen Hollow (a quest ask),
    but the prose, the summary and three facts placed Brienne at The False Hearth."""
    turn = told_turn("r2-p5", 684)
    assert turn.state.world.current_node == "mothfen-hollow"
    assert ViolationKind.SHORT_TRAVEL in _kinds(turn)
    assert "one place short of The False Hearth" in _facts(turn)
    assert not _kinds(turn, "Brienne walks the soft ground toward The False Hearth.")
    assert ViolationKind.SHORT_TRAVEL in _memory_kinds(turn, "r2-p5", 685)
    for fact in (686, 687, 688):
        assert ViolationKind.SHORT_TRAVEL in _memory_kinds(turn, "r2-p5", fact)
    client, fake = fake_client(tmp_path, [fake_text(turn.prose), fake_text(turn.prose)])
    stream = narrate(
        turn.state, list(turn.events), client, actor_id=turn.actor_id, player_text=turn.player_text
    )
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "false hearth burns" not in text
    assert "one place short of The False Hearth" in str(fake.requests[0].messages[-1]["content"])


def test_m29_travel_short_in_other_runs() -> None:
    """R2 (p7 898, full 882): "As you step out at the Second Socket" one place short; the
    summary and fact "reached the edge of Mireglass Fen" from Siltgate Wharf."""
    socket = told_turn("r2-p7", 892)
    assert ViolationKind.SHORT_TRAVEL in _kinds(socket)
    fen = told_turn("r2-full", 877)
    assert "one place short of Mireglass Fen" in _facts(fen)
    assert ViolationKind.SHORT_TRAVEL in _memory_kinds(fen, "r2-full", 881)
    assert not _memory_kinds(fen, "r2-full", 880)  # "leads ... toward Mireglass Fen" is true
    arrived = told_turn("r2-full", 676)  # the next leg really reached Frostglass Oratory
    assert not _kinds(
        arrived, "The frost settles thicker as you step back into Frostglass Oratory."
    )


def test_m29_vial_never_carried() -> None:
    """R12 (p7 320): "fills a glass vial" with no vial in Elowen's pack; the prose filled it."""
    turn = told_turn("r2-p7", 319)
    assert ViolationKind.CLAIMED_ITEM in _kinds(turn)
    assert "Elowen does not carry any glass vial" in _facts(turn)
    assert not _kinds(turn, "Elowen cups the dark pool water in her bare hands.")


def test_m29_chime_lifted_from_the_dust() -> None:
    """R12 (p7 871-874): Brienne carried the chime since 581; the prose lifted it "from the dust"
    beside Hesk's body, and the one-turn summary and its fact recorded the lift."""
    turn = told_turn("r2-p7", 871)
    assert ViolationKind.UNMADE_PICKUP in _kinds(turn)
    assert "Nothing was picked up in these events" in _facts(turn)
    assert ViolationKind.UNMADE_PICKUP in _memory_kinds(turn, "r2-p7", 872)
    assert ViolationKind.UNMADE_PICKUP in _memory_kinds(turn, "r2-p7", 873)
    assert not _kinds(turn, "Brienne carries the chime in her pack back toward Brother Vale.")
    longer = told_turn("r2-full", 877)  # a two-turn summary may recap an earlier real pick-up
    assert ViolationKind.UNMADE_PICKUP not in _memory_kinds(longer, "r2-full", 878)


def test_m29_ledger_handed_in_an_arrival_narration() -> None:
    """R12 (full 698-699): arriving at Spinners' Row, the prose had Serin take the ledger; the
    summary and fact recorded it. The typed hand-over at 702 really made it."""
    turn = told_turn("r2-full", 697)
    assert ViolationKind.UNMADE_HANDOVER in _kinds(turn)
    assert ViolationKind.UNMADE_HANDOVER in _memory_kinds(turn, "r2-full", 698)
    assert ViolationKind.UNMADE_HANDOVER in _memory_kinds(turn, "r2-full", 699)
    real = told_turn("r2-full", 717)
    assert ViolationKind.UNMADE_HANDOVER not in _kinds(
        real, "Serin Vale takes the ledger with both hands and thanks Rook."
    )


def test_m29_light_prose_matches_the_light_state() -> None:
    """R17 prose (p4 213, 215, 245): a candle told staying dark while it was lit (the M29.7a
    engine lights it), a burning torch whose "flame will not come", a wick pinched with no event."""
    candle = _with(told_turn("r2-p4", 212), LightLit(creature_id="pc-p2", item="candle"))
    assert ViolationKind.LIGHT_STATE in _kinds(candle)
    torch = told_turn("r2-p4", 214)
    assert ViolationKind.LIGHT_STATE in _kinds(torch)
    facts = _facts(torch)
    assert "Already lit before this action, and still burning: Rook's torch" in facts
    assert not _kinds(torch, "Rook's torch burns on, its light plain to see across the wharf.")
    pinch = told_turn("r2-p4", 244)
    assert ViolationKind.LIGHT_STATE in _kinds(pinch)
    assert "No light went out in these events" in _facts(pinch)
    out = _with(pinch, LightEnded(creature_id="pc-p2", reason="put out", item="candle"))
    assert ViolationKind.LIGHT_STATE not in _kinds(out)
    assert not _kinds(torch, "Brienne's candle stays dark in her pouch.")  # no candle burns


def test_m29_present_npc_told_absent() -> None:
    """R13 (p7 342): "Wren is nowhere in sight" while Wren stands on the dock. The "ferry-rat"
    (p7 34, 308) is Wren's own role, so it is a known word."""
    turn = told_turn("r2-p7", 341)
    assert ViolationKind.ERASED_PRESENT in _kinds(turn)
    assert not _kinds(turn, "Wren waits by the pilings, and the peddler keeps his canvas shut.")
    away = told_turn("r2-p7", 350)  # at Thornwold Wren is truly elsewhere
    assert ViolationKind.ERASED_PRESENT not in _kinds(away, "Wren is nowhere in sight here.")
    assert not _kinds(told_turn("r2-p7", 307), "Ask the ferry-rat, not me.")


def test_m29_party_counted_wrong() -> None:
    """R28 (full 574, p8 ~866): "the five of you" with four heroes; a smaller group and a lone
    hero facing a foe ("the two of you circle") are left alone."""
    turn = told_turn("r2-full", 574)
    assert ViolationKind.WRONG_COUNT in _kinds(turn)
    assert "The party ('you') is 4 heroes" in _facts(turn)
    assert not _kinds(turn, "The four of you step back onto the riverbank.")
    assert ViolationKind.WRONG_COUNT in _kinds(told_turn("r2-p8", 808))
    assert not _kinds(told_turn("r2-full", 610))  # "The two of you at the stall" is a group
    assert not _kinds(told_turn("r2-p5", 74))  # solo: "The two of you circle once"


def test_m29_hurt_hero_told_whole() -> None:
    """R28 (p8 ~690): "all four of you whole" with Tamsin at 5 of 14 HP."""
    turn = told_turn("r2-p8", 683)
    assert ViolationKind.HURT_TOLD_WHOLE in _kinds(turn)
    assert "Still hurt (never 'whole' or 'unhurt'): Tamsin" in _facts(turn)
    assert not _kinds(turn, "Brienne and Rook stand whole beside Tamsin, who nurses her lip.")
    whole = told_turn("r2-full", 127)  # everyone at full HP: "All four of you are whole."
    assert not _kinds(whole)
    chime = told_turn("r2-p7", 780)
    assert not _kinds(chime, "Brienne and Elowen stand with the chime lying untouched between you.")


def test_m29_race_the_party_does_not_have() -> None:
    """R28 (p8 fight line): "the dwarf" is Elowen, a hill dwarf, so it is clean; a race nobody
    here has is flagged."""
    turn = told_turn("r2-p8", 595)
    assert ViolationKind.WRONG_IDENTITY not in _kinds(turn)
    assert ViolationKind.WRONG_IDENTITY in _kinds(turn, "The zombie fixes on the halfling.")


def test_m29_engine_id_in_prose() -> None:
    """R21 (p4 751): "offer_favour" reached the prose; a kebab id of the manifest is flagged too,
    while hyphenated words ("bell-frame", "pry-bar") stay clean."""
    turn = told_turn("r2-p4", 750)
    assert ViolationKind.IDENTIFIER in _kinds(turn)
    node = turn.state.world.current_node or ""
    assert "-" in node
    assert ViolationKind.IDENTIFIER in _kinds(turn, f"You stand at the {node} rail.")
    assert not _kinds(turn, "The bugbear drags its pry-bar past the rotted bell-frame.")
