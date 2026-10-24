"""M33.2 ultrareview findings 6, 8 and 9 (docs/reviews/M33_ultrareview.md): honest prose the
guard flagged. Each test replays a live playtest save to the beat, feeds THE guard the honest
telling (it passes now) and a still-false telling (it is still caught). FakeLLM only."""

import dataclasses

from aidm.dm.guard import prose_checker
from aidm.dm.guard_types import ViolationKind
from aidm.models.campaign_events import EncounterOffered, OfferResolved
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.rules.progression import offer_closed, peaceful_close
from tests.session.playtest_saves import ToldTurn, events_of, told_turn

K = ViolationKind


def _kinds(turn: ToldTurn, text: str, *, speech: bool = False) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text, speech=speech
    )
    return {v.kind for v in check(text).violations}


def test_v1_m33_stale_foe_common_words() -> None:
    """Finding 6: in a fight with rats (r5 full 139) "Rook scouts the treeline" and "the priest's
    warning" are no stale foes; "a mimic" or the X14 "bandit captain" told there still are."""
    rats = told_turn("m32-r5-full", 139)
    for honest in (
        "Rook scouts the treeline for the pack leader.",
        "The priest's warning comes back to her as the rats close in.",
        "Tamsin mimics the squeal of a rat to draw them off.",
        "The veteran instinct in Brienne's arm keeps her shield high.",
    ):
        assert K.STALE_FOE not in _kinds(rats, honest), honest
    for false in (
        "A mimic heaves itself up out of the causeway mud.",
        "Two zombies lurch out of the dark behind the rats.",
        "The bandit captain watches from the far bank.",
    ):
        assert K.STALE_FOE in _kinds(rats, false), false


def test_v1_m33_stale_foe_kin_word() -> None:
    """Finding 6, r2 full 1654: the cult fanatic told as "the cultist" is the foe in play."""
    turn = told_turn("r2-full", 1654)
    assert K.STALE_FOE not in _kinds(turn, turn.prose)
    assert K.STALE_FOE in _kinds(turn, "A hobgoblin steps out behind the fanatic.")


def test_v1_m33_engine_gold_is_no_coin_promise() -> None:
    """Finding 8: a typed payment (r4 typed 1303, Penn the ferryman) and a quest paying its gold
    (r4 full 1094, Warder Pell) are real coin: telling them is no COIN_PROMISED or UNPAID."""
    paid = told_turn("m31-r4-typed", 1303)
    told = "Tamsin presses five gold into Penn's palm as payment for the crossing."
    assert not _kinds(paid, told) & {K.COIN_PROMISED, K.UNPAID}
    assert K.COIN_PROMISED not in _kinds(paid, 'Penn: "Good coin, and fair."', speech=True)
    reward = told_turn("m31-r4-full", 1094)
    assert not _kinds(reward, "Warder Pell counts out your reward: good coin for each of you.") & {
        K.COIN_PROMISED,
        K.UNPAID,
    }
    said = 'Warder Pell: "Here is your reward, as promised."'
    assert K.COIN_PROMISED not in _kinds(reward, said, speech=True)
    quiet = dataclasses.replace(paid, events=())  # no gold moved: a promise is still caught
    assert K.COIN_PROMISED in _kinds(quiet, 'Penn: "I will pay you well, in good coin."')


def _answered(turn: ToldTurn, foes: tuple[str, ...], boss: str | None) -> ToldTurn:
    """The beat as the engine records it now: the answer names the offer's foes and master."""
    events = tuple(
        e.model_copy(update={"foes": foes, "boss_npc_id": boss})
        if isinstance(e, OfferResolved)
        else e
        for e in turn.events
    )
    return dataclasses.replace(turn, events=events)


def test_v1_m33_offer_master_counts() -> None:
    """Finding 9, r2 p7 334: the master Gurn (a bandit) and two cultists, offer answered by
    parley. "The two behind him" and "the bandit" are the master's own company."""
    turn = _answered(told_turn("r2-p7", 334), ("cultist", "cultist"), "boss-brambleheath-fens")
    honest = (
        "Gurn the Tollkeeper nods, and the two behind him lower their blades. The bandit sets"
        " his mallet down on the stone."
    )
    assert not _kinds(turn, honest) & {K.STALE_FOE, K.FOE_COUNT}
    assert K.FOE_COUNT in _kinds(turn, "Gurn nods, and the three behind him lower their blades.")
    assert K.STALE_FOE in _kinds(turn, "A ghoul watches from the reeds behind Gurn.")


def _master_offer() -> EncounterOffer:
    return next(
        e.event.offer
        for e in events_of("r2-p7")
        if isinstance(e.event, EncounterOffered) and e.event.offer.boss_npc_id
    )


def test_v1_m33_offer_answer_records_master() -> None:
    """Finding 9: every answer to an offer carries its master, as it carries its foes."""
    master = _master_offer()
    closed = offer_closed(master, OfferChoice.PARLEY, success=True, detail="no fight")
    assert closed.boss_npc_id == master.boss_npc_id and closed.foes == master.monster_ids
    assert peaceful_close(master).boss_npc_id == master.boss_npc_id
    old = OfferResolved.model_validate({"offer_id": "o1", "choice": "parley"})
    assert old.boss_npc_id is None  # an old save's answer still loads
