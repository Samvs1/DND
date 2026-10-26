"""The missing engine truths reach the narrator (M40.5, docs/playtests/M39_round7.md Z10, Z11, Z13).

The narrator prompt is rebuilt from the round-7 saves as `narrate` builds it (the audit's
`build_prompt`), and its RESOLVED block must carry the truth the story lacked:
- Z13 (r7b-typed 47-48, 357; Z3's gold lines): why nothing changed hands (Brienne carries no
  blanket; Tamsin does) and that no hero the line names refused anything;
- Z10 (r7b-full 505-513): Sleep names the creatures in its area it did not affect, and why;
- Z11 (r7b-quests 116-119): the things the search found lie where they were found, held by
  nobody, until the pick-up (120-127).
"""

from aidm.models.events import AnyEvent
from scripts.audit.replay import build_prompt
from tests.session.playtest_saves import logged, replay_until, told_turn

RESOLVED = "## RESOLVED TOOL RESULTS"
NO_ANSWER = "{who} refused, declined and ignored nothing"
HELD = "held by nobody"


def _resolved(state_run: str, seq: int, actor: str | None = None, text: str | None = None) -> str:
    told = told_turn(state_run, seq)
    actor_id = actor or told.actor_id
    words = text or told.player_text
    return _block(build_prompt(told.state, told.events, actor_id, words))


def _block(prompt: str) -> str:
    return prompt.split(RESOLVED, 1)[1].split("## STYLE", 1)[0]


def _said(run: str, seq: int) -> str:
    event = logged(run, seq).event
    text = getattr(event, "text", None)
    assert isinstance(text, str)
    return text


def test_r7_typed_47_the_blanket_is_tamsins_and_rook_refused_nothing() -> None:
    block = _resolved("m39-r7-typed", 48)
    assert "Brienne carries no Blanket: Tamsin carries it" in block
    assert NO_ANSWER.format(who="Rook") in block


def test_r7_typed_hero_to_hero_gold_lines_say_no_hero_refused() -> None:
    for seq, who in ((37, "Elowen"), (39, "Elowen"), (41, "Rook"), (148, "Brienne")):
        assert NO_ANSWER.format(who=who) in _resolved("m39-r7-typed", seq), seq


def test_r7_typed_357_the_keepsake_hand_over_is_no_refusal() -> None:
    state = replay_until("m39-r7-typed", 357)
    no_events: list[AnyEvent] = []
    prompt = build_prompt(state, no_events, "pc-p6", _said("m39-r7-typed", 352))
    assert NO_ANSWER.format(who="Tamsin") in _block(prompt)


def test_r7_full_513_sleep_names_the_creatures_it_did_not_affect() -> None:
    block = _resolved("m39-r7-full", 513)
    assert "Sleep did not affect these creatures in its area" in block
    assert "Skeleton A and Skeleton B (undead: the spell cannot affect them)" in block
    assert "Violet Fungus (too many hit points" in block
    assert "Mortha" not in block.split("Sleep did not affect", 1)[1].split("\n", 1)[0]


def test_r7_quests_119_found_items_lie_where_found_until_picked_up() -> None:
    words = _said("m39-r7-quests", 114)
    block = _resolved("m39-r7-quests", 119, "pc-p2", words)
    line = next(x for x in block.splitlines() if HELD in x)
    assert "Brass Watch" in line and "Toll-Salt" in line
    assert HELD not in _resolved("m39-r7-quests", 127)  # both picked up at 120-127
