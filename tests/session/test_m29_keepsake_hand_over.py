"""M29.7a R18 / R23 (docs/playtests/M29_round2.md): keepsakes and NPCs, from the round-2 saves.
Showing is not giving; a lifted keepsake really moves; a quest keepsake said under another name
is still handed over; a thing not carried is refused plainly, never an attitude-only gift."""

import random
from pathlib import Path

from aidm.data.dm_tiers import dm_tiers
from aidm.dm.precheck import precheck
from aidm.models.events import CheckResolved
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import ErrorMsg
from aidm.models.quest_events import KeepsakeGiven, KeepsakeTaken, QuestStepDone
from aidm.models.world_events import AttitudeChanged
from aidm.rules.lifting import lift_events
from aidm.session.reducer import replay
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, of_type, running

LINK = "qi-main-voke-reach-the-bailiff-s-own-debt-0-0"
COIN = "qi-the-keeper-s-coin-own-0-0"


async def _typed(tmp_path: Path, run: str, seq: int, hero: str, text: str) -> list[object]:
    async with running(disabled_llm(tmp_path), replay_until(run, seq)) as (table, _):
        seat = await join(table, "Ann", hero)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        errors = of_type(seat.drain(), ErrorMsg)
        return [*errors, *(e.event for e in table.log if e.seq >= start)]


def test_m29_show_is_not_give() -> None:
    """p4 291-292: "I show Farran Dell the Bailiff's Broken Link and ask him ..." gave the
    main-quest keepsake away."""
    state = replay_until("r2-p4", 291)
    text = "I show Farran Dell the Bailiff's Broken Link and ask him plainly what the debt is"
    assert precheck(state, "pc-p2", text) is None
    assert precheck(state, "pc-p2", "show the Bailiff's Broken Link to Farran Dell") is None


def test_m29_lifting_a_held_keepsake_moves_it_or_is_noticed() -> None:
    """p4 296-298: a natural-20 Sleight of Hand to lift the link back moved nothing."""
    state = replay_until("r2-p4", 296)
    outcomes: set[bool] = set()
    for seed in range(12):
        events = lift_events(state, "pc-p4", "farran-dell", LINK, random.Random(seed), dm_tiers())
        check = events[0]
        assert isinstance(check, CheckResolved) and check.result.skill == "sleight-of-hand"
        outcomes.add(check.result.success)
        after = replay(state, events)
        elowen = after.creatures["pc-p4"].pc
        assert elowen is not None
        if check.result.success:
            assert [e.keepsake_id for e in events if isinstance(e, KeepsakeTaken)] == [LINK]
            assert any(k.id == LINK for k in elowen.keepsakes)
            assert not after.world.npcs["farran-dell"].keepsakes
        else:
            assert any(isinstance(e, AttitudeChanged) for e in events)
            assert not any(k.id == LINK for k in elowen.keepsakes)
    assert outcomes == {True, False}


async def test_m29_typed_lift_runs_the_check(tmp_path: Path) -> None:
    text = (
        "While Farran Dell is distracted by the others, I slip my fingers into his pouch and"
        " lift the Bailiff's Broken Link back out (Sleight of Hand)"
    )
    events = await _typed(tmp_path, "r2-p4", 296, "pc-p4", text)
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert len(checks) == 1 and checks[0].result.skill == "sleight-of-hand"
    moved = any(isinstance(e, KeepsakeTaken) for e in events)
    assert moved == checks[0].result.success


async def test_m29_quest_keepsake_by_another_name_is_delivered(tmp_path: Path) -> None:
    """full 581-583: "I give Mord Wexley the bent silver coin" (keepsake "Mord's Coin") logged
    only an attitude change; the quest was later left behind."""
    events = await _typed(
        tmp_path, "r2-full", 581, "pc-p8", "I give Mord Wexley the bent silver coin"
    )
    given = [(e.keepsake_id, e.npc_id) for e in events if isinstance(e, KeepsakeGiven)]
    assert given == [(COIN, "mord-wexley")]
    assert any(isinstance(e, QuestStepDone) and e.quest_id == "the-keeper-s-coin" for e in events)


async def test_m29_give_what_is_not_carried_is_refused_plainly(tmp_path: Path) -> None:
    events = await _typed(tmp_path, "r2-full", 581, "pc-p8", "I give Mord Wexley the golden idol")
    assert isinstance(events[0], ErrorMsg) and "do not carry" in events[0].text
    assert not any(isinstance(e, AttitudeChanged | KeepsakeGiven) for e in events)
