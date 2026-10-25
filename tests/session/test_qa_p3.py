"""Regressions for the P3 defects of the adversarial QA report (docs/QA_REPORT.md, M9.5)."""

from pathlib import Path

import pytest

from aidm.models.events import CreatureRemoved, LoggedEvent
from aidm.models.protocol_client import Drop, HostLoad, HostPause, HostResume, SubmitAction
from aidm.models.protocol_server import ErrorCode, ErrorMsg
from aidm.server import cli
from aidm.session.persistence import CampaignLoadError, CampaignStore
from aidm.session.table import Table
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import disabled_llm, join, menu_llm, of_type, pick, running

SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)


async def _saved(tmp_path: Path, store: CampaignStore) -> Table:
    llm = menu_llm(tmp_path, SEARCH)[0]
    async with running(llm, inn_state(), store=store) as (table, _):
        host = await join(table, "Ann", "fighter")
        host.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        return table


def _break_semantically(store: CampaignStore, table: Table) -> str:
    cid = table.state.campaign_id
    bad = LoggedEvent(seq=table.state.event_count, event=CreatureRemoved(creature_id="nobody"))
    CampaignStore.append(store.root / cid, [bad])
    return cid


async def test_qa_14_semantic_damage_is_a_clear_load_error(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    cid = _break_semantically(store, await _saved(tmp_path, store))
    with pytest.raises(CampaignLoadError, match=r"damaged: event \d+ \(creature_removed\)"):
        store.load(cid)
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, _):
        host = await join(table, "Bea", "fighter")
        host.send(HostLoad(campaign_id=cid))
        await table.settle()
        errors = of_type(host.drain(), ErrorMsg)
        assert errors and errors[-1].code is ErrorCode.REFUSED
        assert "damaged" in errors[-1].text and "creature_removed" in errors[-1].text


async def test_qa_14_cli_load_of_a_bad_or_missing_save_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = CampaignStore(tmp_path / "saves")
    cid = _break_semantically(store, await _saved(tmp_path, store))
    monkeypatch.setattr(cli, "load_env", lambda: {})
    for wanted in (cid, "nope"):
        assert cli.main(["--saves", str(store.root), "--load", wanted]) == 2
        err = capsys.readouterr().err
        assert "Cannot load saved campaign" in err and "Traceback" not in err
        assert err.isascii()


async def test_qa_15_pause_blocks_item_shop_and_level_jobs(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        hero = table.state.creatures["fighter"]
        assert hero.pc is not None and hero.pc.inventory
        item = hero.pc.inventory[0].item
        host.send(HostPause())
        await table.settle()
        host.drain()
        count = table.state.event_count
        host.send(Drop(item_id=item))
        await table.settle()
        assert of_type(host.drain(), ErrorMsg)[-1].code is ErrorCode.PAUSED
        assert table.state.event_count == count
        host.send(HostResume())
        await table.settle()
        assert table.paused is False
