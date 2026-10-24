"""M32.1b X10-X16 (docs/playtests/M31_round5.md): the storyteller's round 5 defects. Each test
replays a live round 5 save to the narration the model wrote, feeds its REAL text with that
beat's facts to THE guard and checks the kind flagged; the honest telling passes (FakeLLM only)."""

import dataclasses
from pathlib import Path

from aidm.dm.epilogue import epilogue_checker, honest_facts
from aidm.dm.event_text import event_line
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.dm.narrator import narrate
from aidm.models.campaign_events import EpilogueWritten, OfferResolved
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, logged, replay_until, told_turn

K = ViolationKind
TYPED = "m32-r5-typed"
QUESTS = "m32-r5-quests"
FULL = "m32-r5-full"


def _found(turn: ToldTurn, text: str | None = None) -> set[tuple[ViolationKind, str]]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {(v.kind, v.span) for v in check(text if text is not None else turn.prose).violations}


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    return {kind for kind, _ in _found(turn, text)}


def test_v1_m32_coin_promised_and_untold_payment() -> None:
    """X11, quests 391, 395, 638: the favour's asker promised "fifteen silver", and the story
    later had her pay "the full sum" while no gold moved."""
    assert (K.COIN_PROMISED, "would pay") in _found(told_turn(QUESTS, 391))
    assert (K.COIN_PROMISED, "I will pay") in _found(told_turn(QUESTS, 395))
    assert (K.UNPAID, "pays") in _found(told_turn(QUESTS, 638))
    honest = (
        "The Velde Landing Peddler hears you out and nods once, grateful for the report. She"
        " thanks you warmly, and the mist beyond the landing stays where it is."
    )
    assert not _kinds(told_turn(QUESTS, 638), honest) & {K.UNPAID, K.COIN_PROMISED}


def test_v1_m32_errand_outside_the_quest_system() -> None:
    """X10, quests 42-44: the peddler named "a small errand worth a few coins" and "a run of
    silverleaf to the manse gate" with no favour asked: errands exist only through the tool."""
    found = _found(told_turn(QUESTS, 42))
    assert {(K.UNASKED_ERRAND, "a small errand"), (K.COIN_PROMISED, "worth a few")} <= found
    assert K.UNASKED_ERRAND in _kinds(told_turn(QUESTS, 44))
    honest = "The peddler glances up from the stall and nods, busy with the morning's wares."
    assert not _kinds(told_turn(QUESTS, 42), honest) & {K.UNASKED_ERRAND, K.COIN_PROMISED}


def test_v1_m32_foe_actions_in_a_hero_turn() -> None:
    """X12: "The thug slashes low" (quests 477), "sweeps the club at her knees" (typed 120),
    "His next javelin takes Rook" (typed 682) and "next swing hisses past Brienne's ear"
    (typed 1227), each in a beat where that foe made no blow."""
    assert (K.PHANTOM_BLOW, "slashes low") in _found(told_turn(QUESTS, 477))
    assert (K.UNRESOLVED_BLOW, "at her knees") in _found(told_turn(TYPED, 120))
    assert (K.PHANTOM_HIT, "javelin takes") in _found(told_turn(TYPED, 682))
    assert K.PHANTOM_BLOW in _kinds(told_turn(TYPED, 1227))


def test_v1_m32_living_foes_told_fled() -> None:
    """X12, full 139 and 371: rats at 1 of 24 HP and bats at 22 of 22 "scatter into" the dark."""
    for seq in (139, 371):
        assert K.FLED_ALIVE in _kinds(told_turn(FULL, seq)), seq
    honest = "The rats boil and snap at the causeway, thinned but still fighting."
    assert K.FLED_ALIVE not in _kinds(told_turn(FULL, 139), honest)


def test_v1_m32_sleeping_foe_told_acting() -> None:
    """X12, full 400, 424, 450: the cultist under Sleep "tracks Brienne", "holds his ground",
    "watches the bats fall ... lifts his blade"."""
    for seq in (400, 424, 450):
        assert K.HELPLESS_ACTING in _kinds(told_turn(FULL, seq)), seq
    honest = "The cultist sleeps on in the muck, blade slack beside him."
    assert K.HELPLESS_ACTING not in _kinds(told_turn(FULL, 424), honest)


def test_v1_m32_rays_told_in_order() -> None:
    """X12, typed 1320: Scorching Ray hit, missed, hit; the prose had the third miss."""
    assert (K.WRONG_ORDER, "hisses into the") in _found(told_turn(TYPED, 1320))
    honest = (
        "Rook's first ray splashes across Mother Vyra's amber-caked shoulder and the second"
        " hisses into the dark water. The third ray sears her ribs, and she rocks but does not"
        " cry out."
    )
    assert K.WRONG_ORDER not in _kinds(told_turn(TYPED, 1320), honest)


def test_v1_m32_gift_told_refused() -> None:
    """X13, full 182: the model's own tool made Ilric friendly for the gift, the prose had him
    make "no move to take it" while "his warmth cools"."""
    assert (K.REFUSED_HANDOVER, "makes no move to take") in _found(told_turn(FULL, 182))
    honest = "Ilric takes the rations with a grateful nod, and his manner warms."
    assert K.REFUSED_HANDOVER not in _kinds(told_turn(FULL, 182), honest)


def _answered(turn: ToldTurn, foes: tuple[str, ...]) -> ToldTurn:
    """The beat as the engine records it now: the answer names the offer's foes (M32.1b)."""
    events = tuple(
        e.model_copy(update={"foes": foes}) if isinstance(e, OfferResolved) else e
        for e in turn.events
    )
    return dataclasses.replace(turn, events=events)


def test_v1_m32_stale_foe_and_shapes() -> None:
    """X14: the ghast parley told as the earlier bandit captain "and the three behind him"
    (full 1256), "three shapes" and "the three behind him" behind a one-foe offer (full
    1223)."""
    turn = _answered(told_turn(FULL, 1256), ("ghast",))
    found = _found(turn)
    assert {(K.STALE_FOE, "bandit captain"), (K.FOE_COUNT, "the three behind him")} <= found
    found = _found(told_turn(FULL, 1223))
    assert {(K.FOE_COUNT, "three shapes"), (K.FOE_COUNT, "The three behind him")} <= found
    honest = "The ghast lowers its head and lets you pass, grey hide steaming in the cold."
    assert not _kinds(turn, honest) & {K.STALE_FOE, K.FOE_COUNT}


def test_v1_m32_offer_answer_names_its_foes() -> None:
    """X14 root cause: the answer's fact line now names who was answered (the ghast)."""
    turn = _answered(told_turn(FULL, 1256), ("ghast",))
    resolved = next(e for e in turn.events if isinstance(e, OfferResolved))
    line = event_line(turn.state, resolved)
    assert line == "The party chose parley (success) facing a ghast: no fight."


def test_v1_m32_found_told_taken() -> None:
    """X16: "Rook's fingers close on a carved peat node" (quests 338) and "the locket sits in
    her open palm" (typed 1010) while each still lay where it was found."""
    assert (K.FOUND_TAKEN, "fingers close on") in _found(told_turn(QUESTS, 338))
    assert (K.FOUND_TAKEN, "in her open palm") in _found(told_turn(TYPED, 1010))


async def test_v1_m32_finale_never_carries_the_filler(tmp_path: Path) -> None:
    """X15, full 1442: the finale telling ended on "The moment settles, and the scene waits on
    your next move." A cut-short finale now ends on what the model told."""
    turn = told_turn(FULL, 1442)
    cut = (
        "You speak the true name, and the black garden exhales. The keepers relax into the"
        " shallows like salt at last admitting the tide. Sir Zebulon Quill bows to you."
    )
    client, _ = fake_client(tmp_path, [fake_text(cut), fake_text(cut)])
    stream = narrate(turn.state, list(turn.events), client, actor_id=turn.actor_id)
    text = await stream.collect()
    assert CLOSING_LINE not in text and "black garden exhales" in text


def test_v1_m32_epilogue_start_place() -> None:
    """X15, full 1443: "ended where it began, in the Flooded Chapel" (it began in Tidefall and
    ended in Caulmere). The facts state both; the guard flags another place."""
    state = replay_until(FULL, 1443)
    facts = honest_facts(state)
    assert "The tale began at Tidefall and ended at Caulmere." in facts.lines()
    told = logged(FULL, 1443).event
    assert isinstance(told, EpilogueWritten)
    check = epilogue_checker(state, facts)
    report = check(told.text.split(". ")[0] + ".")
    assert K.EPILOGUE_PLACE in {v.kind for v in report.violations}
    honest = "The Salt Covenant began in Tidefall and ended in Caulmere, where the tide spoke."
    assert K.EPILOGUE_PLACE not in {v.kind for v in check(honest).violations}
