"""M31.1c V17 (docs/playtests/M31_round4.md): the storyteller still invented foe actions and
foes and misreported results. Each test replays a live round 4 save to the narration the model
wrote, feeds its REAL text with that beat's facts to THE guard and checks the kind flagged; the
honest telling of the same beat stays clean (FakeLLM only, never the network)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate_round_segment
from aidm.dm.turn_facts import turn_facts
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, told_turn

K = ViolationKind


def _found(turn: ToldTurn, text: str | None = None) -> set[tuple[ViolationKind, str]]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {(v.kind, v.span) for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(
        turn_facts(turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text)
    )


def _assert_cases(cases: list[tuple[str, int, ViolationKind, str]]) -> None:
    for run, seq, kind, span in cases:
        found = _found(told_turn(run, seq))
        assert (kind, span) in found, (run, seq, found)


def _assert_honest(honest: dict[tuple[str, int], str], kinds: set[ViolationKind]) -> None:
    for (run, seq), text in honest.items():
        found = _found(told_turn(run, seq), text)
        assert not {k for k, _ in found} & kinds, (run, seq, found)


_FOE_LIES = {K.PHANTOM_BLOW, K.PHANTOM_HIT, K.UNRESOLVED_BLOW}


async def test_m31_foe_swings_before_its_turn(tmp_path: Path) -> None:
    """typed 391, full 154 174 786 878 886 1371: a foe that made no attack told driving its
    blade, swiping, catching a sleeve, feinting at a hero, slashing, raking, driving you back."""
    _assert_cases(
        [
            ("m31-r4-typed", 391, K.PHANTOM_BLOW, "drives its"),
            ("m31-r4-full", 154, K.PHANTOM_BLOW, "swipes blindly at"),
            ("m31-r4-full", 174, K.PHANTOM_BLOW, "catch only"),
            ("m31-r4-full", 786, K.PHANTOM_BLOW, "feints toward"),
            ("m31-r4-full", 878, K.PHANTOM_BLOW, "slashes a"),
            ("m31-r4-full", 886, K.PHANTOM_BLOW, "raking toward"),
            ("m31-r4-full", 1371, K.PHANTOM_BLOW, "driving you back"),
        ]
    )
    grick = told_turn("m31-r4-full", 1371)
    client, fake = fake_client(tmp_path, [fake_text(grick.prose), fake_text(grick.prose)])
    stream = narrate_round_segment(grick.state, list(grick.events), client)
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "driving you back" not in text
    assert len(fake.requests) == 2 and "ENGINE GUARD" in str(fake.requests[1].messages[-1])


def test_m31_foe_swings_honest_versions_pass() -> None:
    honest = {
        ("m31-r4-typed", 391): "Elowen's rapier hisses through empty air as the sahuagin twists"
        " aside, water sheeting off its shoulders. It wheels toward Brienne, shell-blade held low.",
        ("m31-r4-full", 786): "The cockatrice circles the stones in a low, skittering rush. It"
        " edges toward Rook, then veers back behind the nearest leaning stone.",
        ("m31-r4-full", 1371): "The grick's tentacles coil and sway toward the torchlight, but it"
        " doesn't commit.",
        ("m31-r4-typed", 925): "Your boots scrape the stone, and the ghoul's head snaps toward"
        " the sound.",  # a head turning is no attempt (the first draft flagged it)
    }
    _assert_honest(honest, _FOE_LIES)


def test_m31_foes_that_do_not_exist() -> None:
    """full 66 68 228: "each robed cultist", "the second cultist", "robed cultists" while the
    fight held ONE cultist; the facts now say no other foe is here."""
    _assert_cases(
        [
            ("m31-r4-full", 66, K.FOE_COUNT, "each robed cultist"),
            ("m31-r4-full", 68, K.FOE_COUNT, "second cultist"),
            ("m31-r4-full", 228, K.FOE_COUNT, "cultists"),
        ]
    )
    assert "a cultist, a zombie; no other foe of any kind is here" in _facts(
        told_turn("m31-r4-full", 66)
    )
    honest = {
        ("m31-r4-full", 66): "The zombie sways in the wet muck while the robed cultist hangs back"
        " with twitching fingers.",
        ("m31-r4-full", 1486): "Tamsin's first ray skims wide, but the third catches the mimic"
        " as it twists.",  # "third ray", not a third mimic (the first draft flagged it)
    }
    _assert_honest(honest, {K.FOE_COUNT})


def test_m31_results_told_wrong() -> None:
    """full 1262: Acid Arrow on the acid-immune mimic told eating a furrow; 1321: a Sacred Flame
    that burned the mimic told as Tamsin's and dodged; 1404: an Acid Arrow that missed but still
    dealt half damage told as a clean miss. The facts name immunity and the half damage."""
    _assert_cases(
        [
            ("m31-r4-full", 1262, K.IMMUNE_HARMED, "sizzles across"),
            ("m31-r4-full", 1321, K.PHANTOM_BLOW, "Tamsin's"),
            ("m31-r4-full", 1321, K.HIT_TOLD_MISSED, "twists aside"),
            ("m31-r4-full", 1404, K.MISS_HARM_UNTOLD, "hisses wide"),
        ]
    )
    mimic = _facts(told_turn("m31-r4-full", 1262))
    assert "Mimic is immune to acid: it took no harm" in mimic
    assert "Hurt but still standing" not in mimic
    grick = _facts(told_turn("m31-r4-full", 1404))
    assert "missed, but the miss still dealt half damage" in grick


def test_m31_results_honest_versions_pass() -> None:
    honest = {
        ("m31-r4-full", 1262): "Tamsin's acid arrow bursts against the mimic's flank and the acid"
        " runs off its slick hide, leaving it unmarked.",
        ("m31-r4-full", 1321): "Elowen's sacred flame sears down on the mimic, and its false hide"
        " blisters where the light lands.",
        ("m31-r4-full", 1404): "Tamsin's acid arrow goes wide, but the burst still splashes over"
        " the grick's flank, burning its hide.",
    }
    _assert_honest(honest, {K.IMMUNE_HARMED, K.HIT_TOLD_MISSED, K.MISS_HARM_UNTOLD, K.PHANTOM_BLOW})
