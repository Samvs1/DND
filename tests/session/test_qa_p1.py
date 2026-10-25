"""Regressions for the P1 defects of the adversarial QA report (docs/QA_REPORT.md, M9.5)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_tool_call
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import ErrorCode, ErrorMsg
from aidm.session.persistence import CampaignStore
from aidm.session.table import Table
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    fake_llm,
    join,
    menu_llm,
    of_type,
    pick,
    running,
    start_fight,
)


def _active(table: Table) -> str:
    enc = table.state.encounter
    assert enc is not None
    active = enc.active_id()
    assert active is not None
    return active


def _goblin(table: Table) -> str:
    return next(c.id for c in table.state.creatures.values() if c.id.startswith("goblin"))


def _creative(actor: str, target: str) -> dict[str, object]:
    return {
        "actor": actor,
        "target": target,
        "effect_kind": "minor_damage",
        "severity": "minor",
        "duration_rounds": 1,
    }


async def test_qa_01_creative_action_spends_the_action(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin", "goblin")
        active = _active(table)
        seat = ann if table.players[ann.player_id].creature_id == active else bob
        target = _goblin(table)
        fake.push(fake_tool_call("creative_effect", _creative(active, target)))
        seat.send(SubmitAction(text="I kick a burning brazier onto the foe"))
        await table.settle()
        enc = table.state.encounter
        assert enc is not None and enc.active_id() == active
        assert not enc.combatants[active].economy.action
        seat.drain()
        hp_before = {cid: c.hp for cid, c in table.state.creatures.items()}
        count = table.state.event_count
        fake.push(fake_tool_call("creative_effect", _creative(active, _goblin(table))))
        seat.send(SubmitAction(text="I kick another brazier"))
        await table.settle()
        errors = of_type(seat.drain(), ErrorMsg)
        assert errors and errors[-1].code is ErrorCode.REFUSED
        assert {cid: c.hp for cid, c in table.state.creatures.items()} == hp_before
        said = [e.event.type for e in table.log if e.seq >= count]
        assert said == ["action_declared"]  # M36.10b: the words are told, nothing else happens


async def test_qa_01_flavour_text_keeps_the_action(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        active = _active(table)
        seat = ann if table.players[ann.player_id].creature_id == active else bob
        seat.send(SubmitAction(text="I shout a battle cry"))
        await table.settle()
        enc = table.state.encounter
        assert enc is not None and enc.combatants[active].economy.action


SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)
LISTEN = pick(("search:perception", [], None))  # "I listen at the door"


async def _saved_game(tmp_path: Path, store: CampaignStore) -> Table:
    llm = menu_llm(tmp_path, SEARCH, LISTEN)[0]
    async with running(llm, inn_state(), store=store, interpreter="menu") as (table, _):
        host = await join(table, "Ann", "fighter")
        for text in ("I search behind the hearth", "look around", "I listen at the door"):
            host.send(SubmitAction(text=text))
            await table.settle()
        return table


def _damage_middle_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) >= 3
    lines[1] = lines[1][:10] + "#" + lines[1][11:]
    damaged = "".join(line + chr(10) for line in lines)
    path.write_text(damaged, encoding="utf-8")
    return damaged


async def test_qa_08_damaged_middle_line_keeps_the_log_and_prefers_the_snapshot(
    tmp_path: Path,
) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _saved_game(tmp_path, store)
    cid = table.state.campaign_id
    folder = store.root / cid
    damaged = _damage_middle_line(folder / "events.jsonl")
    loaded = store.load(cid)
    assert loaded.state.model_dump() == table.state.model_dump()
    assert loaded.recovered and loaded.warning is not None and "damaged" in loaded.warning
    kept = list(folder.glob("events.jsonl.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == damaged
    again = store.load(cid)
    assert not again.recovered and again.state.model_dump() == table.state.model_dump()


async def test_qa_08_damaged_middle_line_without_snapshot_says_progress_is_lost(
    tmp_path: Path,
) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _saved_game(tmp_path, store)
    cid = table.state.campaign_id
    folder = store.root / cid
    damaged = _damage_middle_line(folder / "events.jsonl")
    (folder / "snapshot.json").unlink()
    loaded = store.load(cid)
    assert len(loaded.log) == 1
    assert loaded.warning is not None and "lost" in loaded.warning
    kept = list(folder.glob("events.jsonl.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == damaged
