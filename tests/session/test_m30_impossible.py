"""M30.1 impossible actions at the table: the verdict replays, and in a fight it keeps the
hero's action (DECISIONS M30.1). FakeLLM only."""

from pathlib import Path
from typing import Any

from aidm.dm.fake_llm import fake_tool_call
from aidm.models.events import LoggedEvent, event_adapter
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply, replay
from aidm.session.table import Table
from tests.ai.tool_fixtures import party_state, run_tool
from tests.session.table_fixtures import fake_llm, join, running, start_fight

WHY = "a person cannot jump onto a roof"


def _impossible(actor: str) -> dict[str, Any]:
    return {
        "actor": actor,
        "ability_or_skill": "athletics",
        "dc_tier": "hard",
        "reason": "jump onto the house",
        "impossible": WHY,
    }


def test_m30_impossible_replays_to_the_snapshot() -> None:
    base = party_state()
    live = base.model_copy(deep=True)
    events = list(run_tool(live, "request_check", **_impossible("fighter")).events)
    assert [type(e) for e in events] == [ActionImpossible]
    for event in events:
        apply(live, event)
    log = [
        LoggedEvent(seq=i, event=event_adapter.validate_json(e.model_dump_json()))
        for i, e in enumerate(events)
    ]
    snapshot = GameState.model_validate_json(live.model_dump_json())
    assert replay_log(base, log) == snapshot == live
    assert live.event_count == base.event_count + 1
    assert live.creatures == base.creatures and live.world == base.world


def _active(table: Table) -> str:
    enc = table.state.encounter
    assert enc is not None
    active = enc.active_id()
    assert active is not None
    return active


async def test_m30_impossible_in_a_fight_keeps_the_action(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        active = _active(table)
        seat = ann if table.players[ann.player_id].creature_id == active else bob
        fake.push(fake_tool_call("request_check", _impossible(active)))
        seat.send(SubmitAction(text="I jump onto the house"))
        await table.settle()
        enc = table.state.encounter
        assert enc is not None and enc.active_id() == active
        assert enc.combatants[active].economy.action
        verdicts = [e.event for e in table.log if isinstance(e.event, ActionImpossible)]
        assert [v.creature_id for v in verdicts] == [active]
        assert replay(table.initial, [e.event for e in table.log]) == table.state
