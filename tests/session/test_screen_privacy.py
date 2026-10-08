"""M11.2: the shared screen gets only public data; a controller gets only its own private data.

A full session (two seats, one screen) runs every kind of private message: sheet, export, a
level-up offer, a private inventory listing, hit chances, a suggestion, host stats, typing, the
audio remote and a fight. Every message addressed to ONE player (`TableCore.send`) is recorded,
and no other connection may receive that object; the screen never receives a private type, and
no NPC motive or unrevealed secret appears in anything the screen got.
"""

from collections import defaultdict
from pathlib import Path

import pytest

from aidm.models.protocol import AnyServerMsg
from aidm.models.protocol_client import (
    AudioSettingsMsg,
    ExportCharacter,
    RequestHitChances,
    RequestSheet,
    SubmitAction,
    Suggestion,
    Typing,
)
from aidm.models.protocol_server import (
    AudioSettingsState,
    CharacterExport,
    CombatState,
    FloorState,
    HitChances,
    LevelUpAvailable,
    Notice,
    SheetMsg,
    Snapshot,
)
from aidm.models.world import NpcSecret
from aidm.models.world_events import LevelUpReady
from aidm.session.table import Table
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import add_npc
from tests.session.table_fixtures import (
    Seat,
    disabled_llm,
    join,
    of_type,
    running,
    screen_seat,
    start_fight,
)

SECRET = "buried the reeve's silver beneath the old well"
MOTIVE = "wants the reeve ruined before the harvest"
PRIVATE_TYPES = {
    "welcome",
    "sheet",
    "level_up_available",
    "character_export",
    "hit_chances",
    "host_stats",
    "suggestion",
    "creation_result",
    "ability_rolls",
    "pending_confirmation",
}


def _spy(table: Table, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[AnyServerMsg]]:
    sent: dict[str, list[AnyServerMsg]] = defaultdict(list)
    original = table.send

    def send(player_id: str, msg: AnyServerMsg) -> None:
        sent[player_id].append(msg)
        original(player_id, msg)

    monkeypatch.setattr(table, "send", send)
    return sent


async def _private_tour(table: Table, ann: Seat, bob: Seat) -> None:
    ann.send(RequestSheet())
    ann.send(ExportCharacter())
    ann.send(Typing(on=True))
    bob.send(AudioSettingsMsg(narration_volume=30, music_volume=20))
    table.schedule(lambda: _level_up(table))
    await table.settle()
    ann.send(SubmitAction(text="check my inventory"))
    await table.settle()
    await start_fight(table, "goblin")
    enc = table.state.encounter
    assert enc is not None
    goblin = next(cid for cid in enc.combatants if cid.startswith("goblin"))
    ann.send(RequestHitChances(target_id=goblin))
    bob.send(RequestHitChances(target_id=goblin))
    active = enc.active_id()
    adviser = bob if table.players[ann.player_id].creature_id == active else ann
    adviser.send(Suggestion(text="flank it"))
    await table.settle()


async def _level_up(table: Table) -> None:
    table.apply(LevelUpReady(creature_id="fighter", level=2))


async def test_screen_and_controllers_only_get_what_is_theirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = inn_state()
    secret = NpcSecret(id="s-well", text=SECRET)
    add_npc(state, "npc-tam", name="Old Tam", role="farmer", secrets=(secret,), motive=MOTIVE)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        screen = await screen_seat(table)
        sent = _spy(table, monkeypatch)
        await _private_tour(table, ann, bob)
        got = {"screen": screen.drain(), ann.player_id: ann.drain(), bob.player_id: bob.drain()}

    mine = got[ann.player_id]
    assert of_type(mine, SheetMsg) and of_type(mine, CharacterExport)
    assert of_type(mine, LevelUpAvailable), "the level-up offer reaches its owner"
    assert of_type(mine, HitChances) and of_type(got[bob.player_id], HitChances)
    inventory = [m for m in sent[ann.player_id] if isinstance(m, Notice)]
    assert inventory, "the inventory listing is a private notice"
    for owner, msgs in sent.items():
        ids = {id(m) for m in msgs}
        for who, received in got.items():
            if who != owner:
                leaked = [m.type for m in received if id(m) in ids]
                assert not leaked, f"{who} got {leaked} addressed to {owner}"
    seen = got["screen"]
    assert not {m.type for m in seen} & PRIVATE_TYPES
    dump = " ".join(m.model_dump_json() for m in seen)
    assert SECRET not in dump and MOTIVE not in dump
    assert all(n.text not in dump for n in inventory)
    assert of_type(seen, AudioSettingsState) and of_type(seen, FloorState)
    assert of_type(seen, CombatState) and of_type(seen, Snapshot)
    for msgs in got.values():
        assert SECRET not in " ".join(m.model_dump_json() for m in msgs)
