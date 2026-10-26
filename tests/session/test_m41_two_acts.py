"""M41.3 (docs/playtests/M39_round7.md Z6, Z7) on the real round-7 states (fixtures m39-r7-typed,
m39-r7-quests, m39-r7-full = r7b-*), the chooser's pick scripted (FakeLLM), the storyteller down.

Causes found (the chooser's menu and prompt rebuilt offline at each seq; the round-7 runs kept no
chooser log): Z6 a travel opens the party's vote and ends the line, and `rules.menu_steps` then
returned the steps before it only: "We trudge back to the Rust Chapel and I search the iron
walls" lost the search with no word (r7b-typed 541); after a flee or an end of turn the same.
A flee is one hero's act on their own turn: "the party flees" from Elowen's turn can only move
Elowen (r7b-quests 913), and nothing told who was still in the fight. Z7 the menu is the
sender's: a search or a pickup the line gives another hero ("Tamsin searches...", sent from
Brienne's seat) had only the sender's entries, so the sender rolled and kept the finds, while a
talk check went to the named hero because the storyteller names who rolls (r7b-full 54-55)."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep, fake_tool_call
from aidm.models.events import CheckResolved
from aidm.models.world_events import ActionDeclared, ItemDiscovered, KeepsakeGained, PartyMoved
from aidm.session.menu_pick import STOPPED
from aidm.session.menu_turn import DOES
from tests.session.m32_play import play
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

TYPED, QUESTS, FULL = "m39-r7-typed", "m39-r7-quests", "m39-r7-full"
CHAPEL = "the-rust-chapel"


def _by(*steps: tuple[str, list[str], int | None, str | None]) -> FakeStep:
    rows = [{"do": e, "to": t, "qty": q, "by": b} for e, t, q, b in steps]
    return fake_tool_call("choose_actions", {"steps": rows, "other": None, "colour": ""})


async def test_v1_m41_travel_then_search_does_both(tmp_path: Path) -> None:
    """r7b-typed 541: the walk, then the search at the Rust Chapel (round 7: only the walk)."""
    steps = pick(("travel", [CHAPEL], None), ("search:investigation", [], None))
    played = await play(tmp_path, TYPED, 541, picks=[steps])
    moved = [i for i, e in enumerate(played.events) if isinstance(e, PartyMoved)]
    checks = [i for i, e in enumerate(played.events) if isinstance(e, CheckResolved)]
    assert moved and checks and moved[0] < checks[0]
    assert played.of(CheckResolved)[0].creature_id == "pc-p4"
    assert played.state.world.current_node == CHAPEL
    assert len(played.of(ActionDeclared)) == 1
    assert not [n for n in played.notices() if n.startswith("The rest of what you typed")]


async def test_v1_m41_the_rest_waits_for_the_vote(tmp_path: Path) -> None:
    """With a second player seated the walk waits for the vote: nothing is searched before it,
    and nothing is dropped with a word either (the rest rides with the agreed walk)."""
    steps = pick(("travel", [CHAPEL], None), ("search:investigation", [], None))
    played = await menu_play(tmp_path, TYPED, 541, steps, also=("pc-p2",))
    assert not played.of(CheckResolved) and not played.of(PartyMoved)
    assert not [n for n in played.notices() if n.startswith("The rest of what you typed")]


async def test_v1_m41_end_turn_tells_what_it_cut(tmp_path: Path) -> None:
    """r7b-quests 913 is Elowen's turn: an end of turn and a dodge after it; the dodge is told."""
    steps = pick(("end-turn", [], None), ("dodge", [], None))
    played = await menu_play(tmp_path, QUESTS, 913, steps, text="I end my turn and then dodge")
    assert STOPPED.format(why="your turn is over") in played.notices()


async def test_v1_m41_named_hero_searches(tmp_path: Path) -> None:
    """r7b-quests 114 "Tamsin searches the Tolltree Bridge..." from Brienne's seat: Tamsin rolls
    and finds (round 7: Brienne rolled and found both items, 115-117)."""
    played = await play(
        tmp_path, QUESTS, 114, picks=[_by(("search:investigation", [], None, "pc-p8"))]
    )
    assert [c.creature_id for c in played.of(CheckResolved)] == ["pc-p8"]
    assert {e.creature_id for e in played.of(ItemDiscovered)} <= {"pc-p8"}
    label = "Search this place by going through things (Investigation)"
    assert DOES.format(hero="Tamsin", what=label) in played.notices()


async def test_v1_m41_named_hero_picks_up_then_sender_talks(tmp_path: Path) -> None:
    """r7b-full 256: Tamsin picks up the Notes on Smoke, Brienne asks Bram (round 7: Brienne kept
    the notes, 258)."""
    steps = _by(
        ("take:notes-on-smoke", [], None, "pc-p8"), ("talk", ["bram-coldbrook"], None, None)
    )
    played = await play(tmp_path, FULL, 256, picks=[steps])
    assert [(k.creature_id, k.keepsake.name) for k in played.of(KeepsakeGained)] == [
        ("pc-p8", "Notes on Smoke")
    ]


async def test_v1_m41_named_hero_gathers_every_unit(tmp_path: Path) -> None:
    """r7b-full 404 "Rook gathers the damp bog-moss": Rook keeps all three."""
    played = await play(tmp_path, FULL, 404, picks=[_by(("take:damp-bog-moss", [], 3, "pc-p6"))])
    assert [k.creature_id for k in played.of(KeepsakeGained)] == ["pc-p6"] * 3
