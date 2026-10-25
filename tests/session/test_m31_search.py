"""M31.1a V9 (docs/playtests/M31_round4.md): a typed search where something is hidden rolls ONE
discovery check at the hidden things' own DC, and the verdict and the find agree."""

import random
from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec_checks import run_request_check
from aidm.dm.tools import RequestCheckArgs
from aidm.models.abilities import Skill
from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.item_events import ItemUsed
from aidm.models.protocol_client import SubmitAction
from aidm.models.world_events import ItemDiscovered
from aidm.rules.searching import search_events
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import (
    Step,
    assert_replays,
    join,
    menu_llm,
    pick,
    running,
)

QUESTS = "m31-r4-quests"
KEY = "qi-the-twin-in-the-glass-own-1-0"  # placed hidden at quests 604, DC 10
SEARCH: Step = ("search:investigation", [], None)


def _typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


def test_m31_search_verdict_and_find_agree() -> None:
    state = replay_until(QUESTS, 937)
    for seed in range(30):
        events = search_events(random.Random(seed), state, "pc-p6", Skill.INVESTIGATION)
        check = events[0]
        assert isinstance(check, CheckResolved) and check.result.dc == 10
        found = [e.item_id for e in events if isinstance(e, ItemDiscovered)]
        assert found == ([KEY] if check.result.success else [])


def test_m31_storyteller_search_check_uses_the_hidden_dc() -> None:
    """V9, full 971-974: a 13 "failed" against the model's DC 15 and still found a DC 10 item."""
    state = replay_until("m31-r4-full", 971)
    args = RequestCheckArgs(
        actor="pc-p8", ability_or_skill=Skill.INVESTIGATION, dc_tier=DcTier.MEDIUM, reason="search"
    )
    for seed in range(20):
        result = run_request_check(
            state, args, ToolContext(actor_id="pc-p8"), random.Random(seed), tool_registries()
        )
        check = next(e for e in result.events if isinstance(e, CheckResolved))
        assert check.result.dc == 10
        found = any(isinstance(e, ItemDiscovered) for e in result.events)
        assert found == check.result.success


async def _turn(
    tmp_path: Path, seq: int, text: str, actor: str, choice: FakeStep
) -> list[AnyEvent]:
    """`choice`: the menu chooser's reading (M36.10a); the AI is otherwise down."""
    llm = menu_llm(tmp_path, choice, storyteller_down=True)[0]
    async with running(llm, replay_until(QUESTS, seq)) as (table, _):
        seat = await join(table, "Ann", actor)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


async def test_m31_typed_search_rolls_before_anything_else(tmp_path: Path) -> None:
    actor, text = _typed(QUESTS, 937)
    search = pick(SEARCH, other="pick it up, and read it")
    events = await _turn(tmp_path, 937, text, actor, search)
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert [(c.reason, c.result.dc) for c in checks[:1]] == [("search", 10)]
    assert not any(isinstance(e, ItemUsed) for e in events[: events.index(checks[0])])


async def test_m31_light_first_never_replaces_the_search(tmp_path: Path) -> None:
    line = "I light a candle, then search the ash-buried shelves for a note"
    light_then_search = pick(("use:candle-light", [], None), SEARCH)
    events = await _turn(tmp_path, 937, line, "pc-p6", light_then_search)
    used = [e.item for e in events if isinstance(e, ItemUsed)]
    checks = [e.reason for e in events if isinstance(e, CheckResolved)]
    assert used == ["candle"] and checks == ["search"]
