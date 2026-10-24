"""The epilogue (M5.7, SPEC 9): built only from the fact ledger, guarded, template fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from aidm.dm.epilogue import (
    EPILOGUE_STYLE,
    begin_epilogue,
    epilogue_checker,
    epilogue_event,
    epilogue_ready,
    write_epilogue,
)
from aidm.dm.epilogue_facts import epilogue_facts, epilogue_record, template_epilogue
from aidm.dm.fake_llm import FakeStream, fake_text
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.models.events import CreatureDied
from aidm.models.state import GameState
from aidm.session.reducer import ReducerError, apply, replay
from tests.ai.epilogue_fixtures import FINAL_BOSS, LEDGER_FACT, finished_campaign
from tests.ai.fake_scripts import fake_client
from tests.session.progression_fixtures import campaign_state

K = ViolationKind
GOOD = (
    "The Drowned Beacon burned bright again once the last of its enemies were beaten. "
    "Tobin Marrow never forgot the party. "
    "The smugglers' lantern code was found in the cellar, as the ledger records."
)
INVENTED = (
    "Sister Kelene crowned the heroes lords of the harbour and handed each of them "
    "five thousand gold. A dragon named Vharax then burned the beacon down."
)


def _told(state: GameState) -> str:
    """M31.1c V20: the model's prose, then the engine-written record (who lived, the quests)."""
    return " ".join([GOOD, *epilogue_record(epilogue_facts(state))])


def _user_text(messages: list[dict[str, object]]) -> str:
    return "\n".join(str(m["content"]) for m in messages if m["role"] != "system")


def test_not_ready_before_the_campaign_is_complete(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    client, fake = fake_client(tmp_path)
    assert not epilogue_ready(state) and begin_epilogue(state, client) is None
    assert not fake.requests


def test_facts_come_from_state_and_never_include_private_data() -> None:
    _, state, _, _ = finished_campaign()
    apply(state, CreatureDied(creature_id="wizard"))
    facts = epilogue_facts(state)
    text = "\n".join(facts.lines())
    assert text.count("was defeated") == 3 and FINAL_BOSS in text
    assert "Wizard fell and did not return." in text and "Fighter survived" in text
    assert LEDGER_FACT in text and "Quest" in text and "ended" in text
    for npc in state.world.npcs.values():
        if npc.motive:
            assert npc.motive not in text
        assert all(s.text not in text for s in npc.secrets if not s.revealed)


async def test_clean_epilogue_is_streamed_once_from_the_facts_only(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    client, fake = fake_client(tmp_path, [FakeStream((GOOD[:60], GOOD[60:]))])
    result = await write_epilogue(state, client)
    assert result is not None and result.text == _told(state)
    assert result.source is NarrationSource.MODEL and not result.retried
    assert len(fake.requests) == 1 and fake.requests[0].model == "deepseek-v4-pro"
    system = str(fake.requests[0].messages[0]["content"])
    body = _user_text(list(fake.requests[0].messages))
    assert system == EPILOGUE_STYLE and "Invent no names" in system
    assert LEDGER_FACT in body and FINAL_BOSS in body and "FACTS" in body
    secrets = [s.text for n in state.world.npcs.values() for s in n.secrets if not s.revealed]
    assert secrets and all(text not in body for text in secrets)
    assert result.event.text == _told(state) and result.event.source == "model"


async def test_epilogue_that_invents_events_falls_back_to_the_facts(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    client, fake = fake_client(tmp_path, [fake_text(INVENTED), fake_text(INVENTED)])
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.TEMPLATE and result.retried
    assert "Kelene" not in result.text and "Vharax" not in result.text
    assert result.text == " ".join(template_epilogue(epilogue_facts(state)))
    assert len(result.reports) == 2 and K.UNKNOWN_NAME in {
        v.kind for r in result.reports for v in r.violations
    }
    retry = _user_text(list(fake.requests[1].messages))
    assert "Kelene" not in retry and "ENGINE GUARD" in retry
    assert LEDGER_FACT in result.text and "was defeated" in result.text


async def test_unearned_gold_in_the_epilogue_is_flagged(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    greedy = "You receive ten thousand gold coins from Tobin Marrow."
    assert K.UNEARNED_REWARD in {v.kind for v in epilogue_checker(state)(greedy).violations}
    client, _ = fake_client(tmp_path, [fake_text(greedy), fake_text(GOOD)])
    result = await write_epilogue(state, client)
    assert result is not None and result.text == _told(state) and result.retried


async def test_a_clean_retry_is_used(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    client, _ = fake_client(tmp_path, [fake_text(INVENTED), fake_text(GOOD)])
    result = await write_epilogue(state, client)
    assert result is not None and result.text == _told(state) and result.retried
    assert result.source is NarrationSource.MODEL


async def test_template_epilogue_when_there_is_no_model(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    client, fake = fake_client(tmp_path)
    client.mode = client.mode.DISABLED
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.TEMPLATE
    assert not epilogue_checker(state)(result.text).violations
    assert not fake.requests


async def test_epilogue_event_replays_and_requires_a_finished_campaign(tmp_path: Path) -> None:
    start, state, log, _ = finished_campaign()
    client, _ = fake_client(tmp_path, [fake_text(GOOD)])
    stream = begin_epilogue(state, client)
    assert stream is not None
    await stream.collect()
    event = epilogue_event(stream)
    apply(state, event)
    log.append(event)
    assert state.campaign is not None and state.campaign.epilogue == _told(state)
    assert replay(start, log) == state and not epilogue_ready(state)
    _, unfinished, _ = campaign_state()
    with pytest.raises(ReducerError):
        apply(unfinished, event)
