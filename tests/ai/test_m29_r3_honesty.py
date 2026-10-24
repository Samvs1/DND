"""M29.9c storyteller honesty (docs/playtests/M29_round3.md T4 T10 T11 T21). Each test replays a
live round 3 save to the narration the model wrote, feeds its REAL text with that beat's facts
to THE guard and checks the kind flagged; the honest telling of the same beat stays clean
(FakeLLM only, never the network)."""

from pathlib import Path

from aidm.dm.epilogue import epilogue_checker
from aidm.dm.epilogue_facts import epilogue_facts
from aidm.dm.event_text import event_line, event_notes
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate_round_segment
from aidm.dm.turn_facts import turn_facts
from aidm.models.campaign_events import EpilogueWritten
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, logged, replay_until, told_turn

K = ViolationKind


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {v.kind for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(
        turn_facts(turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text)
    )


_FOE_LIES = {K.PHANTOM_BLOW, K.PHANTOM_HIT, K.UNRESOLVED_BLOW}


async def test_m29_invented_foe_attempts(tmp_path: Path) -> None:
    """T4: a foe told springing, lunging, swinging or nearly biting on a beat it made no attack
    (casters 187 204 408 432, full 632 881), a blade opening a hero nobody struck (items 602),
    the cold lashing out with no roll (items 881). The death dog that really bit and missed
    (casters 894) is told honestly and passes."""
    cases = [
        ("r3-casters", 187, K.PHANTOM_BLOW, "springs at"),
        ("r3-casters", 204, K.PHANTOM_BLOW, "lunges"),
        ("r3-casters", 408, K.PHANTOM_BLOW, "lunge at"),
        ("r3-casters", 432, K.PHANTOM_BLOW, "swing at"),
        ("r3-full", 632, K.PHANTOM_BLOW, "sweeping low"),
        ("r3-full", 881, K.PHANTOM_BLOW, "lash out"),
        ("r3-items", 602, K.PHANTOM_HIT, "opens"),
        ("r3-items", 881, K.UNRESOLVED_BLOW, "lashes out"),
    ]
    for run, seq, kind, span in cases:
        turn = told_turn(run, seq)
        check = prose_checker(turn.state, turn.events)
        found = {(v.kind, v.span) for v in check(turn.prose).violations}
        assert (kind, span) in found, (run, seq, found)
    assert not _kinds(told_turn("r3-casters", 894)) & _FOE_LIES
    wolf = told_turn("r3-casters", 187)
    assert "Wolf" in _facts(wolf).split("Did nothing")[1]
    client, fake = fake_client(tmp_path, [fake_text(wolf.prose), fake_text(wolf.prose)])
    stream = narrate_round_segment(wolf.state, list(wolf.events), client)
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "springs at" not in text
    assert len(fake.requests) == 2 and "ENGINE GUARD" in str(fake.requests[1].messages[-1])


def test_m29_invented_foe_attempts_honest_versions_pass() -> None:
    honest = {
        ("r3-casters", 187): "The fire bolt scorches past the wolf's shoulder and bites into a"
        " birch trunk. The wolf flinches from the heat and circles, snarling at Tamsin.",
        ("r3-casters", 204): "Brienne's bolt goes wide of the wolf, which dashes through the"
        " bracken to the scrub and wheels to face Tamsin, hackles high.",
        ("r3-casters", 408): "Rook's eldritch blast cracks into the smoldering zombie, which reels"
        " and rights itself; both corpses keep shambling toward Tamsin.",
        ("r3-full", 632): "The hollow armor stands in the gloom where Rook vanished, its maul"
        " held low, its empty gorget turning toward Tamsin.",
        ("r3-items", 602): "Brienne's quarrel skips off the ruined stone. The cultists hold"
        " their ground behind Sorrel Myn, blades drawn.",
        ("r3-items", 881): "The mephit drags itself upright against the pillar, frost knotting"
        " in its palm as it glares at the three of you.",
    }
    for (run, seq), text in honest.items():
        assert not _kinds(told_turn(run, seq), text) & _FOE_LIES, (run, seq)


def test_m29_saved_spell_is_no_hit() -> None:
    """T4: Sacred Flame the target saved against told scorching (full 358) and charring (full
    1379). The facts now say the save left no harm; the honest telling passes. Full 118 ("licks
    the cultist's sleeve but it twists aside, smoke curling from singed cloth") already tells a
    dodge and passes."""
    for seq, span in ((358, "scorching"), (1379, "chars")):
        turn = told_turn("r3-full", seq)
        check = prose_checker(turn.state, turn.events)
        assert (K.PHANTOM_HIT, span) in {(v.kind, v.span) for v in check(turn.prose).violations}
        assert "saved against sacred flame: no harm" in _facts(turn)
    zombie = told_turn("r3-full", 358)
    honest = (
        "Radiance flares around the zombie, but it lurches aside and the sacred flame gutters out"
        " on the mud, leaving it untouched."
    )
    assert K.PHANTOM_HIT not in _kinds(zombie, honest)
    assert not _kinds(told_turn("r3-full", 118)) & _FOE_LIES


def test_m29_fled_foe_is_not_dead() -> None:
    """T4: the cultist that fled at 1 HP told "sent crashing into the reeds" (full 96); the
    berserker at 6 of 67 HP told "slumping into the cinders" (full 1194). The facts no longer
    call the fled cultist "still standing and fighting"."""
    fled = told_turn("r3-full", 96)
    assert K.FLED_TOLD_DEAD in _kinds(fled)
    facts = _facts(fled)
    assert "Cultist A fled the fight alive" in facts
    assert "Cultist A" not in facts.split("Hurt but still standing")[1].split(".")[0]
    honest = (
        "Rook's arrow tears through the first cultist, who staggers and flees into the reeds."
        " The second one rakes its rusted blade across Tamsin's ribs."
    )
    assert K.FLED_TOLD_DEAD not in _kinds(fled, honest)
    brute = told_turn("r3-full", 1194)
    assert K.UNHURT_DECLARED_DOWN in _kinds(brute)
    honest = "Rook's rapier slips past the berserker's guard, and the brute reels but stays up."
    assert K.UNHURT_DECLARED_DOWN not in _kinds(brute, honest)


def test_m29_gift_told_refused() -> None:
    """T10 (items 499-501): the route note moved to Anwen (KeepsakeGiven), and the prose had her
    push it back across the table."""
    turn = told_turn("r3-items", 501)
    assert K.REFUSED_HANDOVER in _kinds(turn)
    lines = [event_line(turn.state, e) for e in turn.events]
    assert "Tamsin hands the Bloodstained Route Note to Anwen Toft, who takes it." in lines
    honest = (
        "Anwen takes the route note, frowns at the bloodstains and folds it into her apron,"
        " though it is not the archivist's writing she hoped for."
    )
    assert not _kinds(turn, honest) & {K.REFUSED_HANDOVER, K.UNMADE_HANDOVER}


def test_m29_accepted_quest_told_done() -> None:
    """T11 (items 32-34): taking on Beska's errand was told as handing her the sun-ember ("takes
    your sun-ember", "takes the cold ember from your hands") while nobody held one. The facts
    now say the quest is accepted only, in a model-only note that never reaches the feed."""
    for seq, span in ((32, "takes your"), (34, "takes the")):
        turn = told_turn("r3-items", seq)
        check = prose_checker(turn.state, turn.events)
        found = {(v.kind, v.span) for v in check(turn.prose).violations}
        assert (K.UNMADE_HANDOVER, span) in found
    accepted = told_turn("r3-items", 34)
    notes = event_notes(accepted.state, accepted.events)
    assert any("accepted only: nothing handed over or done yet" in x for x in notes)
    lines = [event_line(accepted.state, e) or "" for e in accepted.events]
    assert not any("accepted only" in x for x in lines)
    honest = (
        "Beska nods, relief in her pale knuckles: the ember must come from Wrenfall's cold altar,"
        " and the lantern will wait for it."
    )
    assert not _kinds(accepted, honest) & {K.UNMADE_HANDOVER, K.UNMADE_OUTCOME}


def test_m29_quest_outcome_both_ways() -> None:
    """T11: a quest told done when none was (items 34), and a completed quest told unfinished
    (items 204, after Fuel for the Faithless Flame completed)."""
    accepted = told_turn("r3-items", 34)
    assert K.UNMADE_OUTCOME in _kinds(accepted, "Beska smiles: the task is done.")
    done = told_turn("r3-items", 204)
    assert "completed" in done.state.world.quests["fuel-for-the-faithless-flame"].state.value
    assert K.DENIED_OUTCOME in _kinds(done, "Beska sighs, for the task is not yet done.")
    assert not _kinds(done) & {K.DENIED_OUTCOME, K.UNMADE_OUTCOME, K.REFUSED_HANDOVER}


def test_m29_epilogue_ally_never_joined_party() -> None:
    """T21 leftover (full 1735): the ending's prose said Voss and Ulva "joined the party" while
    the party stayed four heroes; the engine's facts say "sided with the party"."""
    state = replay_until("r3-full", 1735)
    written = logged("r3-full", 1735).event
    assert isinstance(written, EpilogueWritten)
    check = epilogue_checker(state, epilogue_facts(state))
    report = check(written.text)
    assert K.JOINED_PARTY in {v.kind for v in report.violations}
    honest = (
        "In Miremoor Fens, High Lector Orlan Voss was won over and sided with the party by the"
        " way of peace."
    )
    assert K.JOINED_PARTY not in {v.kind for v in check(honest).violations}
