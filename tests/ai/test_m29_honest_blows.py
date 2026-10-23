"""M29.7b the honest storyteller, per creature (docs/playtests/M29_round2.md R19). Each test replays
a live round 2 save to the fight narration the model wrote and shows THE guard rejects the blow,
hit, miss or kill no event resolved, the narrator's facts name who acted and who did nothing, and
honest prose of the same turn stays clean (FakeLLM only)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate_round_segment
from aidm.dm.turn_facts import turn_facts
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, told_turn


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {v.kind for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(turn_facts(turn.state, turn.events))


def _hp(turn: ToldTurn, name: str) -> int:
    return next(c.hp for c in turn.state.creatures.values() if c.name == name and not c.dead)


_BLOWS = {
    ViolationKind.PHANTOM_BLOW,
    ViolationKind.PHANTOM_HIT,
    ViolationKind.FALSE_MISS,
    ViolationKind.WRONG_KILLER,
}


async def test_m29_foe_claw_hit_beside_a_lone_miss(tmp_path: Path) -> None:
    """R19 (p4 871-874): Brienne's one shot missed; the prose added the bugbear's charge and a
    claw hit on her. No foe acted: the guard flags it, the facts say the bugbear did nothing, and
    the same false prose twice ends in the engine template."""
    turn = told_turn("r2-p4", 873)
    assert ViolationKind.PHANTOM_BLOW in _kinds(turn)
    facts = _facts(turn)
    assert "Brienne: shortbow at Bugbear, missed" in facts
    assert "Did nothing in these events" in facts and "Bugbear" in facts.split("Did nothing")[1]
    client, fake = fake_client(tmp_path, [fake_text(turn.prose), fake_text(turn.prose)])
    stream = narrate_round_segment(turn.state, list(turn.events), client)
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "claws rake" not in text
    assert len(fake.requests) == 2 and "ENGINE GUARD" in str(fake.requests[1].messages[-1])
    honest = (
        "Brienne's shaft skitters wide of the bugbear's head, and it bellows, holding its ground."
    )
    assert not _kinds(turn, honest) & _BLOWS
    later = told_turn("r2-p4", 1033)  # Elowen missed; "It catches her across the brow"
    assert ViolationKind.PHANTOM_BLOW in _kinds(later)


def test_m29_bugbear_drops_face_first_while_standing() -> None:
    """R19 (full 1072): the bugbear at 12 of 27 HP "drops face-first"; Rook's arrow that "drives
    deep" was never shot (only Tamsin acted)."""
    turn = told_turn("r2-full", 1071)
    assert _hp(turn, "Bugbear") == 12
    kinds = _kinds(turn)
    assert ViolationKind.UNHURT_DECLARED_DOWN in kinds and ViolationKind.PHANTOM_BLOW in kinds
    assert "Rook" in _facts(turn).split("Did nothing")[1]
    honest = "Tamsin's fire bolt takes the bugbear in the ribs, and it staggers but stays up."
    assert not _kinds(turn, honest) & (_BLOWS | {ViolationKind.UNHURT_DECLARED_DOWN})


def test_m29_shafts_find_their_mark_with_no_roll() -> None:
    """R19 (full 2061): only Elowen's two healing spells resolved, yet the Hunger's bow "twangs"
    and both shafts "find their mark in Elowen and Tamsin"."""
    turn = told_turn("r2-full", 2061)
    kinds = _kinds(turn)
    assert ViolationKind.PHANTOM_BLOW in kinds and ViolationKind.PHANTOM_HIT in kinds
    honest = "The Reflected Hunger watches, bow lowered, as warmth floods back into Tamsin."
    assert not _kinds(turn, honest) & _BLOWS


def test_m29_skeleton_looses_with_no_roll() -> None:
    """R19 (full 509): Elowen's Sacred Flame was the only blow; the second skeleton "looses at
    the dwarf's face"."""
    turn = told_turn("r2-full", 509)
    assert ViolationKind.PHANTOM_BLOW in _kinds(turn)
    facts = _facts(turn)
    assert "Elowen: sacred flame at Skeleton" in facts and "Skeleton B" in facts
    honest = "The second skeleton rattles aside, bow half raised, but it does not loose."
    assert not _kinds(turn, honest) & _BLOWS


def test_m29_kill_credited_to_the_wrong_hero() -> None:
    """R19 (full 395): Sacred Flame killed the cultist; the prose said it "folds around
    Brienne's bolt" (Brienne did not act). A killer who acted but did not kill is flagged too."""
    turn = told_turn("r2-full", 395)
    assert ViolationKind.PHANTOM_BLOW in _kinds(turn)
    assert "Cultist fell (the killing blow was Elowen's)" in _facts(turn)
    wrong = "The cultist folds around Luth's quarrel and sprawls in the dust."
    assert ViolationKind.WRONG_KILLER in _kinds(turn, wrong)
    honest = "The cultist folds under Elowen's sacred flame and sprawls in the dust."
    assert not _kinds(turn, honest) & _BLOWS


def test_m29_bolt_told_skipping_off_after_a_hit() -> None:
    """R19 (full 88): Brienne's bolt hit the cultist for 3; the prose said it "skips off"."""
    turn = told_turn("r2-full", 87)
    assert ViolationKind.FALSE_MISS in _kinds(turn)
    assert "Brienne: light crossbow at Cultist B, hit" in _facts(turn)
    honest = "Brienne's bolt bites into the cultist's shoulder, and the figure reels back a step."
    assert not _kinds(turn, honest) & _BLOWS


def test_m29_graze_from_a_foe_that_did_not_act() -> None:
    """R19 (p8 185, live line 159): the cultist only moved; the prose gave its blade a cut on
    Brienne. Rook really lost 4 HP, to Tamsin's Burning Hands, so his graze is not the lie."""
    turn = told_turn("r2-p8", 158)
    assert ViolationKind.PHANTOM_BLOW in _kinds(turn)
    assert "Cultist" in _facts(turn).split("Did nothing")[1]
    honest = "Rook takes a staggering graze across the ribs as the fire rolls past him."
    assert not _kinds(turn, honest) & _BLOWS


def test_m29_honest_fight_prose_stays_clean() -> None:
    """False positives the per-creature checks must not raise: a head swinging toward a sound,
    a creature hurling itself aside, a passive hit, a dead foe's weapon lying still, a hero who
    did act, and an engine line about a real attack."""
    miss = told_turn("r2-p4", 873)
    for text in (
        "The bugbear's head swings toward the sound, nostrils flaring.",
        "Rook's arrow is already nocked, but the creature hurls itself aside and waits.",
        "Brienne is struck by nothing but the spray of the bearings.",
        "Brienne looses, and the shaft skitters wide.",
    ):
        assert not _kinds(miss, text) & _BLOWS, text
    dead = told_turn("r2-full", 1002)
    assert not _kinds(dead) & _BLOWS  # "The armor lies still, its sword half-buried in the reeds."
    real = told_turn("r2-p5", 144)  # the bandit really shot at Brienne and missed
    assert not _kinds(real, "The bandit looses at Brienne, but the bolt goes wide.") & _BLOWS
    spell = told_turn("r2-full", 1579)
    assert not _kinds(spell, "Elowen's spell tears through the armor's leg.") & _BLOWS
